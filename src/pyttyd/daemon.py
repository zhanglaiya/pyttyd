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


def start_background() -> int:
    existing = read_pid()
    if existing is not None:
        return existing

    runtime = _runtime_dir()
    runtime.mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, "-m", "pyttyd"]
    cfg_env = os.environ.get("PYTTYD_CONFIG")
    if cfg_env:
        cmd.extend(["--config", cfg_env])

    log_path = log_file()
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n--- start {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        log.flush()
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=os.environ.copy(),
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


def status_background() -> tuple[str, int | None]:
    pid = read_pid()
    if pid is None:
        return "stopped", None
    cfg = get_config()
    return "running", pid
