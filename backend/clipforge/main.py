"""FastAPI application: API + the built web UI, with local-only access control.

Access model
  * By default the server listens on 127.0.0.1 only.
  * Every /api request needs the session cookie. A browser on this computer gets it
    automatically; a phone on the local network (when LAN access is enabled) gets it by
    entering the pairing PIN shown in Settings.
  * Cross-origin requests and unexpected Host headers are rejected, so a web page open in
    the user's browser cannot drive the local API.
"""
from __future__ import annotations

import hmac
import ipaddress
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from starlette.staticfiles import StaticFiles

from . import settings
from .config import APP_NAME, FRONTEND_DIST, VERSION, paths
from .db import init_db
from .errors import ClipForgeError
from .jobs.manager import manager
from .logging_setup import log, setup_logging

COOKIE = "clipforge_session"
OPEN_PATHS = {"/api/session", "/api/pair"}
LOOPBACK_ONLY = {"/api/settings/pairing"}


def _is_loopback(host: str | None) -> bool:
    try:
        return bool(host) and ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _host_ok(request: Request) -> bool:
    """Host must be localhost or a literal IP (blocks DNS-rebinding); Origin must match Host."""
    host = (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]")
    if host not in ("localhost", "testserver"):
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return False
    origin = request.headers.get("origin")
    if origin and origin != "null":
        o_host = origin.split("://", 1)[-1]
        if o_host != request.headers.get("host") and not o_host.startswith(("localhost:", "127.0.0.1:", "tauri.")):
            return False
    return True


def _authed(request: Request) -> bool:
    token = settings.get("auth_token") or ""
    got = request.cookies.get(COOKIE) or ""
    return bool(token) and hmac.compare_digest(got, token)


def _set_cookie(resp: JSONResponse) -> JSONResponse:
    resp.set_cookie(COOKIE, settings.get("auth_token"), httponly=True, samesite="strict", max_age=3600 * 24 * 365)
    return resp


class PairIn(BaseModel):
    pin: str


def create_app() -> FastAPI:
    setup_logging()
    init_db()
    settings.ensure_secrets()
    from .ai import model_manager  # noqa: F401  (registers job handlers)
    from .analysis import pipeline  # noqa: F401
    from .api import clips, media, projects, system
    from .export import job as _export_job  # noqa: F401
    from .importing import local, youtube  # noqa: F401

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        manager.start()
        log.info("%s %s started; data dir %s", APP_NAME, VERSION, paths.root)
        yield
        manager.stop()

    app = FastAPI(title=APP_NAME, version=VERSION, lifespan=lifespan, docs_url=None, redoc_url=None)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api"):
            if not _host_ok(request):
                return JSONResponse({"detail": "Request origin not allowed."}, status_code=403)
            client = request.client.host if request.client else None
            if path in LOOPBACK_ONLY and not _is_loopback(client):
                return JSONResponse({"detail": "Only available on the computer running ClipForge."}, status_code=403)
            if path not in OPEN_PATHS and not _authed(request):
                return JSONResponse({"detail": "Not signed in to this ClipForge session."}, status_code=401)
        return await call_next(request)

    @app.exception_handler(ClipForgeError)
    async def clipforge_error(_: Request, exc: ClipForgeError):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception):
        log.exception("unhandled error: %s", exc)
        return JSONResponse({"detail": f"Unexpected error: {exc}"}, status_code=500)

    @app.get("/api/session")
    def session_info(request: Request):
        """A browser on this computer is signed in automatically; other devices must pair."""
        local_client = _is_loopback(request.client.host if request.client else None)
        ok = _authed(request)
        resp = JSONResponse({"authenticated": ok or local_client, "local": local_client,
                             "needs_pin": not ok and not local_client})
        return _set_cookie(resp) if local_client and not ok else resp

    @app.post("/api/pair")
    def pair(body: PairIn):
        if not settings.get("lan_access"):
            return JSONResponse({"detail": "Phone access is turned off in Settings."}, status_code=403)
        if not hmac.compare_digest(body.pin.strip(), settings.get("pair_pin") or ""):
            return JSONResponse({"detail": "That PIN is not correct."}, status_code=403)
        return _set_cookie(JSONResponse({"authenticated": True}))

    for r in (system.router, projects.router, clips.router, media.router):
        app.include_router(r)

    if (FRONTEND_DIST / "index.html").is_file():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            f = (FRONTEND_DIST / full_path).resolve()
            if full_path and f.is_file() and FRONTEND_DIST.resolve() in f.parents:
                return FileResponse(f)
            return FileResponse(FRONTEND_DIST / "index.html")
    else:
        @app.get("/", include_in_schema=False)
        def no_ui():
            return JSONResponse({"detail": "The web UI has not been built. Run `npm run build` in frontend/."})

    return app


def run() -> None:
    import argparse

    import uvicorn

    ap = argparse.ArgumentParser(description=APP_NAME)
    ap.add_argument("--port", type=int, default=8756)
    ap.add_argument("--host", default=None, help="override the listen address")
    args = ap.parse_args()
    init_db()
    host = args.host or ("0.0.0.0" if settings.get("lan_access") else "127.0.0.1")
    uvicorn.run(create_app(), host=host, port=args.port, log_level="warning")


if __name__ == "__main__":
    run()
