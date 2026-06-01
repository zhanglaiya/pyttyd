"""Configuration management for pyttyd."""

from __future__ import annotations

import json
import os
import secrets
import socket
import stat
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from pyttyd.auth import hash_password


DEFAULT_CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "pyttyd"
DEFAULT_CONFIG_PATH = Path(os.environ.get("PYTTYD_CONFIG", DEFAULT_CONFIG_DIR / "config.json"))


def _default_host() -> str:
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return "127.0.0.1"


@dataclass
class Config:
    host: str = "0.0.0.0"
    port: int = 8221
    username: str = "admin"
    password: str = ""
    password_hash: str = ""
    shell: str = field(default_factory=lambda: os.environ.get("SHELL", "/bin/bash"))
    cwd: Optional[str] = None
    title: str = "Pyttyd"
    max_terminals: int = 4
    secret_key: str = field(default_factory=lambda: secrets.token_hex(32))
    allow_origin: str = "*"
    initialized: bool = False

    def to_dict(self, *, include_secrets: bool = False) -> Dict[str, Any]:
        data = asdict(self)
        if not include_secrets:
            data.pop("password_hash", None)
            data.pop("secret_key", None)
            data.pop("password", None)
        return data

    def public_dict(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "shell": self.shell,
            "cwd": self.cwd or str(Path.home()),
            "title": self.title,
            "max_terminals": self.max_terminals,
            "allow_origin": self.allow_origin,
            "initialized": self.initialized,
        }

    def apply_updates(self, updates: Dict[str, Any]) -> None:
        allowed = {
            "host",
            "port",
            "username",
            "shell",
            "cwd",
            "title",
            "max_terminals",
            "allow_origin",
        }
        for key, value in updates.items():
            if key not in allowed:
                continue
            if key == "port":
                value = int(value)
            elif key == "max_terminals":
                value = max(1, min(16, int(value)))
            elif key == "cwd" and value in ("", None):
                value = None
            setattr(self, key, value)


_config: Optional[Config] = None
_config_path: Path = DEFAULT_CONFIG_PATH


def config_path() -> Path:
    return _config_path


def set_config_path(path: Path) -> None:
    global _config_path
    _config_path = path.expanduser().resolve()


def load_config(path: Optional[Path] = None) -> Config:
    global _config
    target = path or _config_path
    set_config_path(target)

    if not target.exists():
        _config = Config()
        return _config

    with target.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    _config = Config(**{k: v for k, v in raw.items() if k in Config.__dataclass_fields__})
    _normalize_config(_config)
    return _config


def _normalize_config(cfg: Config) -> None:
    cfg.username = (cfg.username or "").strip()
    if cfg.password is None:
        cfg.password = ""
    else:
        cfg.password = str(cfg.password).strip()


def get_config() -> Config:
    """Load the latest config from disk (safe after CLI edits without restart)."""
    return load_config()


def save_config(config: Optional[Config] = None, path: Optional[Path] = None) -> Path:
    target = path or _config_path
    target.parent.mkdir(parents=True, exist_ok=True)
    cfg = config or get_config()

    with target.open("w", encoding="utf-8") as fh:
        json.dump(asdict(cfg), fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    target.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return target


def init_config(
    path: Optional[Path] = None,
    *,
    username: Optional[str] = None,
    password: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    force: bool = False,
) -> tuple[Config, str, str]:
    target = path or _config_path
    if target.exists() and not force:
        raise FileExistsError(f"Config already exists at {target}. Use --force to overwrite.")

    plain_password = password or secrets.token_urlsafe(12)
    user = username or f"admin_{secrets.token_hex(3)}"

    cfg = Config(
        host=host or "0.0.0.0",
        port=port or 8221,
        username=user,
        password=plain_password,
        password_hash=hash_password(plain_password),
        shell=os.environ.get("SHELL", "/bin/bash"),
        cwd=None,
        title="Pyttyd",
        max_terminals=4,
        secret_key=secrets.token_hex(32),
        allow_origin="*",
        initialized=True,
    )
    save_config(cfg, target)
    return cfg, user, plain_password


def show_config(cfg: Config) -> Dict[str, Any]:
    data = cfg.to_dict(include_secrets=False)
    data["config_path"] = str(_config_path)
    data["listen"] = f"http://{cfg.host}:{cfg.port}"
    data["shell"] = cfg.shell
    data["cwd"] = cfg.cwd or str(Path.home())
    data["username"] = cfg.username
    if cfg.password:
        data["password"] = cfg.password
    elif cfg.password_hash:
        data["password"] = "(not stored — run: pyttyd config reset-password)"
    else:
        data["password"] = "(not set)"
    return data


def set_password(cfg: Config, plain_password: str) -> None:
    plain_password = plain_password.strip()
    cfg.password = plain_password
    cfg.password_hash = hash_password(plain_password)


def repair_credentials(cfg: Config) -> bool:
    """Re-sync password_hash (and trim username) from stored plain password."""
    _normalize_config(cfg)
    if not cfg.password:
        return False
    set_password(cfg, cfg.password)
    return True
