"""FFmpeg/FFprobe wrappers: discovery, probing, progress-reporting runs, thumbnails."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..config import PACKAGE_DIR
from ..errors import CancelledError, MediaError

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _find(name: str, configured: str) -> str | None:
    if configured and Path(configured).is_file():
        return configured
    exe = name + (".exe" if sys.platform == "win32" else "")
    bundled = PACKAGE_DIR.parent / "bin" / exe  # optional drop-in location: backend/bin/
    if bundled.is_file():
        return str(bundled)
    return shutil.which(name)


def ffmpeg_bin() -> str:
    from .. import settings

    p = _find("ffmpeg", settings.get("ffmpeg_path") or "")
    if not p:
        raise MediaError("FFmpeg was not found. Install FFmpeg or set its path in Settings.")
    return p


def ffprobe_bin() -> str:
    from .. import settings

    p = _find("ffprobe", settings.get("ffprobe_path") or "")
    if not p:
        raise MediaError("FFprobe was not found. Install FFmpeg or set its path in Settings.")
    return p


def tool_versions() -> dict:
    out = {}
    for name, fn in (("ffmpeg", ffmpeg_bin), ("ffprobe", ffprobe_bin)):
        try:
            exe = fn()
            line = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=10,
                                  creationflags=NO_WINDOW).stdout.splitlines()[0]
            out[name] = {"found": True, "path": exe, "version": line}
        except Exception as e:  # noqa: BLE001 - reported to the UI, never fatal
            out[name] = {"found": False, "error": str(e)}
    return out


@dataclass
class MediaInfo:
    duration: float
    size_bytes: int
    bitrate: int | None
    width: int
    height: int
    fps: float
    video_codec: str | None
    pix_fmt: str | None
    has_audio: bool
    audio_codec: str | None
    sample_rate: int | None
    channels: int | None
    container: str
    rotation: int = 0


def _fps(s: str | None) -> float:
    if not s or s in ("0/0", "N/A"):
        return 0.0
    if "/" in s:
        a, b = s.split("/")
        return float(a) / float(b) if float(b) else 0.0
    return float(s)


def probe(path: str | Path) -> MediaInfo:
    """Read real metadata. Raises MediaError for unreadable or video-less files."""
    path = Path(path)
    if not path.is_file():
        raise MediaError(f"File not found: {path.name}")
    r = subprocess.run(
        [ffprobe_bin(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, timeout=60, creationflags=NO_WINDOW,
    )
    if r.returncode != 0:
        detail = (r.stderr or "").strip().splitlines()[-1:] or ["unreadable"]
        raise MediaError(f"This file could not be read as a video ({detail[0]}). It may be corrupted or unsupported.")
    data = json.loads(r.stdout or "{}")
    streams = data.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"
              and not s.get("disposition", {}).get("attached_pic")), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fmt = data.get("format", {})
    if v is None:
        raise MediaError("No video stream was found in this file.")
    duration = float(fmt.get("duration") or v.get("duration") or 0)
    if duration <= 0:
        raise MediaError("The video has no readable duration. It may be corrupted or incomplete.")
    rotation = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rotation = int(sd["rotation"]) % 360
    w, h = int(v.get("width") or 0), int(v.get("height") or 0)
    if rotation in (90, 270):
        w, h = h, w
    return MediaInfo(
        duration=duration,
        size_bytes=int(fmt.get("size") or path.stat().st_size),
        bitrate=int(fmt["bit_rate"]) if fmt.get("bit_rate") else None,
        width=w, height=h,
        fps=round(_fps(v.get("avg_frame_rate")) or _fps(v.get("r_frame_rate")), 3),
        video_codec=v.get("codec_name"), pix_fmt=v.get("pix_fmt"),
        has_audio=a is not None,
        audio_codec=a.get("codec_name") if a else None,
        sample_rate=int(a["sample_rate"]) if a and a.get("sample_rate") else None,
        channels=int(a["channels"]) if a and a.get("channels") else None,
        container=fmt.get("format_name", ""), rotation=rotation,
    )


def run(args: list[str], duration: float | None = None,
        on_progress: Callable[[float], None] | None = None,
        check: Callable[[], None] | None = None, cwd: str | None = None) -> None:
    """Run ffmpeg, reporting measured progress from `-progress`, and stop on cancel."""
    cmd = [ffmpeg_bin(), "-hide_banner", "-nostdin", "-y", "-v", "error", "-progress", "pipe:1", "-nostats", *args]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            cwd=cwd, creationflags=NO_WINDOW)
    import threading

    err_lines: list[str] = []
    t = threading.Thread(target=lambda: err_lines.extend(proc.stderr), daemon=True)  # drain so it can't block
    t.start()
    try:
        for line in proc.stdout:  # type: ignore[union-attr]
            if check:
                check()
            if line.startswith("out_time_us=") and duration and on_progress:
                try:
                    on_progress(min(1.0, max(0.0, int(line.split("=")[1]) / 1e6 / duration)))
                except ValueError:
                    pass
        proc.wait()
    except CancelledError:
        proc.kill()
        proc.wait()
        raise
    finally:
        if proc.poll() is None:
            proc.kill()
    t.join(timeout=2)
    if proc.returncode != 0:
        raise MediaError("FFmpeg failed: " + ("".join(err_lines).strip()[-800:] or f"exit code {proc.returncode}"))


def extract_frame(src: str | Path, t: float, out: str | Path, width: int = 480) -> bool:
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [ffmpeg_bin(), "-hide_banner", "-nostdin", "-y", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(src),
         "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "4", str(out)],
        capture_output=True, timeout=120, creationflags=NO_WINDOW)
    return r.returncode == 0 and Path(out).is_file() and Path(out).stat().st_size > 0


def has_encoder(name: str) -> bool:
    try:
        r = subprocess.run([ffmpeg_bin(), "-hide_banner", "-encoders"], capture_output=True, text=True,
                           timeout=15, creationflags=NO_WINDOW)
        return any(line.split()[1:2] == [name] for line in r.stdout.splitlines() if line.strip())
    except Exception:  # noqa: BLE001
        return False


def encoder_works(name: str) -> bool:
    """Listing an encoder does not mean the GPU/driver accepts it — do a tiny real encode."""
    if not has_encoder(name):
        return False
    try:
        r = subprocess.run(
            [ffmpeg_bin(), "-hide_banner", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
             "color=c=black:s=256x256:r=30:d=0.2", "-c:v", name, "-f", "null", "-"],
            capture_output=True, timeout=30, creationflags=NO_WINDOW)
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def filter_path(p: str | Path) -> str:
    """Escape a path for use inside an ffmpeg filter argument (Windows drive colons included)."""
    s = str(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    return f"'{s}'"


BROWSER_VIDEO = {"h264", "vp8", "vp9", "av1"}
BROWSER_AUDIO = {"aac", "mp3", "opus", "vorbis", None}


def browser_playable(info: MediaInfo, path: str | Path) -> bool:
    ext = Path(path).suffix.lower()
    if ext not in (".mp4", ".m4v", ".webm", ".mov"):
        return False
    if info.video_codec not in BROWSER_VIDEO or info.audio_codec not in BROWSER_AUDIO:
        return False
    return not (info.pix_fmt or "").endswith("10le")  # 10-bit H.264 does not play in WebView2/Chrome
