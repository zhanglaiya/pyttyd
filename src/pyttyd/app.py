from __future__ import annotations

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pyttyd import __static__, __version__, read_template
from pyttyd.auth import (
    SESSION_COOKIE,
    create_session_token,
    get_session_user,
    require_user,
    verify_password,
)
from pyttyd.config import get_config, load_config, save_config
from pyttyd.pty import PTY
from pyttyd.server import request_restart

load_config()

app = FastAPI(title="Pyttyd", version=__version__)
app.mount("/static", StaticFiles(directory=__static__), name="static")

_active_sessions = 0


class LoginRequest(BaseModel):
    username: str
    password: str


class ConfigUpdateRequest(BaseModel):
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    shell: str | None = None
    cwd: str | None = None
    title: str | None = None
    max_terminals: int | None = Field(default=None, ge=1, le=16)
    allow_origin: str | None = None


def _cfg():
    return get_config()


def _render(name: str, **context: Any) -> HTMLResponse:
    html = read_template(name)
    for key, value in context.items():
        html = html.replace(f"{{{{ {key} }}}}", str(value))
    return HTMLResponse(html)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    cfg = _cfg()
    if not cfg.initialized:
        return RedirectResponse("/setup")
    user = get_session_user(request, cfg.secret_key)
    if not user:
        return RedirectResponse("/login")
    return _render("terminal.html", title=cfg.title, version=__version__)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    cfg = _cfg()
    if not cfg.initialized:
        return RedirectResponse("/setup")
    if get_session_user(request, cfg.secret_key):
        return RedirectResponse("/")
    return _render("login.html", title=cfg.title)


@app.get("/setup", response_class=HTMLResponse)
async def setup_page():
    cfg = _cfg()
    if cfg.initialized:
        return RedirectResponse("/login")
    return _render("setup.html", title="Pyttyd Setup")


@app.post("/api/login")
async def login(payload: LoginRequest):
    cfg = _cfg()
    if not cfg.initialized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not initialized")
    if payload.username != cfg.username or not verify_password(payload.password, cfg.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_session_token(payload.username, cfg.secret_key)
    response = JSONResponse({"ok": True, "username": payload.username})
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return response


@app.post("/api/logout")
async def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/api/me")
async def me(request: Request):
    cfg = _cfg()
    user = get_session_user(request, cfg.secret_key)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return {"username": user, "version": __version__}


@app.get("/api/config")
async def get_public_config(request: Request):
    cfg = _cfg()
    require_user(request, cfg.secret_key)
    return cfg.public_dict()


@app.put("/api/config")
async def update_config(request: Request, payload: ConfigUpdateRequest):
    cfg = _cfg()
    require_user(request, cfg.secret_key)

    updates = payload.model_dump(exclude_none=True)
    password = updates.pop("password", None)
    cfg.apply_updates(updates)
    if password:
        from pyttyd.auth import hash_password

        cfg.password_hash = hash_password(password)
    save_config(cfg)
    return {"ok": True, "config": cfg.public_dict(), "restart_required": True}


@app.post("/api/restart")
async def restart_server(request: Request):
    cfg = _cfg()
    require_user(request, cfg.secret_key)

    loop = asyncio.get_running_loop()
    loop.call_later(0.5, request_restart)
    return JSONResponse({"ok": True, "message": "Server restarting..."})


@app.websocket("/ws/tty")
async def websocket_endpoint(
    websocket: WebSocket,
    rows: int = 24,
    cols: int = 80,
):
    global _active_sessions
    cfg = _cfg()
    token = websocket.cookies.get(SESSION_COOKIE) or websocket.query_params.get("token")
    user = None
    if token:
        from pyttyd.auth import decode_session_token

        payload = decode_session_token(token, cfg.secret_key)
        user = payload.get("sub") if payload else None

    if not user:
        await websocket.close(code=4401, reason="Unauthorized")
        return

    if _active_sessions >= cfg.max_terminals:
        await websocket.close(code=4429, reason="Too many terminals")
        return

    await websocket.accept()
    _active_sessions += 1
    try:
        async with PTY(websocket, cfg) as pty:
            await pty.run(rows=rows, cols=cols)
    except WebSocketDisconnect:
        pass
    finally:
        _active_sessions = max(0, _active_sessions - 1)


@app.get("/health")
async def health():
    return {"status": "ok", "version": __version__}
