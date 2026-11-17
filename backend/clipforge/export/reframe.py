"""Smart reframing: choose a stable crop path for a target aspect ratio.

The crop follows a subject only as much as needed. Within a shot the path is either
held still (subject barely moves) or heavily smoothed; it may jump only at scene cuts.
"""
from __future__ import annotations

import numpy as np

ASPECTS = {"9:16": 9 / 16, "16:9": 16 / 9, "1:1": 1.0}
HEIGHTS = {"1080p": {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)},
           "720p": {"9:16": (720, 1280), "16:9": (1280, 720), "1:1": (720, 720)}}


def _even(v: float) -> int:
    return max(2, int(round(v / 2)) * 2)


def output_size(aspect: str, resolution: str, src_w: int, src_h: int, crop_w: int, crop_h: int) -> tuple[int, int]:
    if aspect == "original" or aspect not in ASPECTS:
        if resolution == "original":
            return _even(src_w), _even(src_h)
        short = 1080 if resolution == "1080p" else 720
        scale = short / min(src_w, src_h)
        return _even(src_w * scale), _even(src_h * scale)
    if resolution == "original":
        return _even(crop_w), _even(crop_h)
    return HEIGHTS[resolution][aspect]


def crop_box(src_w: int, src_h: int, aspect: str, zoom: float = 1.0) -> tuple[int, int]:
    ar = ASPECTS[aspect]
    if src_w / src_h > ar:
        h, w = src_h, src_h * ar
    else:
        w, h = src_w, src_w / ar
    zoom = max(1.0, min(4.0, zoom))
    return _even(min(src_w, w / zoom) - 1), _even(min(src_h, h / zoom) - 1)


def _main_face_targets(samples: list[dict]) -> tuple[np.ndarray, float]:
    """Follow one face consistently: start with the biggest, then stay with the nearest."""
    xs = np.full((len(samples), 2), np.nan)
    last = None
    for i, e in enumerate(samples):
        faces = e["faces"]
        if not faces:
            continue
        if last is None:
            f = max(faces, key=lambda f: f[2] * f[3] * f[4])
        else:
            f = min(faces, key=lambda f: (f[0] - last[0]) ** 2 + (f[1] - last[1]) ** 2 - 0.5 * f[2] * f[3])
        last = f
        xs[i] = (f[0], f[1] - f[3] * 0.1)  # aim slightly above centre: keeps foreheads in frame
    ratio = float(np.mean(~np.isnan(xs[:, 0]))) if len(samples) else 0.0
    return xs, ratio


def _fill(a: np.ndarray, default: float) -> np.ndarray:
    idx = np.arange(len(a))
    ok = ~np.isnan(a)
    if not ok.any():
        return np.full(len(a), default)
    return np.interp(idx, idx[ok], a[ok])


def _smooth(vals: np.ndarray, dt: float, tau: float = 1.4) -> np.ndarray:
    """Zero-phase exponential smoothing (forward + backward) — no lag, no jitter."""
    if len(vals) < 2:
        return vals
    alpha = 1 - np.exp(-dt / tau)
    out = vals.astype(float).copy()
    for seq in (range(1, len(out)), range(len(out) - 2, -1, -1)):
        for i in seq:
            prev = out[i - 1] if seq.step == 1 else out[i + 1]
            out[i] = prev + alpha * (out[i] - prev)
    return out


