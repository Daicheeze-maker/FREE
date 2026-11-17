"""YouTube import through yt-dlp, for videos the user is authorised to process.

No cookies, no login, no DRM handling: private, age-gated, members-only or protected
videos fail with a clear message.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from ..config import paths
from ..errors import CancelledError, ImportError_
from ..jobs.manager import JobContext, manager
from ..media import ffmpeg as ff
from ..models import new_id
from .local import DuplicateImport, create_project

HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}


def validate_url(url: str) -> str:
    url = (url or "").strip()
    p = urlparse(url)
    if p.scheme not in ("http", "https") or (p.hostname or "").lower() not in HOSTS:
        raise ImportError_("Enter a valid YouTube video link (youtube.com/watch?v=… or youtu.be/…).")
    if "list=" in p.query and "v=" not in p.query:
        raise ImportError_("Playlists are not supported. Paste the link of a single video.")
    return url


def _friendly(err: Exception) -> str:
    msg = re.sub(r"\x1b\[[0-9;]*m", "", str(err))
    low = msg.lower()
    if any(k in low for k in ("urlopen error", "timed out", "connection refused", "connection reset",
                              "getaddrinfo", "name resolution", "network is unreachable", "tunnel connection",
                              "proxyerror", "unable to download api page", "unable to download webpage")):
        return "Could not reach YouTube. Check your internet connection and try again."
    if "private video" in low:
        return "This video is private. ClipForge cannot access private videos."
    if "sign in to confirm your age" in low or "age-restricted" in low or "members-only" in low \
            or "join this channel" in low:
        return "This video requires signing in (age-restricted or members-only), which ClipForge does not do."
    if "drm" in low:
        return "This video is DRM-protected and cannot be imported."
    if "unavailable" in low or "has been removed" in low or "does not exist" in low or "not available" in low:
        return "This video is unavailable (removed, region-blocked or the link is wrong)."
    if "unsupported url" in low:
        return "This link is not a supported video."
    return "YouTube import failed: " + msg.replace("ERROR: ", "")[:300]


def _ydl(opts: dict):
    try:
        import yt_dlp
    except ImportError as e:
        raise ImportError_("yt-dlp is not installed, so link import is unavailable. Local import still works.") from e
    base = {"quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": 20}
    return yt_dlp.YoutubeDL({**base, **opts}), yt_dlp


def info(url: str) -> dict:
    url = validate_url(url)
    ydl, yt_dlp = _ydl({"skip_download": True})
    try:
        with ydl:
            d = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        raise ImportError_(_friendly(e)) from e
    if d.get("is_live"):
        raise ImportError_("Live streams that are still running cannot be imported.")
    return {"url": url, "title": d.get("title"), "uploader": d.get("uploader") or d.get("channel"),
            "duration": d.get("duration"), "thumbnail": d.get("thumbnail"),
            "width": d.get("width"), "height": d.get("height")}


def download_job(ctx: JobContext) -> dict:
    url = validate_url(ctx.params["url"])
    project_id = new_id()
    out_dir = paths.project(project_id)
    ctx.start_stage("download", "Contacting YouTube")

    def hook(d: dict) -> None:
        if ctx.cancel_event.is_set():
            raise CancelledError()
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                ctx.progress(0.95 * d.get("downloaded_bytes", 0) / total,
                             f"{d.get('downloaded_bytes', 0) / 2**20:.0f} / {total / 2**20:.0f} MB")

    ydl, yt_dlp = _ydl({
        "format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/b[height<=1080]/b",
        "merge_output_format": "mp4", "outtmpl": str(out_dir / "source.%(ext)s"),
        "progress_hooks": [hook], "ffmpeg_location": str(Path(ff.ffmpeg_bin()).parent),
    })
    try:
        with ydl:
            d = ydl.extract_info(url, download=True)
    except CancelledError:
        _cleanup(out_dir)
        raise
    except yt_dlp.utils.DownloadError as e:
        _cleanup(out_dir)
        if ctx.cancel_event.is_set():
            raise CancelledError() from e
        raise ImportError_(_friendly(e)) from e
    files = [f for f in out_dir.glob("source.*") if f.suffix.lower() in (".mp4", ".mkv", ".webm")]
    if not files:
        _cleanup(out_dir)
        raise ImportError_("The download finished but no video file was produced.")
    ctx.progress(0.97, "Registering the project")
    try:
        res = create_project(files[0], origin="youtube", managed=True, name=d.get("title"), origin_url=url,
                             project_id=project_id)
    except DuplicateImport as e:
        _cleanup(out_dir)
        return {"project_id": e.project_id, "duplicate": True}
    except Exception:
        _cleanup(out_dir)
        raise
    return {"project_id": res["project"]["id"]}


def _cleanup(d: Path) -> None:
    import shutil

    shutil.rmtree(d, ignore_errors=True)


manager.register("youtube", download_job, heavy=False, stages=[("download", 1.0)])
