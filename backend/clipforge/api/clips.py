"""Clip routes: review, editor state, captions, crop preview, export."""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from ..captions import engine as cap
from ..config import AUDIO_EXTENSIONS, paths
from ..db import session
from ..export import job as export_job
from ..export import render
from ..media import ffmpeg as ff
from ..models import (CaptionTrack, ClipCandidate, ExportJob, GeneratedClip, SourceVideo, Transcript,
                      TranscriptSegment)

router = APIRouter(prefix="/api")

CROP_MODES = {"smart", "face", "center", "manual", "original", "fit_blur"}
ASPECTS = {"9:16", "16:9", "1:1", "original"}


def _clip(s, clip_id: str) -> GeneratedClip:
    c = s.get(GeneratedClip, clip_id)
    if not c:
        raise HTTPException(404, "Clip not found")
    return c


class CandidateIn(BaseModel):
    status: str | None = None
    title: str | None = None


@router.patch("/candidates/{cid}")
def update_candidate(cid: str, body: CandidateIn):
    with session() as s:
        c = s.get(ClipCandidate, cid)
        if not c:
            raise HTTPException(404, "Suggestion not found")
        if body.status:
            if body.status not in ("suggested", "accepted", "rejected"):
                raise HTTPException(400, "Invalid status")
            c.status = body.status
        if body.title is not None and body.title.strip():
            c.title = body.title.strip()[:300]
            clip = s.query(GeneratedClip).filter_by(candidate_id=cid).first()
            if clip:
                clip.title = c.title
        return c.to_dict()


@router.get("/clips/{clip_id}")
def get_clip(clip_id: str):
    with session() as s:
        c = _clip(s, clip_id)
        track = s.query(CaptionTrack).filter_by(clip_id=clip_id).first()
        cand = s.get(ClipCandidate, c.candidate_id) if c.candidate_id else None
        src = s.query(SourceVideo).filter_by(project_id=c.project_id).first()
        tr = s.query(Transcript).filter_by(project_id=c.project_id).first()
        exports = s.query(ExportJob).filter_by(clip_id=clip_id).order_by(ExportJob.created_at.desc()).all()
        return {
            "clip": {**c.to_dict(), "style": cap.normalize_style(c.style),
                     "export_settings": render.export_settings(c.export_settings)},
            "captions": track.to_dict() if track else {"cues": [], "word_timing": "estimated"},
            "candidate": cand.to_dict() if cand else None,
            "source": src.to_dict(),
            "transcript": tr.to_dict() if tr else None,
            "exports": [{**e.to_dict(), "exists": bool(e.path and Path(e.path).is_file())} for e in exports],
        }


@router.patch("/clips/{clip_id}")
def update_clip(clip_id: str, body: dict):
    """Save editor changes. Everything saved here is what the renderer uses."""
    with session() as s:
        c = _clip(s, clip_id)
        src = s.query(SourceVideo).filter_by(project_id=c.project_id).first()
        start = float(body.get("start", c.start))
        end = float(body.get("end", c.end))
        start, end = max(0.0, start), min(src.duration, end)
        if end - start < 0.5:
            raise HTTPException(400, "A clip must be at least half a second long.")
        c.start, c.end = round(start, 3), round(end, 3)
        if "title" in body and str(body["title"]).strip():
            c.title = str(body["title"]).strip()[:300]
        if "aspect" in body:
            if body["aspect"] not in ASPECTS:
                raise HTTPException(400, "Unsupported aspect ratio")
            c.aspect = body["aspect"]
        if "crop_mode" in body:
            if body["crop_mode"] not in CROP_MODES:
                raise HTTPException(400, "Unsupported crop mode")
            c.crop_mode = body["crop_mode"]
        if "crop" in body:
            cr = body["crop"] or {}
            c.crop = {"x": min(1.0, max(0.0, float(cr.get("x", 0.5)))), "y": min(1.0, max(0.0, float(cr.get("y", 0.5)))),
                      "zoom": min(4.0, max(1.0, float(cr.get("zoom", 1.0))))}
        if "volume" in body:
            c.volume = min(4.0, max(0.0, float(body["volume"])))
        if "music_volume" in body:
            c.music_volume = min(2.0, max(0.0, float(body["music_volume"])))
        if "mute" in body:
            c.mute = bool(body["mute"])
        if "captions_enabled" in body:
            c.captions_enabled = bool(body["captions_enabled"])
        if "style" in body:
            c.style = cap.normalize_style(body["style"])
        if "export_settings" in body:
            c.export_settings = {k: v for k, v in (body["export_settings"] or {}).items()
                                 if k in render.DEFAULT_EXPORT}
        if c.candidate_id:
            cand = s.get(ClipCandidate, c.candidate_id)
            if cand and cand.status == "suggested":
                cand.status = "accepted"  # an edited suggestion is kept across re-analysis
        s.flush()
        return {**c.to_dict(), "style": cap.normalize_style(c.style)}


