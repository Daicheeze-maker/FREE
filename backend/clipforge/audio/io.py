"""Audio extraction and memory-light access to the analysis WAV (16 kHz mono s16)."""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from ..media import ffmpeg as ff

SR = 16000


def extract_wav(src: str | Path, out: str | Path, duration: float, on_progress=None, check=None,
                normalize: bool = False) -> None:
    """Decode the first audio stream to 16 kHz mono PCM for analysis."""
    af = ["-af", "dynaudnorm=f=250:g=15"] if normalize else []
    ff.run(["-i", str(src), "-vn", "-map", "0:a:0", "-ac", "1", "-ar", str(SR), *af,
            "-c:a", "pcm_s16le", str(out)], duration=duration, on_progress=on_progress, check=check)


class Wav:
    """Memory-mapped PCM so hour-long videos are not loaded into RAM at once."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        with wave.open(str(self.path), "rb") as w:
            if w.getframerate() != SR or w.getnchannels() != 1 or w.getsampwidth() != 2:
                raise ValueError("analysis wav must be 16 kHz mono s16")
            self.n = w.getnframes()
        # data chunk is at the end of the header; locate it rather than assuming 44 bytes
        with open(self.path, "rb") as f:
            head = f.read(4096)
        self._offset = head.index(b"data") + 8
        self._mm = np.memmap(self.path, dtype="<i2", mode="r", offset=self._offset, shape=(self.n,))

    @property
    def duration(self) -> float:
        return self.n / SR

    def read(self, start: float, end: float) -> np.ndarray:
        a, b = max(0, int(start * SR)), min(self.n, int(end * SR))
        return (np.asarray(self._mm[a:b], dtype=np.float32) / 32768.0) if b > a else np.zeros(0, np.float32)

    def blocks(self, seconds: float = 60.0):
        t = 0.0
        while t < self.duration:
            yield t, self.read(t, t + seconds)
            t += seconds

    def close(self) -> None:
        mm = getattr(self._mm, "_mmap", None)
        del self._mm
        if mm is not None:
            mm.close()
