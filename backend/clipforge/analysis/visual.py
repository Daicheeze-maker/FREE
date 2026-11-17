"""Visual intelligence without an expensive model: scenes, motion, faces.

A cheap pass inspects frames at the profile's sampling rate (decoded once, at 320 px,
through an FFmpeg pipe). Only timestamps that look promising are later handed to the
optional vision-language model.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
import numpy as np

from ..errors import CancelledError
from ..media import ffmpeg as ff

ANALYSIS_W = 320


def detect_scenes(path: str | Path, duration: float, downscale: int, on_progress, check) -> list[tuple[float, float]]:
    """PySceneDetect content detection, run in 20 s slices so progress and cancel are real."""
    from scenedetect import ContentDetector, SceneManager, open_video

    video = open_video(str(path))
    sm = SceneManager()
    sm.add_detector(ContentDetector(threshold=27.0, min_scene_len=int(max(video.frame_rate, 1) * 0.6)))
    sm.auto_downscale = False
    sm.downscale = max(1, downscale)
    t = 0.0
    while t < duration:
        check()
        n = sm.detect_scenes(video, duration=20.0)
        t += 20.0
        on_progress(min(1.0, t / duration))
        if not n:
            break
    scenes = [(s.get_seconds(), e.get_seconds()) for s, e in sm.get_scene_list(start_in_scene=True)]
    return scenes or [(0.0, duration)]


class FaceDetector:
    def __init__(self, model_path: Path):
        f = model_path if model_path.is_file() else next(model_path.glob("*.onnx"))
        self._det = cv2.FaceDetectorYN.create(str(f), "", (ANALYSIS_W, 180), score_threshold=0.7)
        self._size = None

    def detect(self, frame: np.ndarray) -> list[list[float]]:
        """Faces as [cx, cy, w, h, score], all normalised to 0..1 of the frame."""
        h, w = frame.shape[:2]
        if self._size != (w, h):
            self._det.setInputSize((w, h))
            self._size = (w, h)
        _, faces = self._det.detect(frame)
        out = []
        for f in faces if faces is not None else []:
            x, y, fw, fh, score = float(f[0]), float(f[1]), float(f[2]), float(f[3]), float(f[-1])
            out.append([round((x + fw / 2) / w, 4), round((y + fh / 2) / h, 4),
                        round(fw / w, 4), round(fh / h, 4), round(score, 3)])
        return out


def sample_frames(path: str | Path, width: int, height: int, duration: float, fps: float,
                  face_detector: FaceDetector | None, on_progress, check) -> list[dict]:
    """Per-sample visual track: {t, motion, mc:[x,y] motion centroid, faces:[...]}."""
    aw = ANALYSIS_W
    ah = max(2, int(round(height * aw / max(width, 1) / 2)) * 2)
    cmd = [ff.ffmpeg_bin(), "-hide_banner", "-nostdin", "-v", "error", "-i", str(path), "-an",
           "-vf", f"fps={fps},scale={aw}:{ah}", "-pix_fmt", "bgr24", "-f", "rawvideo", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=ff.NO_WINDOW)
    track: list[dict] = []
    prev = None
    size = aw * ah * 3
    i = 0
    try:
        while True:
            buf = proc.stdout.read(size)  # type: ignore[union-attr]
            if len(buf) < size:
                break
            check()
            frame = np.frombuffer(buf, np.uint8).reshape(ah, aw, 3)
            gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (5, 5), 0)
            motion, mc = 0.0, [0.5, 0.5]
            if prev is not None:
                diff = cv2.absdiff(gray, prev)
                motion = float(diff.mean()) / 255.0
                mask = (diff > 18).astype(np.float32)
                m = mask.sum()
                if m > aw * ah * 0.002:
                    ys, xs = np.nonzero(mask)
                    mc = [round(float(xs.mean()) / aw, 4), round(float(ys.mean()) / ah, 4)]
            prev = gray
            t = i / fps
            entry = {"t": round(t, 3), "motion": round(motion, 5), "mc": mc,
                     "faces": face_detector.detect(frame) if face_detector else []}
            track.append(entry)
            i += 1
            if i % 10 == 0:
                on_progress(min(1.0, t / max(duration, 1e-6)))
    except CancelledError:
        proc.kill()
        raise
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
    return track


def visual_events(track: list[dict], scenes: list[tuple[float, float]], fps: float) -> list[dict]:
    """Derive events from the visual track: sudden movement, rapid cutting, face close-ups/reactions."""
    events: list[dict] = []
    if len(track) < 4:
        return events
    cut_times = [s for s, _ in scenes[1:]]

    def near_cut(t: float) -> bool:
        return any(abs(t - c) <= 1.0 / fps + 0.05 for c in cut_times)

    # Motion spikes: far above the *local* (20 s) motion level, short-lived, and not just the frame
    # difference caused by a cut. Constantly busy footage therefore does not count as "sudden".
    motion = np.array([0.0 if near_cut(e["t"]) else e["motion"] for e in track])
    half = max(2, int(10 * fps))
    z = np.zeros(len(motion))
    for i in range(len(motion)):
        w = motion[max(0, i - half):i + half + 1]
        base = float(np.median(w))
        mad = float(np.median(np.abs(w - base)))
        z[i] = (motion[i] - base) / (1.4826 * mad + 0.004)
    i = 0
    while i < len(track):
        if z[i] > 5 and motion[i] > 0.02:
            j = i
            while j + 1 < len(track) and z[j + 1] > 2.5:
                j += 1
            peak = float(z[i:j + 1].max())
            if track[j]["t"] - track[i]["t"] <= 4.0:
                events.append({"kind": "sudden_movement", "modality": "visual", "start": track[i]["t"],
                               "end": round(track[j]["t"] + 1 / fps, 3),
                               "intensity": round(min(1.0, 0.35 + peak / 40), 3), "confidence": 0.55,
                               "label": "sudden on-screen movement"})
            i = j + 1
        else:
            i += 1

    # Rapid cutting: 3+ cuts inside 6 seconds.
    for k in range(len(cut_times) - 2):
        if cut_times[k + 2] - cut_times[k] <= 6.0:
            if events and events[-1]["kind"] == "rapid_cuts" and cut_times[k] <= events[-1]["end"]:
                events[-1]["end"] = cut_times[k + 2]
            else:
                events.append({"kind": "rapid_cuts", "modality": "visual", "start": cut_times[k],
                               "end": cut_times[k + 2], "intensity": 0.45, "confidence": 0.7,
                               "label": "rapid camera/scene changes"})

    # Face close-ups: the largest face suddenly fills much more of the frame than usual.
    sizes = np.array([max((f[3] for f in e["faces"]), default=0.0) for e in track])
    present = sizes > 0
    if present.sum() >= 4:
        usual = float(np.median(sizes[present]))
        i = 0
        while i < len(track):
            if sizes[i] > max(0.3, usual * 1.6):
                j = i
                while j + 1 < len(track) and sizes[j + 1] > max(0.3, usual * 1.4):
                    j += 1
                events.append({"kind": "face_closeup", "modality": "visual", "start": track[i]["t"],
                               "end": round(track[j]["t"] + 1 / fps, 3),
                               "intensity": round(min(1.0, float(sizes[i:j + 1].max()) + 0.2), 3),
                               "confidence": 0.6, "label": "face close-up"})
                i = j + 1
            else:
                i += 1
    return events


def window_stats(track: list[dict], start: float, end: float) -> dict:
    """Visual summary of a time window, used by clip scoring."""
    w = [e for e in track if start <= e["t"] <= end]
    if not w:
        return {"face_ratio": 0.0, "motion": 0.0, "faces_max": 0}
    return {
        "face_ratio": sum(1 for e in w if e["faces"]) / len(w),
        "motion": float(np.mean([e["motion"] for e in w])),
        "faces_max": max(len(e["faces"]) for e in w),
    }