@router.delete("/clips/{clip_id}")
def delete_clip(clip_id: str):
    with session() as s:
        c = _clip(s, clip_id)
        s.query(CaptionTrack).filter_by(clip_id=clip_id).delete()
        s.query(ExportJob).filter_by(clip_id=clip_id).delete()
        if c.candidate_id:
            cand = s.get(ClipCandidate, c.candidate_id)
            if cand:
                s.delete(cand)
        s.delete(c)
    return {"ok": True}


class CuesIn(BaseModel):
    cues: list[dict]


@router.put("/clips/{clip_id}/captions")
def save_captions(clip_id: str, body: CuesIn):
    """Save edited cues (text and timing). Word timings are rebuilt where the text changed."""
    cleaned = []
    for c in body.cues:
        try:
            start, end, text = float(c["start"]), float(c["end"]), str(c["text"]).strip()
        except (KeyError, TypeError, ValueError) as e:
            raise HTTPException(400, "Each caption needs start, end and text.") from e
        if not text:
            continue
        if end <= start:
            raise HTTPException(400, f"Caption “{text[:30]}” ends before it starts.")
        cleaned.append(cap.retime_words({"id": c.get("id") or "", "start": round(start, 3), "end": round(end, 3),
                                         "text": text, "speaker": str(c.get("speaker") or "")[:40],
                                         "words": c.get("words") or []}))
    cleaned.sort(key=lambda c: c["start"])
    import uuid

    for c in cleaned:
        c["id"] = c["id"] or uuid.uuid4().hex[:8]
    with session() as s:
        _clip(s, clip_id)
        track = s.query(CaptionTrack).filter_by(clip_id=clip_id).first()
        if not track:
            track = CaptionTrack(clip_id=clip_id)
            s.add(track)
        track.cues, track.edited = cleaned, True
        s.flush()
        return track.to_dict()


class RebuildIn(BaseModel):
    max_words: int = 6
    from_transcript: bool = False


@router.post("/clips/{clip_id}/captions/rebuild")
def rebuild_captions(clip_id: str, body: RebuildIn):
    """Re-flow captions to a new words-per-line value; optionally reset them from the transcript."""
    n = max(1, min(body.max_words, 14))
    with session() as s:
        c = _clip(s, clip_id)
        track = s.query(CaptionTrack).filter_by(clip_id=clip_id).first()
        if not track:
            track = CaptionTrack(clip_id=clip_id)
            s.add(track)
        if body.from_transcript or not track.cues:
            segs = [x.to_dict() for x in s.query(TranscriptSegment).filter_by(project_id=c.project_id)
                    .order_by(TranscriptSegment.idx).all()]
            track.cues, track.edited = cap.build_cues(segs, c.start, c.end, n), False
        else:
            track.cues = cap.regroup(track.cues, n)
        s.flush()
        return track.to_dict()


@router.post("/clips/{clip_id}/style/apply-all")
def apply_style_all(clip_id: str):
    """Copy this clip's caption style to every clip in the project."""
    with session() as s:
        c = _clip(s, clip_id)
        style = cap.normalize_style(c.style)
        n = 0
        for other in s.query(GeneratedClip).filter_by(project_id=c.project_id).all():
            other.style = style
            n += 1
        return {"updated": n}