def plan(mode: str, aspect: str, manual: dict, src_w: int, src_h: int, start: float, end: float,
         track: list[dict], scenes: list[tuple[float, float]]) -> dict:
    """Crop plan in normalised units: box size (w,h) and keyframes of the box centre over clip time."""
    if aspect == "original" or aspect not in ASPECTS or mode == "original":
        return {"mode": "original", "effective": "original", "box": [1.0, 1.0], "keys": [[0.0, 0.5, 0.5]],
                "note": "Original framing is kept."}
    if mode == "fit_blur":
        return {"mode": mode, "effective": "fit_blur", "box": [1.0, 1.0], "keys": [[0.0, 0.5, 0.5]],
                "note": "Whole frame is kept on a blurred background — nothing is cropped."}
    zoom = float(manual.get("zoom", 1.0)) if mode == "manual" else 1.0
    cw, ch = crop_box(src_w, src_h, aspect, zoom)
    bw, bh = cw / src_w, ch / src_h

    def clamp(x: float, y: float) -> tuple[float, float]:
        return (float(np.clip(x, bw / 2, 1 - bw / 2)), float(np.clip(y, bh / 2, 1 - bh / 2)))

    def static(x: float, y: float, effective: str, note: str) -> dict:
        cx, cy = clamp(x, y)
        return {"mode": mode, "effective": effective, "box": [round(bw, 5), round(bh, 5)],
                "keys": [[0.0, round(cx, 4), round(cy, 4)]], "note": note}

    if mode == "manual":
        return static(float(manual.get("x", 0.5)), float(manual.get("y", 0.5)), "manual", "Manual crop.")
    if mode == "center":
        return static(0.5, 0.5, "center", "Centered crop.")

    samples = [e for e in track if start - 0.01 <= e["t"] <= end + 0.01]
    if len(samples) < 2:
        return static(0.5, 0.5, "center", "No visual analysis for this range — using a centered crop.")
    faces, face_ratio = _main_face_targets(samples)
    if face_ratio >= 0.35 or (mode == "face" and face_ratio > 0):
        tx, ty = _fill(faces[:, 0], 0.5), _fill(faces[:, 1], 0.5)
        effective, note = "face", f"Following the main face (visible in {face_ratio:.0%} of sampled frames)."
    elif mode == "face":
        return static(0.5, 0.5, "center", "No face was detected in this clip — using a centered crop.")
    else:
        motion = np.array([e["motion"] for e in samples])
        if float(motion.mean()) > 0.004:
            tx = np.array([e["mc"][0] for e in samples])
            ty = np.array([e["mc"][1] for e in samples])
            effective, note = "motion", "No consistent face — following the area with the most on-screen activity."
        else:
            return static(0.5, 0.5, "center", "No face and little movement — using a centered crop.")

    times = np.array([e["t"] for e in samples])
    dt = float(np.median(np.diff(times))) if len(times) > 1 else 0.5
    tau = 1.4 if effective == "face" else 3.0  # activity centroids are noisier: move even less
    cuts = [c for c, _ in scenes if start < c < end]
    bounds = [start, *cuts, end + 1e-6]
    keys: list[list[float]] = []
    for a, b in zip(bounds, bounds[1:]):
        m = (times >= a) & (times < b)
        if not m.any():
            continue
        sx, sy, st = tx[m], ty[m], times[m]
        # A subject that stays within a small zone gets a locked-off shot.
        if np.ptp(sx) < bw * 0.22 and np.ptp(sy) < bh * 0.22:
            px = np.full(len(sx), float(np.median(sx)))
            py = np.full(len(sy), float(np.median(sy)))
        else:
            px, py = _smooth(sx, dt, tau), _smooth(sy, dt, tau)
        seg = [[max(0.0, float(t) - start), *clamp(float(x), float(y))] for t, x, y in zip(st, px, py)]
        seg[0][0] = max(0.0, a - start)  # the new framing begins exactly on the cut
        keys += _simplify(seg, tol=0.004)
    out = []
    for k in keys:
        k = [round(k[0], 3), round(k[1], 4), round(k[2], 4)]
        if out and k[0] <= out[-1][0]:
            k[0] = round(out[-1][0] + 0.001, 3)
        out.append(k)
    return {"mode": mode, "effective": effective, "box": [round(bw, 5), round(bh, 5)],
            "keys": out or [[0.0, 0.5, 0.5]], "note": note, "cuts": [round(c - start, 3) for c in cuts]}


def _simplify(keys: list[list[float]], tol: float) -> list[list[float]]:
    """Drop keyframes that linear interpolation already reproduces (keeps the ffmpeg expression short)."""
    if len(keys) <= 2:
        return keys if len(keys) < 2 or keys[0][1:] != keys[1][1:] else keys[:1]
    out = [keys[0]]
    anchor = 0
    for i in range(2, len(keys)):
        a, b = keys[anchor], keys[i]
        ok = True
        for j in range(anchor + 1, i):
            f = (keys[j][0] - a[0]) / max(1e-6, b[0] - a[0])
            if abs(a[1] + f * (b[1] - a[1]) - keys[j][1]) > tol or abs(a[2] + f * (b[2] - a[2]) - keys[j][2]) > tol:
                ok = False
                break
        if not ok:
            out.append(keys[i - 1])
            anchor = i - 1
    out.append(keys[-1])
    if all(abs(k[1] - out[0][1]) < tol and abs(k[2] - out[0][2]) < tol for k in out):
        return out[:1]
    return out[:80]


def expr(keys: list[list[float]], col: int, scale: float, cuts: list[float] | None = None) -> str:
    """FFmpeg expression: piecewise-linear value over t (hard switch at cuts)."""
    if len(keys) == 1:
        return f"{keys[0][col] * scale:.2f}"
    cuts = cuts or []
    e = f"{keys[-1][col] * scale:.2f}"
    for a, b in reversed(list(zip(keys, keys[1:]))):
        va, vb = a[col] * scale, b[col] * scale
        if any(abs(b[0] - c) < 0.002 for c in cuts) or abs(vb - va) < 0.01:
            piece = f"{va:.2f}"  # hold until the cut, then jump
        else:
            piece = f"{va:.2f}+({vb - va:.2f})*(t-{a[0]:.3f})/{max(1e-3, b[0] - a[0]):.3f}"
        e = f"if(lt(t,{b[0]:.3f}),{piece},{e})"
    return e
