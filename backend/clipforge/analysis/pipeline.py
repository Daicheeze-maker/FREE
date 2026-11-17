"""The analysis job: stages 1-8. (Stages 9-10, rendering and validation, run in export jobs.)

Each stage stores its results (database rows or files in the project folder) and is
recorded as completed, so an interrupted or failed job can be retried without redoing
finished stages.
"""
from __future__ import annotations

import gc
import json
import shutil
from pathlib import Path

import numpy as np

from .. import settings
from ..ai import model_manager
from ..ai.asr import load_asr
from ..ai.llm import get_client
from ..audio import features, tagger as tg
from ..audio.io import Wav, extract_wav
from ..audio.vad import speech_segments
from ..captions import engine as cap
from ..config import paths
from ..db import session
from ..errors import ClipForgeError, MediaError, ModelError
from ..jobs.manager import JobContext, manager
from ..logging_setup import log
from ..media import ffmpeg as ff
from ..models import (CaptionTrack, ClipCandidate, DetectedEvent, ExportJob, GeneratedClip, Job, Project, Scene,
                      SourceVideo, Transcript, TranscriptSegment)
from . import clips as clip_engine
from . import context as ctx_ai
from . import visual
from .speech_events import speech_events

STAGES = [("ingestion", 0.02), ("audio_extraction", 0.06), ("transcription", 0.34), ("visual_analysis", 0.30),
          ("event_detection", 0.14), ("context_analysis", 0.08), ("clip_generation", 0.04), ("captions", 0.02)]
STAGE_LABELS = {
    "ingestion": "Ingestion", "audio_extraction": "Audio extraction", "transcription": "Transcription",
    "visual_analysis": "Visual analysis", "event_detection": "Event detection",
    "context_analysis": "Context analysis", "clip_generation": "Clip generation", "captions": "Captions",
}

DEFAULT_ANALYSIS = {
    "categories": [c for c in clip_engine.CATEGORIES if c != "custom"],
    "min_len": 15, "max_len": 60, "count": 10, "aspect": "9:16",
    "language": "auto",  # auto|en|tl|any whisper language code
    "caption_preset": "dynamic", "profile": "", "normalize_audio": False, "use_llm": True,
}


def analysis_params(p: dict | None) -> dict:
    out = dict(DEFAULT_ANALYSIS)
    out.update({k: v for k, v in (p or {}).items() if k in DEFAULT_ANALYSIS})
    out["min_len"] = float(max(3, min(out["min_len"], 600)))
    out["max_len"] = float(max(out["min_len"] + 1, min(out["max_len"], 900)))
    out["count"] = int(max(1, min(out["count"], 50)))
    if not out["profile"]:
        out["profile"] = settings.get("performance_profile") or "balanced"
    return out


def _events_from_db(project_id: str) -> list[dict]:
    with session() as s:
        return [e.to_dict() for e in s.query(DetectedEvent).filter_by(project_id=project_id)
                .order_by(DetectedEvent.start).all()]


def _segments_from_db(project_id: str) -> list[dict]:
    with session() as s:
        return [x.to_dict() for x in s.query(TranscriptSegment).filter_by(project_id=project_id)
                .order_by(TranscriptSegment.idx).all()]


def _scenes_from_db(project_id: str) -> list[tuple[float, float]]:
    with session() as s:
        return [(x.start, x.end) for x in s.query(Scene).filter_by(project_id=project_id).order_by(Scene.idx).all()]


def _replace_events(project_id: str, modalities_or_kinds: dict, events: list[dict]) -> None:
    with session() as s:
        q = s.query(DetectedEvent).filter_by(project_id=project_id)
        if "modality" in modalities_or_kinds:
            q = q.filter(DetectedEvent.modality.in_(modalities_or_kinds["modality"]))
        if "kind" in modalities_or_kinds:
            q = q.filter(DetectedEvent.kind.in_(modalities_or_kinds["kind"]))
        if "not_kind" in modalities_or_kinds:
            q = q.filter(DetectedEvent.kind.notin_(modalities_or_kinds["not_kind"]))
        q.delete(synchronize_session=False)
        for e in events:
            s.add(DetectedEvent(project_id=project_id, kind=e["kind"], modality=e["modality"],
                                start=float(e["start"]), end=float(e["end"]), intensity=float(e["intensity"]),
                                confidence=float(e["confidence"]), label=e.get("label"), data=e.get("data") or {}))


