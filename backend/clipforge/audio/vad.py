"""Speech segmentation: Silero VAD when installed, loudness-based fallback otherwise."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .io import SR, Wav

MAX_CHUNK = 14.0  # seconds; short chunks keep segment-level timestamps tight


def silero_segments(samples: np.ndarray, model_path: Path, offset: float = 0.0) -> list[tuple[float, float]]:
    import sherpa_onnx as so

    f = model_path if model_path.is_file() else next(model_path.glob("*.onnx"))
    cfg = so.VadModelConfig()
    cfg.silero_vad.model = str(f)
    cfg.silero_vad.min_silence_duration = 0.3
    cfg.silero_vad.min_speech_duration = 0.2
    cfg.silero_vad.max_speech_duration = MAX_CHUNK
    cfg.sample_rate = SR
    vad = so.VoiceActivityDetector(cfg, buffer_size_in_seconds=120)
    win = cfg.silero_vad.window_size
    out: list[tuple[float, float]] = []

    def drain() -> None:
        while not vad.empty():
            seg = vad.front
            out.append((offset + seg.start / SR, offset + (seg.start + len(seg.samples)) / SR))
            vad.pop()

    for i in range(0, len(samples) - win + 1, win):
        vad.accept_waveform(samples[i:i + win])
        drain()
    vad.flush()
    drain()
    return out


def energy_segments(rms_db: np.ndarray, hop: float) -> list[tuple[float, float]]:
    """Fallback: speech-ish regions are frames well above the noise floor."""
    if len(rms_db) == 0:
        return []
    floor = np.percentile(rms_db, 10)
    thr = max(floor + 9.0, -50.0)
    active = rms_db > thr
    segs, start, gap = [], None, 0
    max_gap = int(0.35 / hop)
    for i, a in enumerate(active):
        if a:
            if start is None:
                start = i
            gap = 0
        elif start is not None:
            gap += 1
            if gap > max_gap:
                segs.append((start * hop, (i - gap + 1) * hop))
                start = None
    if start is not None:
        segs.append((start * hop, len(active) * hop))
    out = []
    for a, b in segs:
        if b - a < 0.25:
            continue
        while b - a > MAX_CHUNK:  # hard-split very long regions
            out.append((a, a + MAX_CHUNK))
            a += MAX_CHUNK
        out.append((a, b))
    return out


def speech_segments(wav: Wav, rms_db: np.ndarray, hop: float, vad_model: Path | None,
                    on_progress=None) -> tuple[list[tuple[float, float]], str]:
    if vad_model is not None:
        try:
            segs: list[tuple[float, float]] = []
            for t, block in wav.blocks(120.0):
                segs += silero_segments(block, vad_model, offset=t)
                if on_progress:
                    on_progress(min(1.0, (t + 120.0) / max(wav.duration, 1e-6)))
            return _merge_touching(segs), "silero"
        except Exception:  # noqa: BLE001 - fall back rather than fail the analysis
            pass
    return energy_segments(rms_db, hop), "energy"


def _merge_touching(segs: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Blocks are processed independently; rejoin a segment split exactly at a block edge."""
    out: list[tuple[float, float]] = []
    for a, b in sorted(segs):
        if out and a - out[-1][1] < 0.05 and b - out[-1][0] <= MAX_CHUNK:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return out
