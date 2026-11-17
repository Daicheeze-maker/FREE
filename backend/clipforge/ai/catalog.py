"""Catalog of downloadable local models.

Sizes are the published download sizes. RAM figures are approximate working-set
estimates for CPU inference and are shown to the user as estimates.
Every entry runs on CPU through ONNX Runtime / CTranslate2 — no CUDA required.
"""
from __future__ import annotations

SHERPA = "https://github.com/k2-fsa/sherpa-onnx/releases/download"


def _whisper(size: str, mb: int, ram: float, note: str) -> dict:
    return {
        "id": f"whisper-{size}", "name": f"Whisper {size} (ONNX)", "version": "sherpa-onnx export",
        "purpose": "asr", "provider": "sherpa_whisper",
        "description": f"Multilingual speech recognition with language detection (English, Tagalog and ~100 more). {note}",
        "url": f"{SHERPA}/asr-models/sherpa-onnx-whisper-{size}.tar.bz2",
        "archive_dir": f"sherpa-onnx-whisper-{size}", "size_bytes": mb,
        "ram_gb": ram, "runtime": "ONNX Runtime (CPU)", "license": "MIT (OpenAI Whisper)",
        "license_url": "https://github.com/openai/whisper/blob/main/LICENSE",
        "timing": "estimated",
        "compat": "Windows / Linux / macOS, any CPU. No GPU needed.",
    }


def _fw(size: str, mb: int, ram: float, note: str) -> dict:
    return {
        "id": f"faster-whisper-{size}", "name": f"faster-whisper {size}", "version": "Systran CTranslate2",
        "purpose": "asr", "provider": "faster_whisper",
        "description": f"Whisper with true word-level timestamps. {note}",
        "hf_repo": f"Systran/faster-whisper-{size}", "size_bytes": mb, "ram_gb": ram,
        "runtime": "CTranslate2 (CPU, int8)", "license": "MIT",
        "license_url": "https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE",
        "timing": "word",
        "compat": "Windows / Linux / macOS, any CPU. Downloaded from Hugging Face.",
    }


CATALOG: list[dict] = [
    _whisper("tiny", 116_204_861, 0.6, "Fastest; lower accuracy, weakest on Tagalog."),
    _whisper("base", 207_557_382, 0.8, "Fast; fair accuracy."),
    _whisper("small", 639_387_718, 1.6, "Recommended balance for a 6-core CPU; good English, usable Tagalog/Taglish."),
    _whisper("medium", 1_931_372_882, 3.5, "Better Tagalog/Taglish accuracy; noticeably slower on CPU."),
    _whisper("turbo", 563_790_207, 2.5, "Large-v3-turbo: near-large accuracy with a small decoder."),
    _fw("small", 484_000_000, 1.5, "Recommended when you want word-by-word captions."),
    _fw("medium", 1_530_000_000, 3.0, "Higher accuracy, slower."),
    _fw("large-v3-turbo", 1_620_000_000, 3.5, "Best accuracy of the CPU options."),
    {
        "id": "ced-tiny", "name": "CED-tiny audio tagger", "version": "2024-04-19",
        "purpose": "audio_tagging", "provider": "sherpa_tagger",
        "description": "Detects 527 AudioSet sound classes (laughter, screaming, cheering, music, gunshots...) "
                       "independently of speech recognition.",
        "url": f"{SHERPA}/audio-tagging-models/sherpa-onnx-ced-tiny-audio-tagging-2024-04-19.tar.bz2",
        "archive_dir": "sherpa-onnx-ced-tiny-audio-tagging-2024-04-19", "size_bytes": 28_531_989,
        "ram_gb": 0.3, "runtime": "ONNX Runtime (CPU)", "license": "Apache-2.0 (CED, Xiaomi)",
        "license_url": "https://github.com/RicherMans/CED/blob/main/LICENSE",
        "compat": "Any CPU.",
    },
    {
        "id": "ced-mini", "name": "CED-mini audio tagger", "version": "2024-04-19",
        "purpose": "audio_tagging", "provider": "sherpa_tagger",
        "description": "Larger, more accurate version of the audio tagger.",
        "url": f"{SHERPA}/audio-tagging-models/sherpa-onnx-ced-mini-audio-tagging-2024-04-19.tar.bz2",
        "archive_dir": "sherpa-onnx-ced-mini-audio-tagging-2024-04-19", "size_bytes": 47_658_399,
        "ram_gb": 0.4, "runtime": "ONNX Runtime (CPU)", "license": "Apache-2.0 (CED, Xiaomi)",
        "license_url": "https://github.com/RicherMans/CED/blob/main/LICENSE",
        "compat": "Any CPU.",
    },
    {
        "id": "silero-vad", "name": "Silero VAD", "version": "v4",
        "purpose": "vad", "provider": "sherpa_vad",
        "description": "Voice activity detection. Splits audio at real pauses so captions and clip boundaries "
                       "line up with speech. Without it a simpler loudness-based splitter is used.",
        "url": f"{SHERPA}/asr-models/silero_vad.onnx", "size_bytes": 643_854,
        "ram_gb": 0.05, "runtime": "ONNX Runtime (CPU)", "license": "MIT",
        "license_url": "https://github.com/snakers4/silero-vad/blob/master/LICENSE",
        "compat": "Any CPU.",
    },
    {
        "id": "yunet-face", "name": "YuNet face detector", "version": "2023mar",
        "purpose": "face", "provider": "opencv_yunet",
        "description": "Fast face detector used for face tracking, reaction framing and smart reframing.",
        "url": "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
               "face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "size_bytes": 232_589, "ram_gb": 0.05, "runtime": "OpenCV DNN (CPU)", "license": "MIT",
        "license_url": "https://github.com/opencv/opencv_zoo/blob/main/models/face_detection_yunet/LICENSE",
        "compat": "Any CPU.",
    },
]

# The vision-language / context model is not downloaded by ClipForge: it is served by a local
# OpenAI-compatible server the user runs (llama.cpp Vulkan build, LM Studio or Ollama). See MODEL_SETUP.md.
EXTERNAL_MODELS = [
    {
        "id": "local-vlm", "name": "Vision-language model (local server)",
        "purpose": "vision + context",
        "description": "Describes frames (expressions, on-screen text, gameplay events) and judges conversational "
                       "context. Recommended: Qwen2.5-VL 7B Q4_K_M (~6 GB VRAM) served by llama.cpp with Vulkan "
                       "on AMD GPUs. Optional — analysis works without it using audio, motion, face and transcript signals.",
        "runtime": "llama.cpp server (Vulkan) / LM Studio / Ollama", "license": "Depends on the model you load",
    }
]

BY_ID = {m["id"]: m for m in CATALOG}
RECOMMENDED = ["whisper-small", "ced-tiny", "silero-vad", "yunet-face"]
