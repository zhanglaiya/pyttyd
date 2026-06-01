import array
import fcntl
import json
import logging
import os
import asyncio
import signal
import struct
import sys
import termios

from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from pyttyd.config import Config, get_config

TIOCSWINSZ = termios.TIOCSWINSZ

try:
    TIOCGPGRP = termios.TIOCGPGRP
except AttributeError:
    TIOCGPGRP = None


def _shell_env() -> dict:
    env = os.environ.copy()
    if not env.get("LANG") and not env.get("LC_ALL"):
        env["LANG"] = "C.UTF-8"
        env["LC_ALL"] = "C.UTF-8"
    env.setdefault("TERM", "xterm-256color")
    env.setdefault("COLORTERM", "truecolor")
    return env


def _default_shell(configured: Optional[str] = None) -> str:
    return configured or os.environ.get("SHELL") or "/bin/bash"


def _shell_command(shell: str) -> list:
    base = os.path.basename(shell)
    if base in ("bash", "zsh", "sh", "ksh"):
        return [shell, "-il"]
    if base == "fish":
        return [shell, "-l"]
    return [shell]


def _configure_tty_fd(fd: int) -> None:
    attrs = termios.tcgetattr(fd)
    attrs[3] |= termios.ISIG | termios.ICANON | termios.ECHO
    attrs[6][termios.VINTR] = 3
    termios.tcsetattr(fd, termios.TCSANOW, attrs)


def _foreground_pgid(master_fd: int) -> Optional[int]:
    if TIOCGPGRP is None:
        return None
    try:
        buf = array.array("i", [0])
        fcntl.ioctl(master_fd, TIOCGPGRP, buf, True)
        pgid = buf[0]
        return pgid if pgid > 0 else None
    except OSError:
        return None


class PTY:

    def __init__(self, websocket: WebSocket, config: Optional[Config] = None):
        self.ws = websocket
        self.config = config or get_config()
        self.pty: Optional[int] = None
        self.child_pid: Optional[int] = None

    def _set_winsize(self, rows: int, cols: int) -> None:
        if self.pty is None:
            return
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(self.pty, TIOCSWINSZ, winsize)

    def _send_intr(self) -> None:
        if self.pty is not None:
            os.write(self.pty, b"\x03")
        self._signal_foreground(signal.SIGINT)

    def _signal_foreground(self, sig: signal.Signals) -> None:
        if self.pty is not None:
            pgid = _foreground_pgid(self.pty)
            if pgid is not None:
                try:
                    os.killpg(pgid, sig)
                    return
                except OSError:
                    pass
        if self.child_pid is not None:
            try:
                os.killpg(self.child_pid, sig)
            except OSError:
                try:
                    os.kill(self.child_pid, sig)
                except OSError:
                    pass

    async def read_ws(self):
        while True:
            try:
                data = await self.ws.receive_text()
            except WebSocketDisconnect:
                break
            except Exception as exc:
                logging.error("websocket.receive_text error", exc_info=exc)
                await self.ws.close(reason=str(exc))
                break

            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue

            sig_name = event.get("signal")
            if sig_name == "SIGINT":
                self._send_intr()
                continue
            if sig_name == "SIGTSTP":
                self._signal_foreground(signal.SIGTSTP)
                continue

            if "input" in event and event["input"]:
                if self.pty is not None:
                    raw = event["input"]
                    if raw == "\x03" or "\x03" in raw:
                        self._send_intr()
                    else:
                        os.write(self.pty, raw.encode("utf-8"))
                continue

            resize = event.get("resize")
            if resize and len(resize) == 2:
                cols, rows = resize
                self._set_winsize(int(rows), int(cols))

    async def read_pty(self):
        while True:
            try:
                if self.pty is None:
                    break
                if hasattr(asyncio, "to_thread"):
                    data = await asyncio.to_thread(os.read, self.pty, 4096)
                else:
                    data = await asyncio.get_running_loop().run_in_executor(
                        None, os.read, self.pty, 4096
                    )
            except OSError as exc:
                logging.error("pty read error", exc_info=exc)
                await self.ws.close(reason=str(exc))
                break
            if not data:
                break
            await self.ws.send_bytes(data)

    async def __aenter__(self):
        shell = _default_shell(self.config.shell)
        cwd = self.config.cwd or os.path.expanduser("~")
        env = _shell_env()
        env["SHELL"] = shell
        cmd = _shell_command(shell)

        pid, master_fd = os.forkpty()
        if pid == 0:
            try:
                _configure_tty_fd(0)
                os.chdir(cwd)
                os.execvpe(cmd[0], cmd, env)
            except OSError:
                os._exit(127)
            os._exit(127)

        self.pty = master_fd
        self.child_pid = pid
        return self

    async def run(self, rows: int = 24, cols: int = 80):
        self._set_winsize(rows, cols)
        read_pty = asyncio.create_task(self.read_pty())
        read_ws = asyncio.create_task(self.read_ws())

        done, pending = await asyncio.wait(
            [read_pty, read_ws],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.child_pid is not None:
            try:
                os.kill(self.child_pid, signal.SIGTERM)
            except OSError:
                pass
            try:
                if hasattr(asyncio, "to_thread"):
                    await asyncio.to_thread(os.waitpid, self.child_pid, 0)
                else:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, os.waitpid, self.child_pid, 0)
            except (ChildProcessError, OSError):
                pass
            self.child_pid = None
        if self.pty is not None:
            os.close(self.pty)
            self.pty = None
