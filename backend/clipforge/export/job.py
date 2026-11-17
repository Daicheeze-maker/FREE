"""Export job: stage 9 (render) and stage 10 (quality validation)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .. import settings
from ..captions import engine as cap
from ..config import paths
from ..db import session
from ..errors import ClipForgeError, MediaError
from ..jobs.manager import JobContext, manager
from ..media import ffmpeg as ff
from ..models import CaptionTrack, ExportJob, GeneratedClip, Scene, SourceVideo
from . import reframe, render


def load_track(project_id: str) -> list[dict]:
    f = paths.project(project_id) / "track.json"
    return json.loads(f.read_text())["samples"] if f.exists() else []


def crop_plan_for(clip: dict, source: dict, overrides: dict | None = None) -> dict:
    o = overrides or {}
    with session() as s:
        scenes = [(x.start, x.end) for x in s.query(Scene).filter_by(project_id=clip["project_id"]).all()]
    return reframe.plan(o.get("crop_mode", clip["crop_mode"]), o.get("aspect", clip["aspect"]),
                        o.get("crop", clip.get("crop") or {}), source["width"], source["height"],
                        float(o.get("start", clip["start"])), float(o.get("end", clip["end"])),
                        load_track(clip["project_id"]), scenes)


def run_export(ctx: JobContext) -> dict:
    clip_id, export_id = ctx.params["clip_id"], ctx.params["export_id"]
    with session() as s:
        row = s.get(GeneratedClip, clip_id)
        if not row:
            raise ClipForgeError("The clip no longer exists.")
        clip = row.to_dict()
        source = s.query(SourceVideo).filter_by(project_id=clip["project_id"]).first().to_dict()
        track = s.query(CaptionTrack).filter_by(clip_id=clip_id).first()
        all_cues = track.cues if track else []
    if not Path(source["path"]).is_file():
        raise MediaError("The source video file is missing. It may have been moved or deleted.")
    cfg = render.export_settings({**(clip.get("export_settings") or {}), **(ctx.params.get("settings") or {})})
    cues = cap.clip_cues(all_cues, clip["start"], clip["end"])
    plan = crop_plan_for(clip, source)
    out = render.output_path(clip, cfg, clip["project_id"])
    render.check_disk(out.parent, source, clip["end"] - clip["start"])
    work = paths.tmp / f"export_{export_id}"
    work.mkdir(parents=True, exist_ok=True)
    tmp_out = work / "render.mp4"

    def mark(**fields) -> None:
        with session() as s:
            e = s.get(ExportJob, export_id)
            for k, v in fields.items():
                setattr(e, k, v)

    try:
        ctx.start_stage("render", "Rendering video")
        mark(status="rendering", settings=cfg)
        args, facts = render.build(clip, source, cues, plan, cfg, work, tmp_out)
        ff.run(args, duration=facts["duration"], on_progress=lambda f: ctx.progress(f, "Rendering video"),
               check=ctx.check)
        ctx.finish_stage()

        ctx.start_stage("validate", "Validating the exported file")
        report = render.validate(tmp_out, facts, cues)
        ctx.progress(0.9)
        if not report["ok"]:
            failed = "; ".join(f"{c['name']}: {c['detail']}" for c in report["checks"] if not c["ok"])
            mark(status="failed", validation=report)
            raise MediaError(f"The rendered file failed validation ({failed}).")
        shutil.move(str(tmp_out), str(out))  # only a validated file reaches the output folder
        labels = bool((clip.get("style") or {}).get("speaker_labels"))
        if cfg["sidecar_srt"] and cues:
            out.with_suffix(".srt").write_text(cap.to_srt(cues, labels), encoding="utf-8")
        if cfg["sidecar_vtt"] and cues:
            out.with_suffix(".vtt").write_text(cap.to_vtt(cues, labels), encoding="utf-8")
        report["facts"] = facts
        mark(status="completed", path=str(out), validation=report, size_bytes=out.stat().st_size,
             duration=report["info"]["duration"])
        ctx.finish_stage()
        return {"path": str(out), "export_id": export_id}
    except Exception as e:
        with session() as s:
            row = s.get(ExportJob, export_id)
            if row and row.status != "completed":
                row.status = "cancelled" if type(e).__name__ == "CancelledError" else "failed"
        raise
    finally:
        if not settings.get("keep_temp_files"):
            shutil.rmtree(work, ignore_errors=True)


def submit_export(clip_id: str, cfg: dict | None) -> dict:
    with session() as s:
        clip = s.get(GeneratedClip, clip_id)
        if not clip:
            raise ClipForgeError("Clip not found.")
        if cfg:
            clip.export_settings = {**(clip.export_settings or {}),
                                    **{k: v for k, v in cfg.items() if k in render.DEFAULT_EXPORT}}
        exp = ExportJob(clip_id=clip_id, project_id=clip.project_id, job_id="")
        s.add(exp)
        s.flush()
        export_id, project_id = exp.id, clip.project_id
    job_id = manager.submit("export", {"clip_id": clip_id, "export_id": export_id, "settings": cfg or {}},
                            project_id=project_id, clip_id=clip_id)
    with session() as s:
        s.get(ExportJob, export_id).job_id = job_id
    return {"job_id": job_id, "export_id": export_id}


manager.register("export", run_export, heavy=True, stages=[("render", 0.88), ("validate", 0.12)])
