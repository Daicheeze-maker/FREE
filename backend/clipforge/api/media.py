"""Media routes. Only files registered in the database (or bundled fonts) are ever served."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from ..config import FONTS_DIR
from ..db import session
from ..models import ClipCandidate, ExportJob, SourceVideo

router = APIRouter(prefix="/api")


def _file(path: str | None, media_type: str | None = None, **kw) -> FileResponse:
    if not path or not Path(path).is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(path, media_type=media_type, **kw)


@router.get("/media/video/{pid}")
def video(pid: str):
    """Source video (or its preview copy). Supports HTTP range requests for seeking."""
    with session() as s:
        src = s.query(SourceVideo).filter_by(project_id=pid).first()
        if not src:
            raise HTTPException(404, "Project not found")
        path = src.proxy_path if src.proxy_path and Path(src.proxy_path).is_file() else src.path
    return _file(path)


@router.get("/media/thumb/project/{pid}")
def project_thumb(pid: str):
    with session() as s:
        src = s.query(SourceVideo).filter_by(project_id=pid).first()
        return _file(src.thumb_path if src else None, "image/jpeg")


@router.get("/media/thumb/candidate/{cid}")
def candidate_thumb(cid: str):
    with session() as s:
        c = s.get(ClipCandidate, cid)
        return _file(c.thumb_path if c else None, "image/jpeg")


@router.get("/media/export/{eid}")
def export_file(eid: str, download: bool = False):
    with session() as s:
        e = s.get(ExportJob, eid)
        path = e.path if e and e.status == "completed" else None
    kw = {"filename": Path(path).name} if download and path else {}
    return _file(path, "video/mp4", **kw)


@router.get("/fonts/{name}")
def font(name: str):
    f = FONTS_DIR / Path(name).name  # basename only: no traversal
    if f.suffix.lower() != ".ttf":
        raise HTTPException(404, "Font not found")
    return _file(str(f), "font/ttf")


@router.post("/media/export/{eid}/reveal")
def reveal(eid: str, request: Request):
    """Show an exported file in the system file manager (PC only)."""
    if request.client and request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(403, "Only available on the computer running ClipForge.")
    with session() as s:
        e = s.get(ExportJob, eid)
        path = e.path if e else None
    if not path or not Path(path).is_file():
        raise HTTPException(404, "The exported file no longer exists.")
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(Path(path))])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", str(Path(path).parent)])
    except OSError as err:
        raise HTTPException(500, f"Could not open the folder: {err}") from err
    return {"ok": True}
