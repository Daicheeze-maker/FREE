"""Project routes: import, library, analysis, results."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..analysis import pipeline
from ..captions import engine as cap
from ..config import paths
from ..db import session
from ..errors import ClipForgeError
from ..importing import local, youtube
from ..jobs.manager import manager
from ..models import (CaptionTrack, ClipCandidate, DetectedEvent, ExportJob, GeneratedClip, Job, Project, Scene,
                      SourceVideo, Transcript, TranscriptSegment, new_id)

router = APIRouter(prefix="/api")


def _summary(s, p: Project) -> dict:
    src = s.query(SourceVideo).filter_by(project_id=p.id).first()
    job = (s.query(Job).filter(Job.project_id == p.id, Job.type.in_(["analysis", "proxy"]),
                               Job.status.in_(["queued", "running", "paused"])).order_by(Job.created_at.desc()).first())
    return {**p.to_dict(), "source": src.to_dict() if src else None,
            "clip_count": s.query(ClipCandidate).filter(ClipCandidate.project_id == p.id,
                                                        ClipCandidate.status != "rejected").count(),
            "export_count": s.query(ExportJob).filter_by(project_id=p.id, status="completed").count(),
            "active_job": job.to_dict() if job else None,
            "source_missing": bool(src and not Path(src.path).is_file())}


@router.get("/projects")
def list_projects(q: str = "", status: str = ""):
    with session() as s:
        query = s.query(Project)
        if q:
            query = query.filter(Project.name.ilike(f"%{q}%"))
        if status:
            query = query.filter(Project.status == status)
        return [_summary(s, p) for p in query.order_by(Project.updated_at.desc()).all()]


def _import_response(fn):
    try:
        return fn()
    except local.DuplicateImport as e:
        raise HTTPException(409, detail={"message": str(e), "project_id": e.project_id}) from e


class PathIn(BaseModel):
    path: str
    name: str | None = None


@router.post("/import/path")
def import_path(body: PathIn):
    """Reference a video where it is on this computer (no copy is made)."""
    return _import_response(lambda: local.create_project(body.path.strip().strip('"'), name=body.name))


@router.post("/import/upload")
def import_upload(file: UploadFile = File(...), name: str | None = Form(None)):
    """Browser / phone upload: the file is stored inside the app's data folder."""
    filename = Path(file.filename or "video").name  # drop any client-supplied directories
    local.validate_extension(filename)
    project_id = new_id()
    pdir = paths.project(project_id)
    dest = pdir / ("source" + Path(filename).suffix.lower())
    free = shutil.disk_usage(paths.root).free
    try:
        with open(dest, "wb") as out:
            while chunk := file.file.read(1 << 20):
                free -= len(chunk)
                if free < 500 * 2**20:
                    raise ClipForgeError("Not enough disk space to store this upload.")
                out.write(chunk)
        return _import_response(lambda: local.create_project(
            dest, origin="upload", managed=True, name=name or Path(filename).stem, project_id=project_id))
    except Exception:
        shutil.rmtree(pdir, ignore_errors=True)
        raise


class UrlIn(BaseModel):
    url: str
    authorized: bool = False


@router.post("/import/youtube/info")
def youtube_info(body: UrlIn):
    return youtube.info(body.url)


@router.post("/import/youtube")
def youtube_import(body: UrlIn):
    if not body.authorized:
        raise HTTPException(400, "Confirm that you own this video or have permission to download and edit it.")
    url = youtube.validate_url(body.url)
    return {"job_id": manager.submit("youtube", {"url": url})}


@router.get("/projects/{pid}")
def get_project(pid: str):
    with session() as s:
        p = s.get(Project, pid)
        if not p:
            raise HTTPException(404, "Project not found")
        out = _summary(s, p)
        tr = s.query(Transcript).filter_by(project_id=pid).first()
        out["transcript"] = tr.to_dict() if tr else None
        last = (s.query(Job).filter_by(project_id=pid, type="analysis")
                .order_by(Job.created_at.desc(), Job.started_at.desc()).first())
        out["last_analysis"] = last.to_dict() if last else None
        out["counts"] = {"segments": s.query(TranscriptSegment).filter_by(project_id=pid).count(),
                         "scenes": s.query(Scene).filter_by(project_id=pid).count(),
                         "events": s.query(DetectedEvent).filter_by(project_id=pid).count()}
        return out


class RenameIn(BaseModel):
    name: str


@router.patch("/projects/{pid}")
def rename_project(pid: str, body: RenameIn):
    with session() as s:
        p = s.get(Project, pid)
        if not p:
            raise HTTPException(404, "Project not found")
        if not body.name.strip():
            raise HTTPException(400, "The name cannot be empty.")
        p.name = body.name.strip()[:300]
        return p.to_dict()


@router.delete("/projects/{pid}")
def delete_project(pid: str, delete_exports: bool = False):
    """Remove the project, its analysis data and app-managed media. Original local files are never touched."""
    with session() as s:
        p = s.get(Project, pid)
        if not p:
            raise HTTPException(404, "Project not found")
        for j in s.query(Job).filter(Job.project_id == pid, Job.status.in_(["queued", "running", "paused"])).all():
            manager.cancel(j.id)
        export_paths = [e.path for e in s.query(ExportJob).filter_by(project_id=pid).all() if e.path]
        clip_ids = [c.id for c in s.query(GeneratedClip).filter_by(project_id=pid).all()]
        if clip_ids:
            s.query(CaptionTrack).filter(CaptionTrack.clip_id.in_(clip_ids)).delete(synchronize_session=False)
        for model in (ExportJob, GeneratedClip, ClipCandidate, DetectedEvent, Scene, TranscriptSegment, Transcript,
                      SourceVideo, Job):
            s.query(model).filter_by(project_id=pid).delete(synchronize_session=False)
        s.delete(p)
    shutil.rmtree(paths.projects / pid, ignore_errors=True)
    if delete_exports:
        for e in export_paths:
            for f in (Path(e), Path(e).with_suffix(".srt"), Path(e).with_suffix(".vtt")):
                f.unlink(missing_ok=True)
    return {"ok": True}


