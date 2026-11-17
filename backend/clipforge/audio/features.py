"""Signal-level audio analysis: loudness curve, waveform peaks, spikes, pauses, vocal energy."""
from __future__ import annotations

import numpy as np

from .io import SR, Wav

HOP = 0.05  # seconds per loudness frame


def loudness_curve(wav: Wav, on_progress=None) -> np.ndarray:
    """RMS level in dBFS per 50 ms frame, computed block by block."""
    n = int(HOP * SR)
    parts = []
    for t, block in wav.blocks(120.0):
        usable = len(block) // n * n
        if usable:
            frames = block[:usable].reshape(-1, n)
            rms = np.sqrt(np.mean(frames * frames, axis=1) + 1e-12)
            parts.append(20 * np.log10(rms + 1e-9))
        if on_progress:
            on_progress(min(1.0, (t + 120.0) / max(wav.duration, 1e-6)))
    return np.concatenate(parts) if parts else np.zeros(0, np.float32)


def waveform_peaks(rms_db: np.ndarray, points: int = 2000) -> list[float]:
    """Compact 0..1 envelope for timeline display."""
    if len(rms_db) == 0:
        return []
    lin = np.clip((rms_db + 60) / 60, 0, 1)
    idx = np.linspace(0, len(lin), min(points, len(lin)) + 1).astype(int)
    return [round(float(lin[a:b].max()), 3) if b > a else 0.0 for a, b in zip(idx[:-1], idx[1:])]


def energy_spikes(rms_db: np.ndarray, speech: list[tuple[float, float]] | None = None) -> list[dict]:
    """Sudden loud moments.

    Someone simply starting to talk after a quiet stretch is not a spike, so a frame counts only if it is
    (a) far above the local 10 s median AND (b) either outside detected speech (a bang, a crash, a burst of
    laughter) or clearly louder than this video's normal loud level (a shout).
    """
    if len(rms_db) < 40:
        return []
    k = int(10 / HOP)
    pad = np.pad(rms_db, (k // 2, k // 2), mode="edge")
    step = int(0.5 / HOP)
    centers = np.arange(0, len(rms_db), step)
    med = np.array([np.median(pad[c:c + k]) for c in centers])
    baseline = np.interp(np.arange(len(rms_db)), centers, med)
    delta = rms_db - baseline
    active = rms_db[rms_db > -50.0]
    usual_loud = float(np.percentile(active, 90)) if len(active) else 0.0
    in_speech = np.zeros(len(rms_db), bool)
    for a, b in speech or []:
        in_speech[max(0, int((a - 0.1) / HOP)):int((b + 0.1) / HOP)] = True
    loud = (delta > 12.0) & (rms_db > -30.0) & (~in_speech | (rms_db > usual_loud + 6.0))
    events, i = [], 0
    while i < len(loud):
        if loud[i]:
            j = i
            while j < len(loud) and (loud[j] or (j + 2 < len(loud) and loud[j + 1:j + 3].any())):
                j += 1
            over = float(max(rms_db[i:j].max() - usual_loud, 0.0))
            peak = float(delta[i:j].max())
            events.append({"kind": "energy_spike", "modality": "audio", "start": round(i * HOP, 2),
                           "end": round(j * HOP, 2),
                           "intensity": round(min(1.0, 0.4 + (peak - 12) / 40 + over / 12), 3),
                           "confidence": 0.6, "label": f"sudden loud sound (+{peak:.0f} dB over the local level)"})
            i = j
        else:
            i += 1
    return events


def pauses(speech: list[tuple[float, float]], duration: float, rms_db: np.ndarray | None = None,
           min_gap: float = 2.5) -> list[dict]:
    """Long *quiet* gaps between speech — awkward pauses, or natural places to cut.

    A gap filled with laughter, music or game sound is not a pause, so the gap must also be
    much quieter than the speech around it.
    """
    out = []
    speech_level = None
    if rms_db is not None and len(rms_db) and speech:
        lv = [float(np.median(rms_db[int(a / HOP):max(int(a / HOP) + 1, int(b / HOP))])) for a, b in speech]
        speech_level = float(np.median(lv))
    for (a0, a1), (b0, b1) in zip(speech, speech[1:]):
        gap = b0 - a1
        if gap < min_gap:
            continue
        if speech_level is not None:
            seg = rms_db[int(a1 / HOP):int(b0 / HOP)]
            if len(seg) and float(np.percentile(seg, 70)) > speech_level - 15.0:
                continue
        out.append({"kind": "pause", "modality": "audio", "start": round(a1, 2), "end": round(b0, 2),
                    "intensity": round(min(1.0, gap / 8.0), 3), "confidence": 0.8,
                    "label": f"{gap:.1f}s of quiet between speech"})
    return out


def vocal_energy_events(rms_db: np.ndarray, speech: list[tuple[float, float]]) -> list[dict]:
    """Speech segments much louder than this speaker track's norm (raised voice / excitement)."""
    levels = []
    for a, b in speech:
        seg = rms_db[int(a / HOP):max(int(a / HOP) + 1, int(b / HOP))]
        levels.append(float(np.percentile(seg, 90)) if len(seg) else -90.0)
    if len(levels) < 4:
        return []
    mu, sd = float(np.median(levels)), float(np.std(levels)) or 1.0
    out = []
    for (a, b), lv in zip(speech, levels):
        z = (lv - mu) / max(sd, 2.0)
        if z > 1.5 and lv - mu > 5.0:
            out.append({"kind": "raised_voice", "modality": "audio", "start": round(a, 2), "end": round(b, 2),
                        "intensity": round(min(1.0, z / 4.0 + 0.3), 3), "confidence": 0.55,
                        "label": f"vocal energy +{lv - mu:.0f} dB above the usual speaking level"})
    return out


def clarity(rms_db: np.ndarray, speech: list[tuple[float, float]], start: float, end: float) -> float:
    """0..1 estimate of how clean the speech is in a window: speech level vs. noise floor, minus clipping."""
    a, b = int(start / HOP), int(end / HOP)
    seg = rms_db[a:b]
    if len(seg) == 0:
        return 0.0
    mask = np.zeros(len(seg), bool)
    for s0, s1 in speech:
        if s1 > start and s0 < end:
            mask[max(0, int((s0 - start) / HOP)):int((s1 - start) / HOP)] = True
    if not mask.any():
        return 0.2
    sp = float(np.median(seg[mask]))
    noise = float(np.percentile(seg[~mask], 50)) if (~mask).sum() > 4 else float(np.percentile(rms_db, 5))
    snr = sp - noise
    clipped = float((seg > -1.0).mean())
    return float(np.clip(snr / 30.0, 0.1, 1.0) * (1.0 - min(0.5, clipped * 5)))
