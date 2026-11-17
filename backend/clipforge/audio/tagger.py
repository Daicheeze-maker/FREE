"""AudioSet tagging (laughter, screams, music, ...) — independent of transcription."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .io import SR

# AudioSet label -> ClipForge event kind
LABEL_KINDS = {
    "laughter": ["Laughter", "Baby laughter", "Giggle", "Snicker", "Belly laugh", "Chuckle, chortle"],
    "scream": ["Screaming", "Shout", "Yell", "Children shouting", "Bellow", "Whoop", "Battle cry"],
    "cheering": ["Cheering", "Applause", "Clapping", "Crowd"],
    "gasp": ["Gasp"],
    "crying": ["Crying, sobbing", "Baby cry, infant cry", "Whimper", "Wail, moan"],
    "music": ["Music", "Musical instrument", "Singing", "Background music", "Theme music"],
    "impact": ["Explosion", "Gunshot, gunfire", "Machine gun", "Bang", "Slam", "Smash, crash", "Boom",
               "Glass", "Shatter", "Burst, pop", "Thump, thud", "Eruption", "Fireworks"],
    "speech": ["Speech", "Male speech, man speaking", "Female speech, woman speaking", "Conversation",
               "Narration, monologue", "Child speech, kid speaking"],
}
# minimum probability for a window to count toward an event of that kind
THRESHOLDS = {"laughter": 0.25, "scream": 0.3, "cheering": 0.3, "gasp": 0.25, "crying": 0.3,
              "music": 0.45, "impact": 0.3}


class Tagger:
    def __init__(self, meta: dict, path: Path, threads: int = 2):
        import sherpa_onnx as so

        d = path / meta["archive_dir"]
        model = d / "model.int8.onnx"
        cfg = so.AudioTaggingConfig(
            model=so.AudioTaggingModelConfig(ced=str(model), num_threads=threads),
            labels=str(d / "class_labels_indices.csv"), top_k=12)
        self._tagger = so.AudioTagging(cfg)
        self._kind_of = {label: kind for kind, labels in LABEL_KINDS.items() for label in labels}

    def tag(self, samples: np.ndarray) -> dict[str, float]:
        """Probability per event kind for one window (max over the kind's labels)."""
        st = self._tagger.create_stream()
        st.accept_waveform(SR, samples)
        out: dict[str, float] = {}
        for e in self._tagger.compute(st):
            kind = self._kind_of.get(e.name)
            if kind:
                out[kind] = max(out.get(kind, 0.0), float(e.prob))
        return out


def windows_to_events(times: list[float], probs: list[dict[str, float]], win: float) -> list[dict]:
    """Merge consecutive windows above threshold into timed events."""
    events = []
    for kind, thr in THRESHOLDS.items():
        cur = None
        for t, p in zip(times, probs):
            v = p.get(kind, 0.0)
            if v >= thr:
                if cur and t <= cur["end"] + 1e-6:
                    cur["end"] = t + win
                    cur["vals"].append(v)
                else:
                    if cur:
                        events.append(cur)
                    cur = {"kind": kind, "start": t, "end": t + win, "vals": [v]}
        if cur:
            events.append(cur)
    out = []
    for e in events:
        vals = e.pop("vals")
        peak, mean = max(vals), float(np.mean(vals))
        out.append({**e, "modality": "audio", "intensity": round(min(1.0, 0.6 * peak + 0.4 * mean), 3),
                    "confidence": round(peak, 3), "label": f"{e['kind']} (audio tagger)"})
    return out