class AnalyzeIn(BaseModel):
    settings: dict = {}


@router.post("/projects/{pid}/analyze")
def analyze(pid: str, body: AnalyzeIn):
    with session() as s:
        if not s.get(Project, pid):
            raise HTTPException(404, "Project not found")
        running = s.query(Job).filter(Job.project_id == pid, Job.type == "analysis",
                                      Job.status.in_(["queued", "running", "paused"])).first()
        if running:
            return {"job_id": running.id, "already_running": True}
    params = pipeline.analysis_params(body.settings)
    return {"job_id": manager.submit("analysis", {"project_id": pid, "settings": params}, project_id=pid)}


@router.get("/projects/{pid}/transcript")
def transcript(pid: str):
    with session() as s:
        tr = s.query(Transcript).filter_by(project_id=pid).first()
        segs = s.query(TranscriptSegment).filter_by(project_id=pid).order_by(TranscriptSegment.idx).all()
        return {"info": tr.to_dict() if tr else None,
                "segments": [{"idx": x.idx, "start": x.start, "end": x.end, "text": x.text} for x in segs]}


@router.get("/projects/{pid}/timeline")
def timeline(pid: str):
    """Events, scenes and the waveform envelope for the timeline views."""
    with session() as s:
        events = [e.to_dict() for e in s.query(DetectedEvent).filter_by(project_id=pid)
                  .order_by(DetectedEvent.start).all()]
        scenes = [{"start": x.start, "end": x.end} for x in s.query(Scene).filter_by(project_id=pid)
                  .order_by(Scene.idx).all()]
    f = paths.projects / pid / "peaks.json"
    return {"events": events, "scenes": scenes, "peaks": json.loads(f.read_text()) if f.exists() else []}


def _cand_out(s, c: ClipCandidate) -> dict:
    clip = s.query(GeneratedClip).filter_by(candidate_id=c.id).first()
    d = c.to_dict()
    d["duration"] = round(c.end - c.start, 2)
    d["clip_id"] = clip.id if clip else None
    if clip:  # show the user's edits, not the stale suggestion
        d.update({"title": clip.title, "start": clip.start, "end": clip.end,
                  "duration": round(clip.end - clip.start, 2), "aspect": clip.aspect})
    d["exports"] = s.query(ExportJob).filter_by(clip_id=clip.id, status="completed").count() if clip else 0
    return d


@router.get("/projects/{pid}/candidates")
def candidates(pid: str):
    with session() as s:
        rows = s.query(ClipCandidate).filter_by(project_id=pid).order_by(ClipCandidate.score.desc()).all()
        return [_cand_out(s, c) for c in rows]


class SearchIn(BaseModel):
    query: str


@router.post("/projects/{pid}/search")
def search(pid: str, body: SearchIn):
    if len(body.query.strip()) < 2:
        raise HTTPException(400, "Describe what you are looking for.")
    return {"job_id": manager.submit("search", {"project_id": pid, "query": body.query}, project_id=pid)}


class ManualClipIn(BaseModel):
    start: float
    end: float
    title: str = "Manual clip"


@router.post("/projects/{pid}/clips")
def manual_clip(pid: str, body: ManualClipIn):
    with session() as s:
        p, src = s.get(Project, pid), s.query(SourceVideo).filter_by(project_id=pid).first()
        if not p or not src:
            raise HTTPException(404, "Project not found")
        start, end = max(0.0, body.start), min(src.duration, body.end)
        if end - start < 0.5:
            raise HTTPException(400, "A clip must be at least half a second long.")
        src_d, params = src.to_dict(), pipeline.analysis_params(p.settings)
        segs = [x.to_dict() for x in s.query(TranscriptSegment).filter_by(project_id=pid)
                .order_by(TranscriptSegment.idx).all()]
    text = " ".join(x["text"] for x in segs if x["end"] > start and x["start"] < end)
    cand = {"rank": 2000, "start": start, "end": end, "category": "custom", "score": 0.0, "confidence": 0.0,
            "scores": {}, "reason": "Created manually.", "title": body.title[:200], "transcript_text": text,
            "source": "manual", "low_confidence": False}
    ids = pipeline.store_candidates(pid, src_d, [cand], replace=False)
    pipeline.make_clips(pid, ids, params, segs)
    with session() as s:
        c = s.get(ClipCandidate, ids[0])
        c.status = "accepted"
        return _cand_out(s, c)


@router.get("/clips/recent")
def recent_clips(limit: int = 12):
    with session() as s:
        rows = (s.query(ExportJob).filter_by(status="completed").order_by(ExportJob.created_at.desc())
                .limit(limit).all())
        out = []
        for e in rows:
            clip = s.get(GeneratedClip, e.clip_id)
            out.append({**e.to_dict(), "title": clip.title if clip else "", "candidate_id": clip.candidate_id if clip else None,
                        "exists": bool(e.path and Path(e.path).is_file())})
        return out


@router.get("/caption-presets")
def presets():
    return cap.PRESETS
