"""System routes: status, settings, models, jobs, logs, metadata."""
from __future__ import annotations

import shutil
import socket

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import hardware, logging_setup, settings
from ..ai import llm, model_manager
from ..ai.catalog import RECOMMENDED
from ..analysis import clips as clip_engine
from ..analysis import pipeline
from ..captions import engine as cap
from ..config import APP_NAME, VERSION, VIDEO_EXTENSIONS, paths
from ..db import session
from ..errors import ClipForgeError
from ..export import render
from ..jobs.manager import manager
from ..media import ffmpeg as ff
from ..models import CaptionStyle, Job

router = APIRouter(prefix="/api")


def lan_ip() -> str | None:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # no packet is sent; this only selects the outbound interface
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


@router.get("/system/status")
def status(refresh: bool = False):
    cfg = settings.get_all()
    models = model_manager.list_models()["models"]
    installed = {m["purpose"] for m in models if m["status"] == "installed"}
    return {
        "app": APP_NAME, "version": VERSION, "data_dir": str(paths.root), "setup_complete": cfg["setup_complete"],
        "tools": ff.tool_versions(), "hardware": hardware.detect(refresh), "disk": hardware.disk(paths.root),
        "models_ready": {"asr": "asr" in installed, "audio_tagging": "audio_tagging" in installed,
                         "vad": "vad" in installed, "face": "face" in installed},
        "recommended_models": RECOMMENDED,
        "llm": {"enabled": cfg["llm_enabled"], "local": llm.is_local_url(cfg["llm_base_url"])},
        "lan": {"enabled": cfg["lan_access"], "ip": lan_ip()},
        "output_dir": cfg["output_dir"] or str(paths.exports),
    }


@router.get("/meta")
def meta():
    return {
        "categories": clip_engine.CATEGORIES, "score_labels": clip_engine.SCORE_LABELS,
        "caption_presets": cap.PRESETS, "fonts": cap.FONTS, "platform_presets": render.PLATFORM_PRESETS,
        "export_defaults": render.export_settings(None), "analysis_defaults": pipeline.analysis_params(None),
        "stages": [{"id": k, "label": pipeline.STAGE_LABELS[k]} for k, _ in pipeline.STAGES],
        "video_extensions": sorted(VIDEO_EXTENSIONS), "profiles": list(settings.PROFILES),
    }


@router.get("/settings")
def get_settings():
    return settings.get_all()


@router.put("/settings")
def put_settings(values: dict):
    values = {k: v for k, v in values.items() if k not in ("auth_token", "pair_pin")}
    if "llm_api_key" in values and values["llm_api_key"] in (True, False):
        values.pop("llm_api_key")  # the UI only ever sees whether a key is set
    if values.get("output_dir"):
        from pathlib import Path

        try:
            Path(values["output_dir"]).expanduser().mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise HTTPException(400, f"That output folder cannot be used: {e}") from e
    try:
        settings.update(values)
    except KeyError as e:
        raise HTTPException(400, str(e)) from e
    return settings.get_all()


@router.post("/settings/llm-test")
def llm_test():
    try:
        return llm.test_connection()
    except ClipForgeError as e:
        return {"ok": False, "error": str(e)}


@router.get("/settings/pairing")
def pairing():
    """Phone pairing details. Only meaningful on the PC itself; the middleware restricts it to loopback."""
    cfg = settings.get_all(include_secrets=True)
    return {"pin": cfg["pair_pin"], "ip": lan_ip(), "enabled": cfg["lan_access"]}


@router.get("/fs/list")
def fs_list(path: str = ""):
    """Folder browser for choosing a video on this computer (loopback only; lists folders and videos)."""
    import os
    import string
    import sys
    from pathlib import Path

    home = Path.home()
    p = Path(path).expanduser() if path else home
    if not p.is_dir():
        raise HTTPException(400, "That folder does not exist.")
    dirs, files = [], []
    try:
        for e in sorted(os.scandir(p), key=lambda e: e.name.lower()):
            if e.name.startswith((".", "$")):
                continue
            try:
                if e.is_dir():
                    dirs.append({"name": e.name, "path": e.path})
                elif Path(e.name).suffix.lower() in VIDEO_EXTENSIONS:
                    files.append({"name": e.name, "path": e.path, "size": e.stat().st_size})
            except OSError:
                continue
    except PermissionError as e:
        raise HTTPException(403, "ClipForge is not allowed to read that folder.") from e
    roots = [{"name": "Home", "path": str(home)}]
    for name in ("Videos", "Movies", "Downloads", "Desktop"):
        if (home / name).is_dir():
            roots.append({"name": name, "path": str(home / name)})
    if sys.platform == "win32":
        roots += [{"name": f"{d}:", "path": f"{d}:\\"} for d in string.ascii_uppercase if Path(f"{d}:\\").exists()]
    return {"path": str(p), "parent": str(p.parent) if p.parent != p else None, "dirs": dirs, "files": files,
            "roots": roots}


