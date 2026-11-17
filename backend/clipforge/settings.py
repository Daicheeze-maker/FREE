"""Application settings stored in SQLite, with typed defaults."""
from __future__ import annotations

import secrets
from typing import Any

from .db import session
from .models import AppSetting

DEFAULTS: dict[str, Any] = {
    "setup_complete": False,
    "ffmpeg_path": "",  # empty = find on PATH
    "ffprobe_path": "",
    "output_dir": "",  # empty = <data>/exports
    "performance_profile": "balanced",  # performance|balanced|quality
    "cpu_threads": 0,  # 0 = auto
    # AI providers
    "asr_provider": "sherpa_whisper",  # sherpa_whisper|faster_whisper
    "asr_model": "",  # catalog id of the active speech model
    "tagger_model": "",  # catalog id of the active audio tagger
    "face_model": "",  # catalog id of the face detector
    "llm_enabled": False,  # local OpenAI-compatible server (llama.cpp / Ollama / LM Studio)
    "llm_base_url": "http://127.0.0.1:8080/v1",
    "llm_model": "",
    "llm_vision": True,  # the configured model accepts images
    "llm_api_key": "",  # kept server side only, never returned to the UI
    "allow_cloud_ai": False,  # must be on before a non-local llm_base_url is used
    # export defaults
    "export_codec": "h264",
    "export_quality": "high",  # draft|standard|high
    "video_encoder": "auto",  # auto|software|hardware
    # privacy / network
    "lan_access": False,  # serve the UI to phones on the local network (restart required)
    "pair_pin": "",
    "auth_token": "",
    "keep_temp_files": False,
}

SECRET_KEYS = {"llm_api_key", "auth_token"}


def get_all(include_secrets: bool = False) -> dict[str, Any]:
    out = dict(DEFAULTS)
    with session() as s:
        for row in s.query(AppSetting).all():
            out[row.key] = row.value
    if not include_secrets:
        for k in SECRET_KEYS:
            out[k] = bool(out.get(k))  # only reveal whether it is set
    return out


def get(key: str) -> Any:
    with session() as s:
        row = s.get(AppSetting, key)
        return row.value if row else DEFAULTS.get(key)


def update(values: dict[str, Any]) -> None:
    with session() as s:
        for k, v in values.items():
            if k not in DEFAULTS:
                raise KeyError(f"Unknown setting: {k}")
            row = s.get(AppSetting, k)
            if row:
                row.value = v
            else:
                s.add(AppSetting(key=k, value=v))


def ensure_secrets() -> None:
    """Create the session token and phone pairing PIN on first run."""
    if not get("auth_token"):
        update({"auth_token": secrets.token_urlsafe(32)})
    if not get("pair_pin"):
        update({"pair_pin": f"{secrets.randbelow(10**6):06d}"})


PROFILES = {
    # sample_fps: frames/sec inspected by the cheap OpenCV pass; vlm_frames: budget for the expensive model
    "performance": {"sample_fps": 1.0, "tag_hop": 2.0, "vlm_frames": 12, "scene_downscale": 4},
    "balanced": {"sample_fps": 2.0, "tag_hop": 1.0, "vlm_frames": 30, "scene_downscale": 3},
    "quality": {"sample_fps": 4.0, "tag_hop": 0.5, "vlm_frames": 80, "scene_downscale": 2},
}
