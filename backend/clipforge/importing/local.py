"""Create projects from local files (referenced in place) or uploads (stored in the data dir)."""
from __future__ import annotations

import hashlib
from pathlib import Path

from ..config import VIDEO_EXTENSIONS, paths
from ..db import session
from ..errors import ClipForgeError, ImportError_
from ..jobs.manager import JobContext, manager
from ..media import ffmpeg as ff
from ..models import Project, SourceVideo, new_id


class DuplicateImport(ClipForgeError):
    def __init__(self, project_id: str):
        super().__init__("This video has already been imported.")
        self.project_id = project_id


def fingerprint(path: Path) -> str:
    """Content fingerprint that stays cheap for huge files: size + first and last megabyte."""
    h = hashlib.sha1()
    size = path.stat().st_size
    h.update(str(size).encode())
    with open(path, "rb") as f:
        h.update(f.read(1 << 20))
        if size > (2 << 20):
            f.seek(-(1 << 20), 2)
            h.update(f.read(1 << 20))
    return h.hexdigest()


def validate_extension(name: str) -> None:
    ext = Path(name).suffix.lower()
    if ext not in VIDEO_EXTENSIONS:
        raise ImportError_(f"“{ext or name}” is not a supported video type. "
                           f"Supported: {', '.join(sorted(e.strip('.').upper() for e in VIDEO_EXTENSIONS))}.")


def create_project(path: str | Path, origin: str = "local", managed: bool = False, name: str | None = None,
                   origin_url: str | None = None, project_id: str | None = None) -> dict:
    path = Path(path).expanduser()
    if not path.is_file():
        raise ImportError_("That file does not exist.")
    path = path.resolve()
    validate_extension(path.name)
    info = ff.probe(path)  # raises a readable error for corrupted / unsupported files
    fp = fingerprint(path)
    with session() as s:
        dup = s.query(SourceVideo).filter_by(fingerprint=fp).first()
        if dup:
            raise DuplicateImport(dup.project_id)
        project = Project(id=project_id or new_id(), name=(name or path.stem)[:300])
        s.add(project)
        s.flush()
        thumb = paths.project(project.id) / "thumb.jpg"
        ok = ff.extract_frame(path, min(info.duration * 0.1, 10.0), thumb, width=640)
        src = SourceVideo(
            project_id=project.id, path=str(path), filename=path.name, origin=origin, origin_url=origin_url,
            managed=managed, fingerprint=fp, size_bytes=info.size_bytes, duration=info.duration, width=info.width,
            height=info.height, fps=info.fps, video_codec=info.video_codec, audio_codec=info.audio_codec,
            has_audio=info.has_audio, sample_rate=info.sample_rate, channels=info.channels, bitrate=info.bitrate,
            thumb_path=str(thumb) if ok else None)
        s.add(src)
        s.flush()
        result = {"project": project.to_dict(), "source": src.to_dict()}
    if not ff.browser_playable(info, path):
        manager.submit("proxy", {"project_id": result["project"]["id"]}, project_id=result["project"]["id"])
        result["proxy"] = True
    return result


def make_proxy(ctx: JobContext) -> dict:
    """Preview copy for formats the built-in player cannot decode (MKV, AVI, HEVC, 10-bit...)."""
    pid = ctx.params["project_id"]
    with session() as s:
        src = s.query(SourceVideo).filter_by(project_id=pid).first()
        if not src:
            return {}
        path, duration = src.path, src.duration
    out = paths.project(pid) / "proxy.mp4"
    ctx.start_stage("proxy", "Creating a preview copy")
    ff.run(["-i", path, "-vf", "scale=-2:'min(720,ih)'", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)],
           duration=duration, on_progress=lambda f: ctx.progress(f), check=ctx.check)
    with session() as s:
        src = s.query(SourceVideo).filter_by(project_id=pid).first()
        if src:
            src.proxy_path = str(out)
    return {"proxy": str(out)}


manager.register("proxy", make_proxy, heavy=True, stages=[("proxy", 1.0)])
