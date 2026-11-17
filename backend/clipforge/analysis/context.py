"""Optional language-model passes: frame description and conversational context.

Used only when the user has enabled a local OpenAI-compatible server. Failures here
are reported and the analysis continues with the signal-based engine.
"""
from __future__ import annotations

import subprocess

from ..ai.llm import LLMClient
from ..errors import ModelError
from ..media import ffmpeg as ff
from .clips import AFFINITY, fmt_t

FRAME_SYSTEM = (
    "You analyse single video frames for a video clipping tool. Reply with JSON only: "
    '{"description": str, "people": int, "expression": str, "on_screen_text": str, '
    '"event": str, "interest": 0-10}. "interest" is how visually notable the frame is. '
    "Describe only what is visible. Use an empty string when something is absent."
)

CONTEXT_SYSTEM = (
    "You find self-contained moments in a video transcript for short-form clips. "
    "Lines look like `[index] time text`. Lines in parentheses are detected non-speech events. "
    "The transcript may be English, Tagalog or Taglish; do not translate it. "
    "A good moment keeps the whole interaction: setup, punchline or answer, and the reaction. "
    "Reply with JSON only: a list of objects "
    '{"start_index": int, "end_index": int, "category": one of %s, "title": str (same language as the speech), '
    '"reason": str, "interest": 0-10, "complete": bool}. Return [] if nothing stands out.'
) % sorted(AFFINITY)


def frame_jpeg(src: str, t: float, width: int = 640) -> bytes:
    r = subprocess.run([ff.ffmpeg_bin(), "-hide_banner", "-nostdin", "-v", "error", "-ss", f"{max(0, t):.3f}",
                        "-i", src, "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "5",
                        "-f", "image2pipe", "-c:v", "mjpeg", "-"],
                       capture_output=True, timeout=120, creationflags=ff.NO_WINDOW)
    if r.returncode != 0 or not r.stdout:
        raise ModelError(f"Could not extract a frame at {t:.1f}s")
    return r.stdout


def pick_frame_times(events: list[dict], scenes: list[tuple[float, float]], budget: int) -> list[float]:
    """Spend the frame budget where something already looks promising, plus one frame per scene."""
    times: list[float] = []
    strong = sorted((e for e in events if e["modality"] != "speech" and e["kind"] not in ("pause", "music")),
                    key=lambda e: -e["intensity"])
    for e in strong[: max(1, budget // 3)]:
        mid = (e["start"] + e["end"]) / 2
        times += [mid, max(0.0, e["start"] - 1.0), e["end"] + 0.8]  # the event plus frames around it
    for a, b in scenes:
        times.append((a + b) / 2)
    out: list[float] = []
    for t in times:
        if all(abs(t - o) > 0.7 for o in out):
            out.append(round(t, 2))
        if len(out) >= budget:
            break
    return sorted(out)


def describe_frames(client: LLMClient, src: str, times: list[float], on_progress) -> list[dict]:
    events = []
    for i, t in enumerate(times):
        on_progress(i / max(1, len(times)), f"Vision model: frame at {fmt_t(t)}")
        data = client.chat_json(FRAME_SYSTEM, "Analyse this frame.", images=[frame_jpeg(src, t)], max_tokens=300)
        if not isinstance(data, dict):
            continue
        interest = float(data.get("interest") or 0)
        desc = str(data.get("description") or "").strip()
        events.append({
            "kind": "vlm_frame", "modality": "visual", "start": round(max(0.0, t - 0.5), 2), "end": round(t + 0.5, 2),
            "intensity": round(min(1.0, max(0.0, interest / 10.0)), 3), "confidence": 0.6,
            "label": desc[:300] or "frame described by the vision model",
            "data": {"expression": str(data.get("expression") or ""),
                     "on_screen_text": str(data.get("on_screen_text") or ""),
                     "event": str(data.get("event") or ""), "people": data.get("people")},
        })
    return events


def transcript_windows(segments: list[dict], events: list[dict], max_chars: int = 5000) -> list[str]:
    """Annotated transcript, split into overlapping windows that fit a small model's context."""
    notable = sorted((e for e in events if e["modality"] != "speech" and e["intensity"] >= 0.35
                      and e["kind"] != "music"), key=lambda e: e["start"])
    lines = []
    ei = 0
    for s in segments:
        while ei < len(notable) and notable[ei]["start"] <= s["start"]:
            e = notable[ei]
            desc = e["label"] if e["kind"] == "vlm_frame" else e["kind"].replace("_", " ")
            lines.append(f"({desc} at {fmt_t(e['start'])})")
            ei += 1
        lines.append(f"[{s['idx']}] {fmt_t(s['start'])} {s['text']}")
    windows, cur, size = [], [], 0
    for line in lines:
        if size + len(line) > max_chars and cur:
            windows.append("\n".join(cur))
            cur = cur[-6:]  # overlap so a moment on the border is seen whole
            size = sum(len(x) for x in cur)
        cur.append(line)
        size += len(line)
    if cur:
        windows.append("\n".join(cur))
    return windows


def _to_proposals(data, by_idx: dict[int, dict]) -> list[dict]:
    out = []
    for item in data if isinstance(data, list) else []:
        try:
            a, b = by_idx[int(item["start_index"])], by_idx[int(item["end_index"])]
        except (KeyError, ValueError, TypeError):
            continue  # the model referenced a line that does not exist: ignore, never guess
        if b["end"] <= a["start"]:
            continue
        out.append({"start": a["start"], "end": b["end"], "category": str(item.get("category") or ""),
                    "title": str(item.get("title") or "")[:200], "reason": str(item.get("reason") or "")[:400],
                    "interest": min(1.0, max(0.0, float(item.get("interest") or 0) / 10.0)),
                    "complete": item.get("complete") is not False})
    return out


def propose_moments(client: LLMClient, segments: list[dict], events: list[dict], on_progress) -> list[dict]:
    by_idx = {s["idx"]: s for s in segments}
    windows = transcript_windows(segments, events)
    out: list[dict] = []
    for i, w in enumerate(windows):
        on_progress(i / max(1, len(windows)), f"Context model: part {i + 1} of {len(windows)}")
        out += _to_proposals(client.chat_json(CONTEXT_SYSTEM, w, max_tokens=1200), by_idx)
    return out


def search_moments(client: LLMClient, query: str, segments: list[dict], events: list[dict]) -> list[dict]:
    by_idx = {s["idx"]: s for s in segments}
    out: list[dict] = []
    for w in transcript_windows(segments, events):
        system = CONTEXT_SYSTEM + f" Only return moments that match this request from the user: {query!r}."
        out += _to_proposals(client.chat_json(system, w, max_tokens=1200), by_idx)
    for p in out:
        p["category"] = "custom"
    return out