def run_analysis(ctx: JobContext) -> dict:
    project_id = ctx.params["project_id"]
    params = analysis_params(ctx.params.get("settings"))
    profile = settings.PROFILES.get(params["profile"], settings.PROFILES["balanced"])
    with session() as s:
        project = s.get(Project, project_id)
        src_row = s.query(SourceVideo).filter_by(project_id=project_id).first()
        if not project or not src_row:
            raise ClipForgeError("The project no longer exists.")
        project.status, project.settings, project.notice = "analyzing", params, None
        src = src_row.to_dict()
        done = set(s.get(Job, ctx.job_id).completed_stages or [])
    pdir = paths.project(project_id)
    wav_path, rms_path = pdir / "audio.wav", pdir / "rms.npy"
    speech_path, track_path = pdir / "speech.json", pdir / "track.json"
    warnings: list[str] = []

    def skip(stage: str, *files: Path) -> bool:
        if stage in done and all(f.exists() for f in files):
            ctx.skip_stage(stage)
            return True
        return False

    try:
        # ---- 1. ingestion ---------------------------------------------------
        ctx.start_stage("ingestion", "Validating the source video")
        if not Path(src["path"]).is_file():
            raise MediaError("The source video file is missing. It may have been moved or deleted.")
        info = ff.probe(src["path"])
        free = shutil.disk_usage(paths.root).free
        need = int(info.duration * 16000 * 2 * 1.2) + 200 * 2**20
        if free < need:
            raise MediaError(f"Not enough disk space for analysis ({free / 2**30:.1f} GB free).")
        ctx.progress(1.0)
        ctx.finish_stage()

        # ---- 2. audio extraction + preparation ------------------------------
        has_audio = info.has_audio
        if not skip("audio_extraction", rms_path, speech_path):
            ctx.start_stage("audio_extraction", "Extracting audio")
            if has_audio:
                extract_wav(src["path"], wav_path, info.duration, check=ctx.check, normalize=params["normalize_audio"],
                            on_progress=lambda f: ctx.progress(f * 0.6, "Extracting audio"))
                wav = Wav(wav_path)
                rms = features.loudness_curve(wav, lambda f: ctx.progress(0.6 + f * 0.15, "Measuring loudness"))
                vad_model = model_manager.installed_path("silero-vad")
                speech, vad_kind = speech_segments(wav, rms, features.HOP, vad_model,
                                                   lambda f: ctx.progress(0.75 + f * 0.25, "Finding speech"))
                wav.close()
                if vad_kind == "energy":
                    warnings.append("Silero VAD is not installed: speech was split by loudness, "
                                    "which is less precise in noisy audio.")
            else:
                rms, speech = np.zeros(0, np.float32), []
                warnings.append("This video has no audio track: only visual analysis was performed.")
            np.save(rms_path, rms)
            speech_path.write_text(json.dumps(speech))
            (pdir / "peaks.json").write_text(json.dumps(features.waveform_peaks(rms)))
            ctx.progress(1.0)
            ctx.finish_stage()
        rms = np.load(rms_path)
        speech = [tuple(x) for x in json.loads(speech_path.read_text())]

        # ---- 3. transcription ----------------------------------------------
        if "transcription" in done:
            ctx.skip_stage("transcription")
        else:
            ctx.start_stage("transcription", "Loading the speech model")
            segments_out, language, timing, provider, model_id = [], None, "estimated", "none", "none"
            if has_audio and speech:
                active = model_manager.active("asr")
                if not active:
                    raise ModelError("No speech recognition model is installed. "
                                     "Download one in Settings > AI models, then retry.")
                meta, mpath = active
                asr = load_asr(meta, mpath)
                wav = Wav(wav_path)
                lang = None if params["language"] in ("", "auto") else params["language"]
                res = asr.transcribe(wav, speech, lang, lambda f, text: ctx.progress(f, text or None))
                wav.close()
                segments_out, language, timing = res.segments, res.language, res.word_timing
                provider, model_id = res.provider, res.model
                del asr
                gc.collect()  # free the speech model before the next model loads
            with session() as s:
                s.query(TranscriptSegment).filter_by(project_id=project_id).delete()
                s.query(Transcript).filter_by(project_id=project_id).delete()
                s.add(Transcript(project_id=project_id, language=language, provider=provider, model=model_id,
                                 word_timing=timing))
                for i, seg in enumerate(segments_out):
                    s.add(TranscriptSegment(project_id=project_id, idx=i, start=seg.start, end=seg.end,
                                            text=seg.text, language=seg.language, words=seg.words))
            ctx.progress(1.0, f"{len(segments_out)} sentences transcribed")
            ctx.finish_stage()
        segments = _segments_from_db(project_id)

        # ---- 4. visual analysis --------------------------------------------
        if not skip("visual_analysis", track_path):
            ctx.start_stage("visual_analysis", "Detecting scene changes")
            scenes = visual.detect_scenes(src["path"], info.duration, profile["scene_downscale"],
                                          lambda f: ctx.progress(f * 0.45, "Detecting scene changes"), ctx.check)
            face_path = model_manager.active("face")
            detector = visual.FaceDetector(face_path[1]) if face_path else None
            if detector is None:
                warnings.append("The face detector is not installed: face tracking and face-based signals are off.")
            track = visual.sample_frames(src["path"], info.width, info.height, info.duration, profile["sample_fps"],
                                         detector, lambda f: ctx.progress(0.45 + f * 0.55, "Inspecting frames"),
                                         ctx.check)
            track_path.write_text(json.dumps({"fps": profile["sample_fps"], "samples": track}))
            with session() as s:
                s.query(Scene).filter_by(project_id=project_id).delete()
                for i, (a, b) in enumerate(scenes):
                    s.add(Scene(project_id=project_id, idx=i, start=a, end=b))
            ctx.progress(1.0, f"{len(scenes)} scenes, {len(track)} frames inspected")
            ctx.finish_stage()
        track_data = json.loads(track_path.read_text())
        track, track_fps = track_data["samples"], track_data["fps"]
        scenes = _scenes_from_db(project_id)

        # ---- 5. event detection --------------------------------------------
        has_tagger = True
        if "event_detection" in done:
            ctx.skip_stage("event_detection")
            has_tagger = model_manager.active("audio_tagging") is not None
        else:
            ctx.start_stage("event_detection", "Detecting audio events")
            events: list[dict] = []
            if has_audio and len(rms):
                events += features.energy_spikes(rms, speech)
                events += features.pauses(speech, info.duration, rms)
                events += features.vocal_energy_events(rms, speech)
                active = model_manager.active("audio_tagging")
                if active:
                    tagger = tg.Tagger(*active)
                    wav = Wav(wav_path)
                    win, hop = 2.0, profile["tag_hop"]
                    times = list(np.arange(0.0, max(0.01, wav.duration - 0.5), hop))
                    probs = []
                    for i, t in enumerate(times):
                        probs.append(tagger.tag(wav.read(t, t + win)))
                        if i % 5 == 0:
                            ctx.progress(0.8 * i / len(times), "Listening for laughter, reactions and sound effects")
                    wav.close()
                    events += tg.windows_to_events([float(t) for t in times], probs, win)
                    del tagger
                    gc.collect()
                else:
                    has_tagger = False
                    warnings.append("No audio tagging model is installed: laughter, screams and sound effects "
                                    "were not detected (loudness and speech signals were still used).")
            ctx.progress(0.85, "Detecting visual events")
            events += visual.visual_events(track, scenes, track_fps)
            events += speech_events(segments)
            _replace_events(project_id, {"not_kind": ["vlm_frame"]}, events)
            ctx.progress(1.0, f"{len(events)} events on the timeline")
            ctx.finish_stage()
        events = _events_from_db(project_id)

        # ---- 6. context analysis -------------------------------------------
        proposals: list[dict] = []
        ctx.start_stage("context_analysis", "Linking events with their context")
        client = None
        if params["use_llm"]:
            try:
                client = get_client()
            except ModelError as e:
                warnings.append(str(e))
        if client:
            try:
                if client.vision:
                    times = ctx_ai.pick_frame_times(events, scenes, profile["vlm_frames"])
                    frames = ctx_ai.describe_frames(client, src["path"], times,
                                                    lambda f, m: ctx.progress(f * 0.6, m))
                    _replace_events(project_id, {"kind": ["vlm_frame"]}, frames)
                    events = _events_from_db(project_id)
                if segments:
                    proposals = ctx_ai.propose_moments(client, segments, events,
                                                       lambda f, m: ctx.progress(0.6 + f * 0.4, m))
            except ModelError as e:
                log.warning("language model pass failed: %s", e)
                warnings.append(f"The local AI model could not be used ({e}). "
                                "Clips were selected from audio, visual and transcript signals only.")
        ctx.progress(1.0)
        ctx.finish_stage()

        # ---- 7. clip generation --------------------------------------------
        ctx.start_stage("clip_generation", "Scoring and ranking candidates")
        inp = clip_engine.Inputs(duration=info.duration, segments=segments, speech=speech, events=events,
                                 scenes=scenes, track=track, rms_db=rms, min_len=params["min_len"],
                                 max_len=params["max_len"], count=params["count"], categories=params["categories"],
                                 proposals=proposals, has_tagger=has_tagger)
        cands = clip_engine.generate(inp)
        cand_ids = store_candidates(project_id, src, cands, ctx)
        ctx.finish_stage()

        # ---- 8. captions ----------------------------------------------------
        ctx.start_stage("captions", "Building caption tracks")
        make_clips(project_id, cand_ids, params, segments)
        ctx.progress(1.0)
        ctx.finish_stage()

        notice = None
        if not cands:
            notice = "No interesting moments were found in this video. You can still create a clip manually."
        elif all(c["low_confidence"] for c in cands):
            notice = ("No strong moments were found. The suggestions below are the best available but have "
                      "little evidence behind them.")
        with session() as s:
            p = s.get(Project, project_id)
            p.status, p.notice = "analyzed", notice
        if not settings.get("keep_temp_files"):
            wav_path.unlink(missing_ok=True)  # the WAV is large and can be re-extracted
        return {"candidates": len(cands), "warnings": warnings, "notice": notice}
    except Exception:
        with session() as s:
            p = s.get(Project, project_id)
            if p:
                has_results = s.query(ClipCandidate).filter_by(project_id=project_id).count() > 0
                p.status = "analyzed" if has_results else "imported"
        raise


