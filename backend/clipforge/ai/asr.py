"""Speech recognition providers behind one interface.

`word_timing` tells the rest of the app the truth about timestamps:
  "word"      – the model produced per-word times (faster-whisper).
  "estimated" – only chunk-level times are real; word times are interpolated inside
                each short voice-activity chunk (sherpa-onnx Whisper exports).
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

import numpy as np

from ..audio.io import SR, Wav
from ..errors import ModelError
from ..hardware import threads


@dataclass
class Segment:
    start: float
    end: float
    text: str
    language: str | None = None
    words: list[dict] = field(default_factory=list)  # {w, start, end}


@dataclass
class TranscriptResult:
    language: str | None
    segments: list[Segment]
    word_timing: str
    provider: str
    model: str


class ASRProvider(Protocol):
    word_timing: str

    def transcribe(self, wav: Wav, chunks: list[tuple[float, float]], language: str | None,
                   on_progress: Callable[[float, str], None]) -> TranscriptResult: ...

    def transcribe_chunk(self, samples: np.ndarray) -> str: ...


_SENT = re.compile(r"(?<=[.!?…。？！])\s+")


def interpolate_words(text: str, start: float, end: float) -> list[dict]:
    """Spread words across [start, end] in proportion to their length. Clearly an estimate."""
    toks = text.split()
    if not toks:
        return []
    weights = [len(t) + 1.5 for t in toks]
    total = sum(weights)
    out, t = [], start
    for tok, w in zip(toks, weights):
        d = (end - start) * w / total
        out.append({"w": tok, "start": round(t, 3), "end": round(t + d, 3)})
        t += d
    return out


def split_sentences(text: str, start: float, end: float, language: str | None) -> list[Segment]:
    """Split one recognised chunk into sentence segments, sharing time by text length."""
    text = " ".join(text.split())
    if not text:
        return []
    parts = [p for p in _SENT.split(text) if p.strip()]
    total = sum(len(p) for p in parts) or 1
    out, t = [], start
    for p in parts:
        d = (end - start) * len(p) / total
        out.append(Segment(round(t, 3), round(t + d, 3), p, language, interpolate_words(p, t, t + d)))
        t += d
    return out


class SherpaWhisper:
    word_timing = "estimated"

    def __init__(self, meta: dict, path: Path):
        self.meta = meta
        d = path / meta["archive_dir"]
        size = meta["id"].replace("whisper-", "")
        self.files = {k: d / f"{size}-{k}" for k in ("encoder.int8.onnx", "decoder.int8.onnx", "tokens.txt")}
        missing = [str(f) for f in self.files.values() if not f.exists()]
        if missing:
            raise ModelError(f"Speech model files are missing: {missing[0]}")
        self._rec: dict[str, object] = {}

    def _recognizer(self, language: str):
        import sherpa_onnx as so

        if language not in self._rec:
            self._rec.clear()  # keep a single model in memory
            self._rec[language] = so.OfflineRecognizer.from_whisper(
                encoder=str(self.files["encoder.int8.onnx"]), decoder=str(self.files["decoder.int8.onnx"]),
                tokens=str(self.files["tokens.txt"]), language=language, task="transcribe",
                num_threads=threads())
        return self._rec[language]

    def _decode(self, samples: np.ndarray, language: str) -> tuple[str, str | None]:
        rec = self._recognizer(language)
        st = rec.create_stream()
        st.accept_waveform(SR, samples)
        rec.decode_stream(st)
        return st.result.text.strip(), (getattr(st.result, "lang", "") or "").strip("<|>") or None

    def transcribe_chunk(self, samples: np.ndarray) -> str:
        return self._decode(samples, "")[0]

    def transcribe(self, wav, chunks, language, on_progress):
        lang = language
        if not lang:
            # Detect on the longest chunks; one fixed language avoids short chunks flipping to random languages.
            votes: Counter[str] = Counter()
            for a, b in sorted(chunks, key=lambda c: c[0] - c[1])[:6]:
                _, detected = self._decode(wav.read(a, b), "")
                if detected:
                    votes[detected] += b - a
            lang = votes.most_common(1)[0][0] if votes else ""
        segments: list[Segment] = []
        total = sum(b - a for a, b in chunks) or 1.0
        done = 0.0
        for a, b in chunks:
            text = clean_text(self._decode(wav.read(a, b), lang or "")[0])
            if text:
                segments += split_sentences(text, a, b, lang or None)
            done += b - a
            on_progress(done / total, text[:120])
        return TranscriptResult(lang or None, segments, self.word_timing, "sherpa_whisper", self.meta["id"])


class FasterWhisper:
    word_timing = "word"

    def __init__(self, meta: dict, path: Path):
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise ModelError("faster-whisper is not installed.") from e
        self.meta = meta
        self.model = WhisperModel(str(path), device="cpu", compute_type="int8", cpu_threads=threads())

    def transcribe_chunk(self, samples: np.ndarray) -> str:
        segs, _ = self.model.transcribe(samples, beam_size=1)
        return " ".join(s.text.strip() for s in segs)

    def transcribe(self, wav, chunks, language, on_progress):
        # faster-whisper runs its own VAD; whole-file decode keeps cross-chunk context.
        segs, info = self.model.transcribe(str(wav.path), language=language or None, word_timestamps=True,
                                           vad_filter=True, beam_size=5)
        out: list[Segment] = []
        for s in segs:
            words = [{"w": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)}
                     for w in (s.words or []) if w.word.strip()]
            if not clean_text(s.text):
                continue
            out.append(Segment(round(s.start, 3), round(s.end, 3), s.text.strip(), info.language, words))
            on_progress(min(1.0, s.end / max(wav.duration, 1e-6)), s.text.strip()[:120])
        return TranscriptResult(info.language, out, self.word_timing, "faster_whisper", self.meta["id"])


_STOCK = {"thank you.", "thanks for watching!", "thank you for watching.", "you", ".", "bye.", "bye"}


def clean_text(text: str) -> str:
    """Remove Whisper's non-speech annotations ("(laughs)", "[MUSIC]", "♪") and stock phrases it
    hallucinates on audio with no speech. Returns "" when nothing spoken is left."""
    t = re.sub(r"[\[(（][^\])）]*[\])）]?", " ", text)
    t = re.sub(r"[♪♫]+", " ", t)
    t = " ".join(t.split()).strip(" -")
    if t.lower() in _STOCK or not re.search(r"\w", t):
        return ""
    return t


PROVIDERS = {"sherpa_whisper": SherpaWhisper, "faster_whisper": FasterWhisper}


def load_asr(meta: dict, path: Path) -> ASRProvider:
    cls = PROVIDERS.get(meta["provider"])
    if not cls:
        raise ModelError(f"No speech provider named {meta['provider']}")
    return cls(meta, path)
