"""Authentication helpers for pyttyd."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Dict, Optional, TYPE_CHECKING

from fastapi import HTTPException, Request, status

if TYPE_CHECKING:
    from pyttyd.config import Config

SESSION_COOKIE = "pyttyd_session"
SESSION_TTL = 60 * 60 * 24 * 7  # 7 days


def hash_password(password: str, *, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return "pbkdf2_sha256$120000$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_b64, digest_b64 = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(iterations),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def authenticate(cfg: "Config", username: str, password: str) -> bool:
    username = username.strip()
    password = password.strip()
    expected_user = (cfg.username or "").strip()
    if username != expected_user:
        return False
    if cfg.password_hash and verify_password(password, cfg.password_hash):
        return True
    stored = (cfg.password or "").strip()
    if stored and hmac.compare_digest(password, stored):
        from pyttyd.config import save_config, set_password

        set_password(cfg, password)
        save_config(cfg)
        return True
    return False


def _cookie_secure(request: Request) -> bool:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    return proto == "https"


def _sign(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def create_session_token(username: str, secret_key: str) -> str:
    payload = {
        "sub": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + SESSION_TTL,
        "nonce": secrets.token_hex(8),
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = _sign(raw, secret_key)
    token = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    return f"{token}.{signature}"


def decode_session_token(token: str, secret_key: str) -> Optional[Dict[str, Any]]:
    try:
        encoded, signature = token.rsplit(".", 1)
        padding = "=" * (-len(encoded) % 4)
        raw = base64.urlsafe_b64decode(encoded + padding)
        if not hmac.compare_digest(_sign(raw, secret_key), signature):
            return None
        payload = json.loads(raw.decode("utf-8"))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except (ValueError, json.JSONDecodeError, TypeError):
        return None


def get_session_user(request: Request, secret_key: str) -> Optional[str]:
    token = request.cookies.get(SESSION_COOKIE) or request.headers.get("X-Pyttyd-Token")
    if not token:
        return None
    payload = decode_session_token(token, secret_key)
    if not payload:
        return None
    return payload.get("sub")


def require_user(request: Request, secret_key: str) -> str:
    user = get_session_user(request, secret_key)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user
