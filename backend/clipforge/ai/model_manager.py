"""Download, pause/resume, verify, select and remove local models."""
from __future__ import annotations

import shutil
import tarfile
import urllib.request
from pathlib import Path

from .. import settings
from ..config import paths
from ..db import session
from ..errors import CancelledError, ModelError
from ..jobs.manager import JobContext, manager
from ..logging_setup import log
from ..models import AIModel, now
from .catalog import BY_ID, CATALOG, EXTERNAL_MODELS

SETTING_FOR_PURPOSE = {"asr": "asr_model", "audio_tagging": "tagger_model", "face": "face_model"}


def model_dir(model_id: str) -> Path:
    return paths.models / model_id


def installed_path(model_id: str) -> Path | None:
    with session() as s:
        row = s.get(AIModel, model_id)
        if row and row.status == "installed" and row.path and Path(row.path).exists():
            return Path(row.path)
    return None


def active(purpose: str) -> tuple[dict, Path] | None:
    """The selected model for a purpose, or the only installed one. Never silently downloads."""
    key = SETTING_FOR_PURPOSE.get(purpose)
    chosen = settings.get(key) if key else ""
    ids = [chosen] if chosen else []
    ids += [m["id"] for m in CATALOG if m["purpose"] == purpose and m["id"] != chosen]
    for mid in ids:
        p = installed_path(mid) if mid in BY_ID else None
        if p:
            return BY_ID[mid], p
    return None


def list_models() -> dict:
    with session() as s:
        rows = {r.id: r.to_dict() for r in s.query(AIModel).all()}
    current = settings.get_all()
    out = []
    for m in CATALOG:
        r = rows.get(m["id"], {})
        status = r.get("status", "not_installed")
        if status == "installed" and not (r.get("path") and Path(r["path"]).exists()):
            status = "not_installed"  # files were removed outside the app
        key = SETTING_FOR_PURPOSE.get(m["purpose"])
        act = active(m["purpose"]) if key else None
        out.append({**{k: v for k, v in m.items() if k not in ("archive_dir",)},
                    "status": status, "bytes_done": r.get("bytes_done", 0),
                    "bytes_total": r.get("bytes_total") or m["size_bytes"],
                    "verified_at": r.get("verified_at"), "error": r.get("error"),
                    "active": bool(act and act[0]["id"] == m["id"]),
                    "selected": bool(key and current.get(key) == m["id"])})
    return {"models": out, "external": EXTERNAL_MODELS, "models_dir": str(paths.models)}


def _set(model_id: str, **fields) -> None:
    with session() as s:
        row = s.get(AIModel, model_id)
        if not row:
            row = AIModel(id=model_id)
            s.add(row)
        for k, v in fields.items():
            setattr(row, k, v)


def start_download(model_id: str) -> str:
    if model_id not in BY_ID:
        raise ModelError("Unknown model.")
    need = BY_ID[model_id]["size_bytes"] * 2.5  # archive + extracted copy
    free = shutil.disk_usage(paths.root).free
    if free < need:
        raise ModelError(f"Not enough disk space: about {need / 2**30:.1f} GB needed, {free / 2**30:.1f} GB free.")
    _set(model_id, status="downloading", error=None, bytes_total=BY_ID[model_id]["size_bytes"])
    return manager.submit("model_download", {"model_id": model_id})


def download_job(ctx: JobContext) -> dict:
    model_id = ctx.params["model_id"]
    meta = BY_ID[model_id]
    dest = model_dir(model_id)
    dest.mkdir(parents=True, exist_ok=True)
    ctx.start_stage("download", f"Downloading {meta['name']}")
    try:
        if "hf_repo" in meta:
            _download_hf(ctx, meta, dest)
        else:
            _download_url(ctx, meta, dest)
        _set(model_id, status="installed", path=str(dest), error=None, bytes_done=meta["size_bytes"])
        verify(model_id)
    except CancelledError:
        # a cancelled/paused download keeps its partial file so it can resume with an HTTP Range request
        _set(model_id, status="paused")
        raise
    except Exception as e:  # noqa: BLE001
        _set(model_id, status="error", error=str(e))
        raise ModelError(f"Download failed: {e}") from e
    return {"model_id": model_id}


