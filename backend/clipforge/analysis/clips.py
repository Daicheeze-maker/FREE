"""Clip decision engine.

Fuses audio, visual, transcript and (optional) language-model evidence into ranked,
explainable clip candidates whose boundaries respect sentences and reactions.

Scores estimate how interesting the content is. They are not a prediction of views.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..audio import features
from .visual import window_stats

CATEGORIES = {
    "funny": "Funny Moments",
    "reactions": "Best Reactions",
    "unexpected": "Unexpected Moments",
    "epic": "Epic Moments",
    "conversation": "Interesting Conversations",
    "educational": "Educational Highlights",
    "emotional": "Emotional Moments",
    "statements": "Important Statements",
    "custom": "Custom AI Search",
}

REACTION_KINDS = {"laughter", "scream", "cheering", "gasp", "crying", "impact", "energy_spike", "raised_voice",
                  "sudden_movement", "face_closeup"}
# how strongly each event kind argues for each category
AFFINITY = {
    "funny": {"laughter": 1.0, "speech_humor": 0.6, "speech_story": 0.2},
    "reactions": {"scream": 1.0, "gasp": 0.9, "raised_voice": 0.6, "face_closeup": 0.5, "speech_surprise": 0.5,
                  "energy_spike": 0.4, "speech_exclaim": 0.3},
    "unexpected": {"energy_spike": 0.7, "impact": 0.7, "sudden_movement": 0.7, "speech_surprise": 0.6, "gasp": 0.4},
    "epic": {"cheering": 1.0, "impact": 0.6, "rapid_cuts": 0.3, "sudden_movement": 0.4, "scream": 0.3},
    "conversation": {"speech_question": 0.7, "speech_story": 0.5, "speech_statement": 0.3, "fast_speech": 0.2},
    "educational": {"speech_educational": 1.0, "speech_question": 0.2},
    "emotional": {"crying": 1.0, "speech_emotional": 0.8},
    "statements": {"speech_statement": 0.9, "speech_exclaim": 0.2},
}
SCORE_LABELS = {
    "interesting": "Interesting content", "context": "Context completeness", "entertainment": "Humor / entertainment",
    "reaction": "Reaction intensity", "clarity": "Audio clarity", "visual": "Visual relevance",
    "coherence": "Narrative coherence", "boundaries": "Beginning and ending quality",
}
# final score = 100 * sum(weight * sub-score); weights sum to 1
WEIGHTS = {"interesting": 0.24, "entertainment": 0.14, "reaction": 0.14, "context": 0.12, "clarity": 0.08,
           "visual": 0.08, "coherence": 0.10, "boundaries": 0.10}
MIN_SIGNAL = 0.18  # below this there is no real evidence of an interesting moment


@dataclass
class Inputs:
    duration: float
    segments: list[dict]  # sentences: {idx,start,end,text}
    speech: list[tuple[float, float]]  # voice-activity chunks
    events: list[dict]
    scenes: list[tuple[float, float]]
    track: list[dict]
    rms_db: np.ndarray
    min_len: float = 15.0
    max_len: float = 60.0
    count: int = 10
    categories: list[str] = field(default_factory=lambda: [c for c in CATEGORIES if c != "custom"])
    proposals: list[dict] = field(default_factory=list)  # from the language model
    has_tagger: bool = True


def fmt_t(t: float) -> str:
    t = max(0, int(t))
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


def _sat(x: float, k: float = 1.0) -> float:
    return 1.0 - math.exp(-k * max(0.0, x))


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


# --------------------------------------------------------------------------- windows
def _moments(inp: Inputs) -> list[dict]:
    """Anchor moments. Reactions and spoken signals are clustered separately: a reaction belongs to
    whatever led up to it (found by walking back through the speech), not to whatever happens to
    follow it a few seconds later."""
    reactions = sorted((e for e in inp.events if (e["kind"] in REACTION_KINDS and e["intensity"] >= 0.35)
                        or (e["kind"] == "vlm_frame" and e["intensity"] >= 0.6)), key=lambda e: e["start"])
    spoken = sorted((e for e in inp.events if e["kind"].startswith("speech_")), key=lambda e: e["start"])
    moments: list[dict] = []
    for group, max_gap in ((reactions, 3.0), (spoken, 2.0)):
        cur = None
        for e in group:
            if cur and e["start"] - cur["end"] <= max_gap and e["end"] - cur["start"] <= inp.max_len * 0.6:
                cur["end"] = max(cur["end"], e["end"])
                cur["events"].append(e)
            else:
                cur = {"start": e["start"], "end": e["end"], "events": [e]}
                moments.append(cur)
    return moments


def _window_for(inp: Inputs, m0: float, m1: float) -> tuple[float, float]:
    """Grow a window around a moment so it holds the full setup -> event -> reaction."""
    segs = inp.segments
    target = min(inp.max_len, max(inp.min_len, (m1 - m0) + 14.0))
    inside = [i for i, s in enumerate(segs) if s["end"] > m0 - 0.5 and s["start"] < m1 + 0.5]
    if not segs or (not inside and _nearby(segs, m0, m1) is None):
        # no speech nearby (e.g. pure gameplay): centre on the event with lead-in, snap to scene cuts
        start = max(0.0, m0 - min(6.0, target * 0.4))
        end = min(inp.duration, max(m1 + 2.0, start + inp.min_len))
        return _snap_scenes(inp, start, min(end, start + inp.max_len))
    if not inside:
        inside = [_nearby(segs, m0, m1)]  # type: ignore[list-item]
    first, last = inside[0], inside[-1]
    # Walk back through the conversational run to capture the setup.
    while first > 0:
        prev, cur = segs[first - 1], segs[first]
        gap = cur["start"] - prev["end"]
        new_len = max(m1, segs[last]["end"]) - prev["start"]
        if gap > 2.0 or new_len > target or (m0 - prev["start"]) > max(12.0, inp.max_len * 0.6):
            break
        first -= 1
    # Walk forward so the reaction / closing sentence is complete.
    while last + 1 < len(segs):
        cur, nxt = segs[last], segs[last + 1]
        tail = max(cur["end"], m1)  # the moment is over when both the sentence and the reaction are
        gap = nxt["start"] - tail
        new_len = nxt["end"] - segs[first]["start"]
        if new_len > inp.max_len:
            break
        if gap > 1.0 and (tail - segs[first]["start"]) >= inp.min_len:
            break
        if gap > 2.5:
            break
        last += 1
    # Too short? extend backwards while the speech is continuous.
    while segs[last]["end"] - segs[first]["start"] < inp.min_len and first > 0 \
            and segs[first]["start"] - segs[first - 1]["end"] <= 2.0 \
            and segs[last]["end"] - segs[first - 1]["start"] <= inp.max_len:
        first -= 1
    # Too long? drop setup sentences from the front, never the anchor.
    while segs[last]["end"] - segs[first]["start"] > inp.max_len and segs[first]["end"] <= m0 and first < last:
        first += 1
    start = segs[first]["start"]
    end = max(segs[last]["end"], min(m1 + 0.5, segs[first]["start"] + inp.max_len))
    start, end = _pad(inp, start, end, first, last)
    # Still too short (a brief reaction with little speech): add lead-in / tail from the silence around
    # it, never reaching into the neighbouring sentences.
    lo = segs[first - 1]["end"] + 0.3 if first > 0 else 0.0
    hi = segs[last + 1]["start"] - 0.3 if last + 1 < len(segs) else inp.duration
    start = min(start, max(lo, m0 - 1.0))  # the event itself is always inside, with a beat before it
    end = max(end, min(hi, m1 + 0.5))
    need = inp.min_len - (end - start)
    if need > 0:
        lead = min(need * 0.7, max(0.0, start - lo))
        start -= lead
        tail = min(need - lead, max(0.0, hi - end))
        end += tail
        start -= min(inp.min_len - (end - start), max(0.0, start - lo)) if end - start < inp.min_len else 0.0
    return round(start, 2), round(end, 2)


def _nearby(segs: list[dict], m0: float, m1: float) -> int | None:
    """Closest sentence to a speech-less moment: the line just before it (its setup); otherwise the
    line right after it (the spoken reaction); otherwise an earlier line within 6 s."""
    before = [i for i, s in enumerate(segs) if s["end"] <= m0 + 0.5 and m0 - s["end"] <= 6.0]
    after = [i for i, s in enumerate(segs) if s["start"] >= m1 - 0.5 and s["start"] - m1 <= 3.0]
    if before and m0 - segs[before[-1]]["end"] <= 2.5:
        return before[-1]
    if after:
        return after[0]
    return before[-1] if before else None


def _pad(inp: Inputs, start: float, end: float, first: int, last: int) -> tuple[float, float]:
    """Small breathing room that never reaches into the neighbouring sentence."""
    segs = inp.segments
    lo = segs[first - 1]["end"] if first > 0 else 0.0
    hi = segs[last + 1]["start"] if last + 1 < len(segs) else inp.duration
    start = max(lo, start - 0.2, 0.0) if start - lo > 0.05 else start
    end = min(hi, end + 0.35, inp.duration) if hi - end > 0.05 else end
    if end - start > inp.max_len:
        end = start + inp.max_len
    return round(start, 2), round(end, 2)


def _snap_scenes(inp: Inputs, start: float, end: float) -> tuple[float, float]:
    cuts = [s for s, _ in inp.scenes] + [inp.duration]
    for c in cuts:
        if abs(c - start) <= 1.0:
            start = c
        if abs(c - end) <= 1.0 and c - start >= inp.min_len * 0.8:
            end = c
    return round(max(0.0, start), 2), round(min(inp.duration, end), 2)


def _passages(inp: Inputs) -> list[tuple[float, float]]:
    """Speech-only candidates: coherent runs of sentences bounded by real pauses."""
    out, segs = [], inp.segments
    i = 0
    while i < len(segs):
        j = i
        while j + 1 < len(segs) and segs[j + 1]["start"] - segs[j]["end"] <= 1.2 \
                and segs[j + 1]["end"] - segs[i]["start"] <= inp.max_len:
            j += 1
        if segs[j]["end"] - segs[i]["start"] >= inp.min_len:
            out.append(_pad(inp, segs[i]["start"], segs[j]["end"], i, j))
        i = j + 1
    return out


# --------------------------------------------------------------------------- scoring
def score_window(inp: Inputs, start: float, end: float, llm: dict | None = None) -> dict:
    dur = max(0.1, end - start)
    evs = [e for e in inp.events if _overlap(start, end, e["start"], e["end"]) > 0 or start <= e["start"] <= end]
    by_kind: dict[str, float] = {}
    for e in evs:
        by_kind[e["kind"]] = max(by_kind.get(e["kind"], 0.0), e["intensity"])
    segs = [s for s in inp.segments if s["end"] > start and s["start"] < end]
    speech_time = sum(_overlap(start, end, a, b) for a, b in inp.speech)
    coverage = min(1.0, speech_time / dur)
    vis = window_stats(inp.track, start, end)

    reactions = [e for e in evs if e["kind"] in REACTION_KINDS and e["intensity"] >= 0.35]
    speech_signal = sum(e["intensity"] for e in evs if e["modality"] == "speech")
    vlm = max((e["intensity"] for e in evs if e["kind"] == "vlm_frame"), default=0.0)
    llm_interest = (llm or {}).get("interest", 0.0)
    interesting = max(_sat(speech_signal, 0.55) * 0.9, vlm, llm_interest)
    entertainment = max(by_kind.get("laughter", 0), by_kind.get("cheering", 0) * 0.9,
                        by_kind.get("speech_humor", 0) * 0.5)
    reaction = max(by_kind.get(k, 0) * w for k, w in (
        ("scream", 1.0), ("gasp", 0.9), ("crying", 0.9), ("raised_voice", 0.8), ("energy_spike", 0.75),
        ("impact", 0.8), ("face_closeup", 0.6), ("sudden_movement", 0.65), ("laughter", 0.6), ("cheering", 0.7)))

    # Context: is there a setup before the first reaction, and an aftermath after the last?
    if reactions and segs:
        first_r, last_r = min(e["start"] for e in reactions), max(e["end"] for e in reactions)
        setup = sum(_overlap(start, first_r, s["start"], s["end"]) for s in segs)
        context = 0.35 + 0.4 * min(1.0, setup / 4.0) + 0.25 * min(1.0, max(0.0, end - last_r) / 1.0)
    elif segs:
        context = 0.55 + 0.45 * min(1.0, len(segs) / 3.0)  # multi-sentence passage carries its own context
    else:
        context = 0.3
    if llm and llm.get("complete") is False:
        context *= 0.7

    # Boundaries: do we start/end in silence rather than mid-speech?
    def in_speech(t: float) -> bool:  # transcribed sentences, not raw voice activity (laughs trigger VAD too)
        return any(x["start"] + 0.12 < t < x["end"] - 0.12 for x in inp.segments)

    b_start = 0.35 if in_speech(start) else 1.0
    b_end = 0.35 if in_speech(end) else 1.0
    mid_reaction = any(e["start"] + 0.3 < end < e["end"] - 0.3 for e in reactions)
    boundaries = (b_start + b_end) / 2 * (0.75 if mid_reaction else 1.0)

    # Coherence: continuous delivery, no dead air inside.
    dead = sum(_overlap(start, end, e["start"], e["end"]) for e in evs if e["kind"] == "pause")
    # time filled by an audible reaction (laughter, cheering...) is part of the moment, not a gap
    react_time = sum(_overlap(start, end, e["start"], e["end"]) for e in reactions if e["modality"] == "audio")
    filled = min(1.0, coverage + min(react_time, dur) / dur)
    if segs:
        coherence = float(np.clip(0.3 + 0.7 * filled - 0.8 * dead / dur, 0.0, 1.0))
    else:
        coherence = 0.5 if reactions else 0.2

    clarity = features.clarity(inp.rms_db, inp.speech, start, end) if segs else (0.5 if reactions else 0.2)
    visual = float(np.clip(0.45 * vis["face_ratio"] + 0.25 * _sat(vis["motion"], 40) + 0.3 * max(
        by_kind.get("face_closeup", 0), by_kind.get("sudden_movement", 0), by_kind.get("rapid_cuts", 0), vlm), 0, 1))

    scores = {"interesting": interesting, "context": context, "entertainment": entertainment, "reaction": reaction,
              "clarity": clarity, "visual": visual, "coherence": coherence, "boundaries": boundaries}
    scores = {k: round(float(v), 3) for k, v in scores.items()}

    affinity = {c: sum(by_kind.get(k, 0) * w for k, w in kinds.items()) for c, kinds in AFFINITY.items()}
    if coverage > 0.6 and len(segs) >= 3:
        affinity["conversation"] += 0.15  # sustained talk is at least a conversation/explanation
    if llm and llm.get("category") in AFFINITY:
        affinity[llm["category"]] += 0.6
    allowed = {c: v for c, v in affinity.items() if c in inp.categories} or affinity
    category = max(allowed, key=allowed.get)  # type: ignore[arg-type]
    signal = max(interesting, entertainment, reaction, vlm, llm_interest)
    total = 100.0 * sum(WEIGHTS[k] * scores[k] for k in WEIGHTS)
    # Evidence gates the score: clean, well-cut footage of nothing is still nothing.
    total *= 0.45 + 0.55 * min(1.0, signal / 0.6)

    modalities = {e["modality"] for e in evs if e["intensity"] >= 0.3}
    peak_conf = max((e["confidence"] for e in evs), default=0.0)
    confidence = 0.15 + 0.15 * len(modalities) + 0.3 * peak_conf
    if not inp.has_tagger:
        confidence *= 0.8
    if llm:
        confidence += 0.1
    return {"start": start, "end": end, "scores": scores, "score": round(total, 1), "category": category,
            "signal": round(signal, 3), "confidence": round(float(np.clip(confidence, 0.05, 0.95)), 2),
            "events": evs, "segments": segs, "coverage": coverage, "affinity": allowed.get(category, 0.0)}


def _reason(c: dict) -> str:
    """Plain-language explanation built only from signals that were actually measured."""
    parts = []
    strong = sorted((e for e in c["events"] if e["modality"] != "speech" and e["kind"] not in ("pause", "music")
                     and c["start"] - 0.5 <= (e["start"] + e["end"]) / 2 <= c["end"] + 0.5),
                    key=lambda e: -e["intensity"])[:3]
    for e in strong:
        parts.append(f"{e['kind'].replace('_', ' ')} at {fmt_t(e['start'])} "
                     f"({int(e['intensity'] * 100)}% intensity)")
    said = [e["label"] for e in c["events"] if e["modality"] == "speech" and e.get("label", "").startswith("said")][:2]
    if said:
        parts.append("; ".join(said))
    if any(e["kind"] == "speech_question" for e in c["events"]) and len(c["segments"]) >= 2:
        parts.append("a question and its answer are kept together")
    s = c["scores"]
    if s["context"] >= 0.75 and strong:
        parts.append("includes the spoken setup before the reaction")
    if s["boundaries"] >= 0.95:
        parts.append("starts and ends on pauses, not mid-sentence")
    elif s["boundaries"] < 0.7:
        parts.append("a boundary falls inside speech — consider adjusting the trim")
    if not parts:
        parts.append("continuous, clear speech with no stronger signal")
    return "Selected because: " + "; ".join(parts) + "."


def _title(c: dict) -> str:
    segs = c["segments"]
    if not segs:
        return f"{CATEGORIES[c['category']].rstrip('s')} at {fmt_t(c['start'])}"
    peak = max((e for e in c["events"] if e["kind"] in REACTION_KINDS), key=lambda e: e["intensity"], default=None)
    pick = None
    if peak:  # the line right before the biggest reaction is usually the punchline
        before = [s for s in segs if s["start"] <= peak["start"] + 0.5]
        pick = before[-1] if before else None
    if not pick:
        pick = next((s for s in segs if "?" in s["text"]), None) or max(segs, key=lambda s: len(s["text"]))
    text = pick["text"].strip().strip('"')
    if len(text) > 64:
        text = text[:61].rsplit(" ", 1)[0] + "…"
    return text[:1].upper() + text[1:]


# --------------------------------------------------------------------------- selection
def _iou(a: dict, b: dict) -> tuple[float, float]:
    inter = _overlap(a["start"], a["end"], b["start"], b["end"])
    union = max(a["end"], b["end"]) - min(a["start"], b["start"])
    smaller = min(a["end"] - a["start"], b["end"] - b["start"])
    return inter / union if union else 0.0, inter / smaller if smaller else 0.0


def generate(inp: Inputs) -> list[dict]:
    """Return ranked candidates (possibly empty when the video has no real moments)."""
    raw: list[dict] = []
    seen: set[tuple[float, float]] = set()

    def add(start: float, end: float, llm: dict | None = None, source: str = "signals") -> None:
        start, end = max(0.0, start), min(inp.duration, end)
        if end - start < min(inp.min_len, inp.duration) * 0.6 or (round(start, 1), round(end, 1)) in seen:
            return
        seen.add((round(start, 1), round(end, 1)))
        c = score_window(inp, start, end, llm)
        c["source"] = source
        c["llm"] = llm
        raw.append(c)

    for m in _moments(inp):
        add(*_window_for(inp, m["start"], m["end"]))
    for a, b in _passages(inp):
        add(a, b)
    for p in inp.proposals:
        add(*_window_for(inp, p["start"], p["end"]), llm=p, source="llm")

    raw.sort(key=lambda c: -c["score"])
    kept: list[dict] = []
    for c in raw:
        if c["signal"] < MIN_SIGNAL * 0.5:
            continue
        if any(_iou(c, k)[0] > 0.4 or _iou(c, k)[1] > 0.7 for k in kept):
            continue
        kept.append(c)
    strong = [c for c in kept if c["signal"] >= MIN_SIGNAL]
    result = strong[:inp.count] if strong else kept[:3]
    out = []
    for rank, c in enumerate(result, 1):
        llm = c.get("llm") or {}
        reason = _reason(c)
        if llm.get("reason"):
            reason = f"Language model: {llm['reason'].strip()} {reason}"
        out.append({
            "rank": rank, "start": c["start"], "end": c["end"], "category": c["category"], "score": c["score"],
            "confidence": c["confidence"], "scores": c["scores"], "reason": reason,
            "title": (llm.get("title") or _title(c))[:200],
            "transcript_text": " ".join(s["text"] for s in c["segments"]),
            "source": c["source"], "low_confidence": c["signal"] < MIN_SIGNAL,
        })
    return out
