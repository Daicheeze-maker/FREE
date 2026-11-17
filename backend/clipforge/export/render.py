"""Render a clip with FFmpeg from its saved editor state, then validate the file."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from .. import hardware, settings
from ..captions import engine as cap
from ..config import FONTS_DIR, paths
from ..errors import MediaError
from ..media import ffmpeg as ff
from . import reframe

QUALITY = {"draft": {"crf": 28, "preset": "veryfast"}, "standard": {"crf": 23, "preset": "medium"},
           "high": {"crf": 18, "preset": "medium"}}

# Platform presets only set encoding parameters that every one of these platforms accepts
# (H.264 + AAC in MP4, 9:16). Length limits change often and differ per account, so they are
# advisory text with a link to the platform's own help page rather than enforced rules.
PLATFORM_PRESETS = {
    "tiktok": {"label": "TikTok", "aspect": "9:16", "resolution": "1080p", "fps": 30, "codec": "h264",
               "quality": "high", "audio_bitrate": 192, "normalize": True,
               "advice": "Vertical 9:16, 1080x1920. Check current length limits in TikTok's help center.",
               "url": "https://support.tiktok.com/"},
    "shorts": {"label": "YouTube Shorts", "aspect": "9:16", "resolution": "1080p", "fps": 30, "codec": "h264",
               "quality": "high", "audio_bitrate": 192, "normalize": True,
               "advice": "Vertical or square. Check current length limits on YouTube Help.",
               "url": "https://support.google.com/youtube/"},
    "reels": {"label": "Instagram Reels", "aspect": "9:16", "resolution": "1080p", "fps": 30, "codec": "h264",
              "quality": "high", "audio_bitrate": 192, "normalize": True,
              "advice": "Vertical 9:16, 1080x1920. Check current length limits in Instagram's help center.",
              "url": "https://help.instagram.com/"},
    "general": {"label": "General short-form", "aspect": "9:16", "resolution": "1080p", "fps": "source",
                "codec": "h264", "quality": "high", "audio_bitrate": 192, "normalize": False,
                "advice": "High-quality H.264 MP4 that plays everywhere.", "url": ""},
}

DEFAULT_EXPORT = {"preset": "general", "resolution": "1080p", "fps": "source", "codec": "h264", "quality": "high",
                  "video_bitrate": 0, "audio_bitrate": 192, "normalize": False, "burn_captions": True,
                  "sidecar_srt": False, "sidecar_vtt": False, "filename": "", "output_dir": ""}


def export_settings(clip_settings: dict | None) -> dict:
    out = dict(DEFAULT_EXPORT)
    out["codec"] = settings.get("export_codec") or "h264"
    out["quality"] = settings.get("export_quality") or "high"
    out.update({k: v for k, v in (clip_settings or {}).items() if k in DEFAULT_EXPORT})
    return out


def safe_name(text: str) -> str:
    name = re.sub(r"[^\w\- ]+", "", text, flags=re.UNICODE).strip().replace(" ", "_")[:60]
    return name or "clip"


def output_path(clip: dict, cfg: dict, project_id: str) -> Path:
    base = cfg.get("output_dir") or settings.get("output_dir") or str(paths.exports / project_id)
    out_dir = Path(base).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = safe_name(cfg.get("filename") or clip["title"])
    tag = clip["aspect"].replace(":", "x")
    p = out_dir / f"{stem}_{tag}.mp4"
    if p.exists():
        p = out_dir / f"{stem}_{tag}_{datetime.now():%Y%m%d_%H%M%S}.mp4"
    return p


def _encoder(codec: str) -> tuple[list[str], str]:
    """Pick an encoder that really works here. Software is the default; hardware is opt-in."""
    pref = settings.get("video_encoder") or "auto"
    hw = hardware.detect()["encoders"]
    if pref == "hardware":
        for name in ([f"{'hevc' if codec == 'h265' else 'h264'}_{v}" for v in ("amf", "nvenc", "qsv")]):
            if hw.get(name):
                return ["-c:v", name], name
    if codec == "h265" and hw.get("libx265"):
        return ["-c:v", "libx265", "-tag:v", "hvc1"], "libx265"
    if codec == "h265":
        raise MediaError("H.265 was requested but this FFmpeg build has no H.265 encoder. Choose H.264.")
    return ["-c:v", "libx264"], "libx264"


def build(clip: dict, source: dict, cues: list[dict], crop_plan: dict, cfg: dict, workdir: Path,
          out: Path) -> tuple[list[str], dict]:
    """FFmpeg arguments for this clip. Returns (args, facts about the render)."""
    start, dur = float(clip["start"]), float(clip["end"]) - float(clip["start"])
    if dur <= 0.2:
        raise MediaError("The clip is too short to export.")
    sw, sh = source["width"], source["height"]
    bw, bh = crop_plan["box"]
    cw, ch = reframe._even(bw * sw), reframe._even(bh * sh)
    W, H = reframe.output_size(clip["aspect"] if crop_plan["effective"] != "original" else "original",
                               cfg["resolution"], sw, sh, cw, ch)
    if crop_plan["effective"] == "fit_blur":
        W, H = reframe.output_size(clip["aspect"], "1080p" if cfg["resolution"] == "original" else cfg["resolution"],
                                   sw, sh, sw, sh)
    fps = source["fps"] or 30
    if cfg["fps"] not in ("source", "", None):
        fps = float(cfg["fps"])
    fps = min(fps, 60.0)

    inputs = ["-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", source["path"]]
    n_in = 1
    eff = crop_plan["effective"]
    if eff == "original":
        v = f"[0:v]scale={W}:{H}"
    elif eff == "fit_blur":
        v = (f"[0:v]split[bgs][fgs];[bgs]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
             f"boxblur=24:4[bg];[fgs]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];"
             f"[bg][fg]overlay=(W-w)/2:(H-h)/2")
    else:
        keys, cuts = crop_plan["keys"], crop_plan.get("cuts", [])
        # keys hold the box centre (normalised); ffmpeg wants the top-left corner in pixels
        tl = [[k[0], k[1] - bw / 2, k[2] - bh / 2] for k in keys]
        x, y = reframe.expr(tl, 1, sw, cuts), reframe.expr(tl, 2, sh, cuts)
        v = f"[0:v]crop={cw}:{ch}:x='{x}':y='{y}',scale={W}:{H}"
    v += f",setsar=1,fps={fps:g}"
    burned = bool(cfg["burn_captions"] and clip.get("captions_enabled", True) and cues)
    if burned:
        ass = workdir / "captions.ass"
        ass.write_text(cap.to_ass(cues, clip.get("style") or {}, W, H), encoding="utf-8")
        v += f",ass={ff.filter_path(ass)}:fontsdir={ff.filter_path(FONTS_DIR)}"
    v += ",format=yuv420p[v]"

    audio_parts = []
    has_src_audio = bool(source.get("has_audio")) and not clip.get("mute")
    music = clip.get("music_path")
    if music and not Path(music).is_file():
        raise MediaError("The background music file no longer exists. Remove it or choose another file.")
    if has_src_audio:
        audio_parts.append(f"[0:a:0]volume={float(clip.get('volume', 1.0)):.3f}[a0]")
    if music:
        inputs += ["-stream_loop", "-1", "-t", f"{dur:.3f}", "-i", music]
        audio_parts.append(f"[{n_in}:a:0]volume={float(clip.get('music_volume', 0.25)):.3f}[a1]")
        n_in += 1
    if has_src_audio and music:
        mix = "[a0][a1]amix=inputs=2:duration=first:normalize=0"
    elif has_src_audio:
        mix = "[a0]anull"
    elif music:
        mix = "[a1]anull"
    else:  # silent track so every player and platform sees a normal audio stream
        inputs += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        mix = f"[{n_in}:a:0]anull"
    if cfg["normalize"] and (has_src_audio or music):
        mix += ",loudnorm=I=-14:TP=-1.5:LRA=11"
    audio_parts.append(mix + ",aresample=48000[a]")

    enc, enc_name = _encoder(cfg["codec"])
    q = QUALITY.get(cfg["quality"], QUALITY["high"])
    if int(cfg.get("video_bitrate") or 0) > 0:
        rate = ["-b:v", f"{int(cfg['video_bitrate'])}k", "-maxrate", f"{int(cfg['video_bitrate'] * 1.5)}k",
                "-bufsize", f"{int(cfg['video_bitrate'] * 3)}k"]
    elif enc_name.startswith("lib"):
        rate = ["-crf", str(q["crf"] + (4 if enc_name == "libx265" else 0)), "-preset", q["preset"]]
    else:
        rate = ["-b:v", {"draft": "4M", "standard": "8M", "high": "12M"}[cfg["quality"]]]
    args = [*inputs, "-filter_complex", ";".join([v, *audio_parts]), "-map", "[v]", "-map", "[a]",
            *enc, *rate, "-c:a", "aac", "-b:a", f"{int(cfg['audio_bitrate'])}k", "-ac", "2",
            "-t", f"{dur:.3f}", "-movflags", "+faststart", str(out)]
    return args, {"width": W, "height": H, "fps": fps, "duration": dur, "encoder": enc_name,
                  "captions_burned": burned, "crop": eff}


def validate(path: Path, facts: dict, cues: list[dict]) -> dict:
    """Check the rendered file for real: streams, size, duration, and a full decode pass."""
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    try:
        info = ff.probe(path)
    except MediaError as e:
        return {"ok": False, "checks": [{"name": "File is readable", "ok": False, "detail": str(e)}]}
    add("Video stream", info.video_codec is not None, f"{info.video_codec} {info.width}x{info.height} @ {info.fps:g} fps")
    add("Audio stream", info.has_audio, f"{info.audio_codec}, {info.sample_rate} Hz" if info.has_audio else "missing")
    add("Resolution", (info.width, info.height) == (facts["width"], facts["height"]),
        f"expected {facts['width']}x{facts['height']}, got {info.width}x{info.height}")
    tol = max(0.25, facts["duration"] * 0.02)
    add("Duration", abs(info.duration - facts["duration"]) <= tol,
        f"expected {facts['duration']:.2f}s, got {info.duration:.2f}s")
    r = subprocess.run([ff.ffmpeg_bin(), "-hide_banner", "-nostdin", "-v", "error", "-i", str(path), "-f", "null", "-"],
                       capture_output=True, text=True, timeout=1800, creationflags=ff.NO_WINDOW)
    errors = (r.stderr or "").strip()
    add("Full decode (playback validity)", r.returncode == 0 and not errors,
        "every frame decoded without errors" if not errors else errors[-300:])
    if facts["captions_burned"]:
        inside = all(-0.01 <= c["start"] < c["end"] <= facts["duration"] + 0.05 for c in cues)
        ordered = all(a["end"] <= b["start"] + 0.01 for a, b in zip(cues, cues[1:]))
        add("Caption timing", inside and ordered,
            f"{len(cues)} cues, all inside the clip and in order (timing is checked, not the rendered pixels)")
    return {"ok": all(c["ok"] for c in checks), "checks": checks,
            "info": {"width": info.width, "height": info.height, "fps": info.fps, "duration": info.duration,
                     "video_codec": info.video_codec, "audio_codec": info.audio_codec,
                     "size_bytes": info.size_bytes}}


def check_disk(out_dir: Path, source: dict, dur: float) -> None:
    need = max(200 * 2**20, int((source.get("bitrate") or 8_000_000) / 8 * dur * 3))
    free = shutil.disk_usage(out_dir).free
    if free < need:
        raise MediaError(f"Not enough free disk space to export ({free / 2**30:.1f} GB free).")


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)