def _download_url(ctx: JobContext, meta: dict, dest: Path) -> None:
    url = meta["url"]
    fname = url.rsplit("/", 1)[1]
    part = dest / (fname + ".part")
    done = part.stat().st_size if part.exists() else 0
    req = urllib.request.Request(url, headers={"User-Agent": "ClipForge"})
    if done:
        req.add_header("Range", f"bytes={done}-")
    with urllib.request.urlopen(req, timeout=60) as resp:
        if done and resp.status != 206:  # server ignored the range: start over
            done = 0
        total = done + int(resp.headers.get("Content-Length") or 0)
        _set(meta["id"], bytes_total=total)
        with open(part, "ab" if done else "wb") as f:
            while True:
                ctx.check_cancel_only()
                chunk = resp.read(1 << 18)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                ctx.progress(done / total * 0.9 if total else 0, f"{done / 2**20:.0f} / {total / 2**20:.0f} MB")
                _set(meta["id"], bytes_done=done)
    if total and done != total:
        raise ModelError(f"Incomplete download ({done} of {total} bytes).")
    final = dest / fname
    part.replace(final)
    if fname.endswith(".tar.bz2"):
        ctx.message("Extracting")
        with tarfile.open(final) as tf:
            tf.extractall(dest, filter="data")  # "data" filter blocks path traversal / special files
        final.unlink()
    ctx.progress(1.0, "Installed")


def _download_hf(ctx: JobContext, meta: dict, dest: Path) -> None:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as e:
        raise ModelError("huggingface_hub is not installed (pip install faster-whisper).") from e
    ctx.message("Downloading from Hugging Face (progress is not reported by this source)")
    snapshot_download(meta["hf_repo"], local_dir=str(dest))
    ctx.progress(1.0, "Installed")


def verify(model_id: str) -> dict:
    """Load the model and run a tiny inference — proves the files are complete and usable."""
    meta = BY_ID.get(model_id)
    p = installed_path(model_id)
    if not meta or not p:
        raise ModelError("Model is not installed.")
    import numpy as np

    silence = np.zeros(16000, dtype=np.float32)
    try:
        if meta["purpose"] == "asr":
            from .asr import load_asr

            load_asr(meta, p).transcribe_chunk(silence)
        elif meta["purpose"] == "audio_tagging":
            from ..audio.tagger import Tagger

            Tagger(meta, p).tag(silence)
        elif meta["purpose"] == "vad":
            from ..audio.vad import silero_segments

            silero_segments(silence, p)
        elif meta["purpose"] == "face":
            from ..analysis.visual import FaceDetector

            FaceDetector(p).detect(np.zeros((180, 320, 3), dtype=np.uint8))
    except Exception as e:  # noqa: BLE001
        _set(model_id, status="error", error=f"Verification failed: {e}")
        log.warning("model %s failed verification: %s", model_id, e)
        raise ModelError(f"Verification failed: {e}") from e
    _set(model_id, verified_at=now(), error=None)
    return {"ok": True}


def remove(model_id: str) -> None:
    d = model_dir(model_id)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    _set(model_id, status="not_installed", path=None, bytes_done=0, verified_at=None, error=None)
    for key in SETTING_FOR_PURPOSE.values():
        if settings.get(key) == model_id:
            settings.update({key: ""})


def select(model_id: str) -> None:
    meta = BY_ID.get(model_id)
    if not meta or not installed_path(model_id):
        raise ModelError("Install the model before selecting it.")
    key = SETTING_FOR_PURPOSE.get(meta["purpose"])
    if key:
        settings.update({key: model_id})
        if meta["purpose"] == "asr":
            settings.update({"asr_provider": meta["provider"]})


manager.register("model_download", download_job, heavy=False, stages=[("download", 1.0)])