# ---- models -----------------------------------------------------------------
@router.get("/models")
def models():
    return model_manager.list_models()


@router.post("/models/{model_id}/download")
def model_download(model_id: str):
    return {"job_id": model_manager.start_download(model_id)}


@router.post("/models/{model_id}/pause")
def model_pause(model_id: str):
    with session() as s:
        jobs = s.query(Job).filter(Job.type == "model_download", Job.status.in_(["running", "queued"])).all()
        ids = [j.id for j in jobs if j.params.get("model_id") == model_id]
    for j in ids:
        manager.pause(j)
    return {"ok": True}


@router.post("/models/{model_id}/verify")
def model_verify(model_id: str):
    return model_manager.verify(model_id)


@router.post("/models/{model_id}/select")
def model_select(model_id: str):
    model_manager.select(model_id)
    return {"ok": True}


@router.delete("/models/{model_id}")
def model_remove(model_id: str):
    model_manager.remove(model_id)
    return {"ok": True}


# ---- jobs -------------------------------------------------------------------
@router.get("/jobs")
def jobs(project_id: str | None = None, active: bool = False, limit: int = 50):
    with session() as s:
        q = s.query(Job)
        if project_id:
            q = q.filter(Job.project_id == project_id)
        if active:
            q = q.filter(Job.status.in_(["queued", "running", "paused"]))
        return [j.to_dict() for j in q.order_by(Job.created_at.desc(), Job.id).limit(limit).all()]


@router.get("/jobs/{job_id}")
def job(job_id: str):
    with session() as s:
        j = s.get(Job, job_id)
        if not j:
            raise HTTPException(404, "Job not found")
        return j.to_dict()


@router.post("/jobs/{job_id}/cancel")
def job_cancel(job_id: str):
    manager.cancel(job_id)
    return {"ok": True}


@router.post("/jobs/{job_id}/pause")
def job_pause(job_id: str):
    manager.pause(job_id)
    return {"ok": True}


@router.post("/jobs/{job_id}/resume")
def job_resume(job_id: str):
    manager.resume(job_id)
    return {"ok": True}


@router.post("/jobs/{job_id}/retry")
def job_retry(job_id: str):
    """Re-queue a failed/cancelled/interrupted job. Finished analysis stages are not repeated."""
    with session() as s:
        j = s.get(Job, job_id)
        if not j:
            raise HTTPException(404, "Job not found")
        if j.status not in ("failed", "cancelled", "interrupted"):
            raise HTTPException(400, "Only failed, cancelled or interrupted jobs can be retried.")
        type_, params, pid, cid = j.type, dict(j.params), j.project_id, j.clip_id
        stages = list(j.completed_stages or []) if j.type == "analysis" else []
    if type_ == "export":
        from ..export.job import submit_export

        return submit_export(cid, params.get("settings"))
    if type_ == "model_download":
        return {"job_id": model_manager.start_download(params["model_id"])}
    return {"job_id": manager.submit(type_, params, project_id=pid, clip_id=cid, completed_stages=stages)}


# ---- caption styles ---------------------------------------------------------
class StyleIn(BaseModel):
    name: str
    data: dict


@router.get("/caption-styles")
def styles():
    with session() as s:
        return [x.to_dict() for x in s.query(CaptionStyle).order_by(CaptionStyle.name).all()]


@router.post("/caption-styles")
def save_style(body: StyleIn):
    name = body.name.strip()[:80]
    if not name:
        raise HTTPException(400, "Give the style a name.")
    with session() as s:
        row = s.query(CaptionStyle).filter_by(name=name).first()
        data = cap.normalize_style({**body.data, "preset": "custom"})
        if row:
            row.data = data
        else:
            row = CaptionStyle(name=name, data=data)
            s.add(row)
        s.flush()
        return row.to_dict()


@router.delete("/caption-styles/{style_id}")
def delete_style(style_id: str):
    with session() as s:
        row = s.get(CaptionStyle, style_id)
        if row:
            s.delete(row)
    return {"ok": True}


# ---- diagnostics ------------------------------------------------------------
@router.get("/logs")
def logs(lines: int = 300):
    return {"text": logging_setup.tail(min(lines, 2000)), "path": str(paths.logs / "clipforge.log")}


@router.post("/system/cleanup")
def cleanup():
    """Delete temporary files (render work folders, cached analysis audio)."""
    freed = 0
    for f in paths.tmp.glob("*"):
        if f.is_dir():
            freed += sum(x.stat().st_size for x in f.rglob("*") if x.is_file())
            shutil.rmtree(f, ignore_errors=True)
        else:
            freed += f.stat().st_size
            f.unlink(missing_ok=True)
    with session() as s:
        busy = {j.project_id for j in s.query(Job).filter(Job.status.in_(["queued", "running", "paused"])).all()}
    for wav in paths.projects.glob("*/audio.wav"):
        if wav.parent.name not in busy:
            freed += wav.stat().st_size
            wav.unlink(missing_ok=True)
    return {"freed_bytes": freed}