def store_candidates(project_id: str, src: dict, cands: list[dict], ctx: JobContext | None = None,
                     replace: bool = True) -> list[str]:
    """Persist candidates with real thumbnails. Suggestions the user kept or exported are preserved."""
    pdir = paths.project(project_id)
    ids = []
    with session() as s:
        if replace:
            for old in s.query(ClipCandidate).filter_by(project_id=project_id).all():
                clip = s.query(GeneratedClip).filter_by(candidate_id=old.id).first()
                exported = clip and s.query(ExportJob).filter_by(clip_id=clip.id).count() > 0
                if old.status == "accepted" or exported:
                    continue
                if clip:
                    s.delete(clip)
                s.delete(old)
    for i, c in enumerate(cands):
        with session() as s:
            row = ClipCandidate(project_id=project_id, rank=c["rank"], title=c["title"], start=c["start"],
                                end=c["end"], category=c["category"], score=c["score"], confidence=c["confidence"],
                                reason=c["reason"], scores=c["scores"], transcript_text=c["transcript_text"],
                                source=c["source"], low_confidence=c["low_confidence"])
            s.add(row)
            s.flush()
            thumb = pdir / "thumbs" / f"{row.id}.jpg"
            if ff.extract_frame(src["path"], c["start"] + (c["end"] - c["start"]) * 0.35, thumb):
                row.thumb_path = str(thumb)
            ids.append(row.id)
        if ctx:
            ctx.progress((i + 1) / len(cands), f"Prepared {i + 1} of {len(cands)} candidates")
    return ids


