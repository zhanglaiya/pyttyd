"""Background process management for pyttyd."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from pyttyd.config import config_path, get_config


def _runtime_dir() -> Path:
    return config_path().parent


def pid_file() -> Path:
    return _runtime_dir() / "pyttyd.pid"


def log_file() -> Path:
    return _runtime_dir() / "pyttyd.log"


def _is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read_pid() -> int | None:
    path = pid_file()
    if not path.exists():
        return None
    try:
        pid = int(path.read_text().strip())
    except (ValueError, OSError):
        return None
    if not _is_alive(pid):
        path.unlink(missing_ok=True)
        return None
    return pid


def pids_on_port(port: int) -> list[int]:
    try:
        out = subprocess.check_output(
            ["lsof", "-ti", f":{port}"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    pids: list[int] = []
    for token in out.split():
        token = token.strip()
        if token.isdigit():
            pids.append(int(token))
    return pids


def clear_port(port: int) -> list[int]:
    killed: list[int] = []
    for pid in pids_on_port(port):
        try:
            os.kill(pid, signal.SIGTERM)
            killed.append(pid)
        except ProcessLookupError:
            continue
    if killed:
        time.sleep(0.5)
        for pid in pids_on_port(port):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                continue
    return killed


def process_cmdline(pid: int) -> str:
    proc_path = Path(f"/proc/{pid}/cmdline")
    if not proc_path.exists():
        return ""
    raw = proc_path.read_bytes().replace(b"\x00", b" ").decode("utf-8", errors="replace")
    return raw.strip()


def start_background(*, force: bool = False) -> int:
    existing = read_pid()
    if existing is not None and not force:
        return existing
    if existing is not None and force:
        stop_background()

    runtime = _runtime_dir()
    runtime.mkdir(parents=True, exist_ok=True)

    cfg = str(config_path())
    cmd = [sys.executable, "-m", "pyttyd", "--config", cfg]
    env = os.environ.copy()
    env["PYTTYD_CONFIG"] = cfg

    log_path = log_file()
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n--- start {time.strftime('%Y-%m-%d %H:%M:%S')} config={cfg} ---\n")
        log.flush()
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=env,
        )

    pid_file().write_text(str(proc.pid), encoding="utf-8")
    return proc.pid


def stop_background() -> bool:
    pid = read_pid()
    if pid is None:
        return False

    os.kill(pid, signal.SIGTERM)
    for _ in range(20):
        if not _is_alive(pid):
            break
        time.sleep(0.2)
    else:
        os.kill(pid, signal.SIGKILL)

    pid_file().unlink(missing_ok=True)
    return True


def restart_background() -> int:
    cfg = get_config()
    stop_background()
    clear_port(cfg.port)
    return start_background(force=True)


def status_background() -> tuple[str, int | None]:
    pid = read_pid()
    if pid is None:
        return "stopped", None
    return "running", pid