@router.get("/clips/{clip_id}/crop-plan")
def crop_plan(clip_id: str, mode: str | None = None, aspect: str | None = None, start: float | None = None,
              end: float | None = None, x: float | None = None, y: float | None = None, zoom: float | None = None):
    """The exact crop path the renderer will use, for live preview in the editor."""
    with session() as s:
        c = _clip(s, clip_id)
        clip = c.to_dict()
        src = s.query(SourceVideo).filter_by(project_id=c.project_id).first().to_dict()
    o: dict = {}
    if mode:
        o["crop_mode"] = mode
    if aspect:
        o["aspect"] = aspect
    if start is not None:
        o["start"] = start
    if end is not None:
        o["end"] = end
    if x is not None or y is not None or zoom is not None:
        base = clip.get("crop") or {}
        o["crop"] = {"x": x if x is not None else base.get("x", 0.5), "y": y if y is not None else base.get("y", 0.5),
                     "zoom": zoom if zoom is not None else base.get("zoom", 1.0)}
    return export_job.crop_plan_for(clip, src, o)


def _subs(clip_id: str, fmt: str) -> PlainTextResponse:
    with session() as s:
        c = _clip(s, clip_id)
        track = s.query(CaptionTrack).filter_by(clip_id=clip_id).first()
        cues = cap.clip_cues(track.cues if track else [], c.start, c.end)
        labels = bool(cap.normalize_style(c.style).get("speaker_labels"))
        name = render.safe_name(c.title)
    text = cap.to_srt(cues, labels) if fmt == "srt" else cap.to_vtt(cues, labels)
    return PlainTextResponse(text, media_type="text/vtt" if fmt == "vtt" else "application/x-subrip",
                             headers={"Content-Disposition": f'attachment; filename="{name}.{fmt}"'})


@router.get("/clips/{clip_id}/subtitles.srt")
def srt(clip_id: str):
    return _subs(clip_id, "srt")


@router.get("/clips/{clip_id}/subtitles.vtt")
def vtt(clip_id: str):
    return _subs(clip_id, "vtt")


@router.post("/clips/{clip_id}/music")
def upload_music(clip_id: str, file: UploadFile = File(...)):
    name = Path(file.filename or "music").name
    ext = Path(name).suffix.lower()
    if ext not in AUDIO_EXTENSIONS:
        raise HTTPException(400, "Choose an audio file (MP3, WAV, M4A, AAC, OGG or FLAC).")
    with session() as s:
        c = _clip(s, clip_id)
        pid = c.project_id
    dest = paths.project(pid) / "music" / f"{clip_id}{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".upload")  # validate first so a bad upload never replaces good music
    with open(tmp, "wb") as out:
        shutil.copyfileobj(file.file, out)
    import subprocess

    r = subprocess.run([ff.ffprobe_bin(), "-v", "error", "-select_streams", "a:0", "-show_entries",
                        "stream=codec_name", "-of", "csv=p=0", str(tmp)], capture_output=True, text=True,
                       timeout=30, creationflags=ff.NO_WINDOW)
    if r.returncode != 0 or not r.stdout.strip():
        tmp.unlink(missing_ok=True)
        raise HTTPException(400, "That file does not contain readable audio.")
    for old in dest.parent.glob(f"{clip_id}.*"):
        if old != tmp:
            old.unlink(missing_ok=True)
    tmp.replace(dest)
    with session() as s:
        c = _clip(s, clip_id)
        c.music_path = str(dest)
    return {"music_path": str(dest), "name": name}


@router.delete("/clips/{clip_id}/music")
def remove_music(clip_id: str):
    with session() as s:
        c = _clip(s, clip_id)
        if c.music_path and Path(c.music_path).is_relative_to(paths.root):
            Path(c.music_path).unlink(missing_ok=True)
        c.music_path = None
    return {"ok": True}


class ExportIn(BaseModel):
    settings: dict = {}


@router.post("/clips/{clip_id}/export")
def export(clip_id: str, body: ExportIn):
    return export_job.submit_export(clip_id, body.settings)


@router.get("/projects/{pid}/exports")
def exports(pid: str):
    with session() as s:
        rows = s.query(ExportJob).filter_by(project_id=pid).order_by(ExportJob.created_at.desc()).all()
        out = []
        for e in rows:
            clip = s.get(GeneratedClip, e.clip_id)
            out.append({**e.to_dict(), "title": clip.title if clip else "",
                        "exists": bool(e.path and Path(e.path).is_file())})
        return out