def make_clips(project_id: str, cand_ids: list[str], params: dict, segments: list[dict]) -> None:
    """Create the editable clip + caption track for each candidate."""
    style = cap.normalize_style({"preset": params.get("caption_preset", "dynamic")})
    with session() as s:
        tr = s.query(Transcript).filter_by(project_id=project_id).first()
        for cid in cand_ids:
            cand = s.get(ClipCandidate, cid)
            if not cand or s.query(GeneratedClip).filter_by(candidate_id=cid).first():
                continue
            clip = GeneratedClip(project_id=project_id, candidate_id=cid, title=cand.title, start=cand.start,
                                 end=cand.end, aspect=params.get("aspect", "9:16"), crop_mode="smart",
                                 crop={"x": 0.5, "y": 0.5, "zoom": 1.0}, style=style)
            s.add(clip)
            s.flush()
            s.add(CaptionTrack(clip_id=clip.id, cues=cap.build_cues(segments, cand.start, cand.end, style["max_words"]),
                               language=tr.language if tr else None,
                               word_timing=tr.word_timing if tr else "estimated"))


def run_search(ctx: JobContext) -> dict:
    """Custom AI Search: find moments matching a free-text request."""
    project_id, query = ctx.params["project_id"], ctx.params["query"].strip()
    ctx.start_stage("search", "Searching")
    with session() as s:
        project = s.get(Project, project_id)
        src = s.query(SourceVideo).filter_by(project_id=project_id).first().to_dict()
        params = analysis_params(project.settings)
    pdir = paths.project(project_id)
    if not (pdir / "track.json").exists():
        raise ClipForgeError("Analyze the video before searching it.")
    segments, events, scenes = _segments_from_db(project_id), _events_from_db(project_id), _scenes_from_db(project_id)
    track = json.loads((pdir / "track.json").read_text())["samples"]
    rms = np.load(pdir / "rms.npy")
    speech = [tuple(x) for x in json.loads((pdir / "speech.json").read_text())]
    method = "text"
    proposals: list[dict] = []
    client = get_client() if params["use_llm"] else None
    if client and segments:
        proposals = ctx_ai.search_moments(client, query, segments, events)
        method = "llm"
    else:
        from .speech_events import text_match

        for seg in segments:
            m = text_match(query, seg["text"])
            if m >= 0.5:
                proposals.append({"start": seg["start"], "end": seg["end"], "category": "custom", "title": "",
                                  "reason": f"Transcript matches “{query}” ({m:.0%} of the words). "
                                            "No language model is configured, so this is a text match only.",
                                  "interest": 0.35 + 0.4 * m, "complete": True})
        for e in events:
            if e["kind"] == "vlm_frame" and text_match(query, e.get("label") or "") >= 0.5:
                proposals.append({"start": e["start"], "end": e["end"], "category": "custom", "title": "",
                                  "reason": f"A frame description matches “{query}”.", "interest": 0.6,
                                  "complete": True})
    ctx.progress(0.7)
    inp = clip_engine.Inputs(duration=src["duration"], segments=segments, speech=speech, events=events,
                             scenes=scenes, track=track, rms_db=rms, min_len=params["min_len"],
                             max_len=params["max_len"], count=10, categories=["custom"], proposals=proposals)
    found = []
    for p in proposals:
        a, b = clip_engine._window_for(inp, p["start"], p["end"])
        c = clip_engine.score_window(inp, a, b, p)
        found.append({"rank": 0, "start": a, "end": b, "category": "custom", "score": c["score"],
                      "confidence": c["confidence"], "scores": c["scores"],
                      "reason": p["reason"] or clip_engine._reason(c),
                      "title": p["title"] or clip_engine._title({**c, "category": "custom"}),
                      "transcript_text": " ".join(x["text"] for x in c["segments"]),
                      "source": "search", "low_confidence": method == "text"})
    found.sort(key=lambda c: -c["score"])
    kept: list[dict] = []
    for c in found:
        if not any(clip_engine._iou(c, k)[0] > 0.4 for k in kept):
            kept.append(c)
    kept = kept[:8]
    for i, c in enumerate(kept, 1):
        c["rank"] = 1000 + i
    ids = store_candidates(project_id, src, kept, replace=False)
    make_clips(project_id, ids, params, segments)
    return {"found": len(kept), "method": method}


manager.register("analysis", run_analysis, heavy=True, stages=STAGES)
manager.register("search", run_search, heavy=True, stages=[("search", 1.0)])
