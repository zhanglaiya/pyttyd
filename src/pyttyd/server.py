"""Server launcher with graceful restart support."""

from __future__ import annotations

import os
import signal
import sys

import uvicorn

from pyttyd.config import get_config


def run_server(*, reload: bool = False) -> None:
    cfg = get_config()
    uvicorn.run(
        "pyttyd.app:app",
        host=cfg.host,
        port=cfg.port,
        reload=reload,
        log_level="info",
    )


def request_restart() -> None:
    """Re-exec the current process to apply configuration changes."""
    os.execv(sys.executable, [sys.executable, "-m", "pyttyd"] + sys.argv[1:])


def schedule_restart(delay: float = 0.5) -> None:
    signal.alarm(max(1, int(delay)))
