"""Caption cues, styles and subtitle formats (SRT, VTT, ASS for burn-in).

Cues are stored in source-video time. Rendering/export converts to clip time, so
trimming a clip can never shift captions out of sync.
"""
from __future__ import annotations

import copy
import re
import uuid

BASE_STYLE = {
    "preset": "minimal",
    "font": "Poppins", "weight": 600, "size": 5.2,  # size = % of output height
    "color": "#FFFFFF", "highlight_color": "#FFD400",
    "outline_color": "#000000", "outline": 2.5,  # px at 1080p-height scale
    "shadow": 1.0,
    "background": False, "background_color": "#000000", "background_opacity": 0.6,
    "position_y": 78.0,  # % from the top to the caption's vertical centre
    "align": "center",  # left|center|right
    "max_words": 6,
    "uppercase": False,
    "animation": "none",  # none|fade|pop
    "highlight": "none",  # none|word (active word highlighted)|single (one word at a time)
    "safe_margin": 6.0,  # % of width kept clear at the sides
    "speaker_labels": False,
}

PRESETS = {
    "dynamic": {**BASE_STYLE, "preset": "dynamic", "font": "Poppins", "weight": 800, "size": 6.4, "max_words": 3,
                "uppercase": True, "outline": 4.0, "animation": "pop", "highlight": "word",
                "highlight_color": "#FFE14A", "position_y": 70.0},
    "minimal": {**BASE_STYLE, "preset": "minimal", "weight": 600, "size": 4.6, "max_words": 8, "outline": 1.5,
                "shadow": 0.5, "position_y": 84.0},
    "gaming": {**BASE_STYLE, "preset": "gaming", "font": "Anton", "weight": 400, "size": 7.4, "max_words": 3,
               "uppercase": True, "outline": 5.0, "shadow": 2.0, "animation": "pop", "highlight": "word",
               "color": "#FFFFFF", "highlight_color": "#39FF6A", "position_y": 66.0},
    "podcast": {**BASE_STYLE, "preset": "podcast", "weight": 600, "size": 4.8, "max_words": 7, "outline": 0.0,
                "shadow": 0.0, "background": True, "background_opacity": 0.7, "position_y": 82.0,
                "speaker_labels": True, "animation": "fade"},
}
PRESETS["custom"] = {**BASE_STYLE, "preset": "custom"}

FONTS = {  # family -> weights bundled with the app (all SIL Open Font License)
    "Poppins": [400, 600, 700, 800], "Anton": [400], "Bebas Neue": [400],
}


def normalize_style(style: dict | None) -> dict:
    out = copy.deepcopy(PRESETS.get((style or {}).get("preset", "minimal"), BASE_STYLE))
    for k, v in (style or {}).items():
        if k in BASE_STYLE:
            out[k] = v
    return out


# --------------------------------------------------------------------------- cue building
_BREAK = re.compile(r"[.!?…,;:]$")


def build_cues(segments: list[dict], start: float, end: float, max_words: int) -> list[dict]:
    """Group transcript words into caption cues inside [start, end] (source time)."""
    words = []
    for seg in segments:
        if seg["end"] <= start or seg["start"] >= end:
            continue
        seg_words = seg.get("words") or [{"w": seg["text"], "start": seg["start"], "end": seg["end"]}]
        for w in seg_words:
            mid = (w["start"] + w["end"]) / 2
            if start <= mid <= end:
                words.append({**w, "speaker": seg.get("speaker")})
    cues, cur = [], []

    def flush() -> None:
        if cur:
            cues.append({"id": uuid.uuid4().hex[:8], "start": round(cur[0]["start"], 3),
                         "end": round(cur[-1]["end"], 3), "text": " ".join(w["w"] for w in cur),
                         "speaker": cur[0].get("speaker") or "",
                         "words": [{"w": w["w"], "start": round(w["start"], 3), "end": round(w["end"], 3)}
                                   for w in cur]})
            cur.clear()

    for w in words:
        if cur and (w["start"] - cur[-1]["end"] > 0.7 or len(cur) >= max_words):
            flush()
        cur.append(w)
        if _BREAK.search(w["w"]) and len(cur) >= max(2, max_words // 2):
            flush()
    flush()
    for a, b in zip(cues, cues[1:]):  # no overlap, and hold a cue briefly across tiny gaps
        if b["start"] - a["end"] < 0.25:
            a["end"] = b["start"]
    return cues


def regroup(cues: list[dict], max_words: int) -> list[dict]:
    """Re-flow existing (possibly edited) cues to a new words-per-line setting."""
    segs = [{"start": c["start"], "end": c["end"], "text": c["text"], "words": c["words"], "speaker": c.get("speaker")}
            for c in cues]
    if not segs:
        return []
    return build_cues(segs, min(s["start"] for s in segs) - 1, max(s["end"] for s in segs) + 1, max_words)


def retime_words(cue: dict) -> dict:
    """After the user edits a cue's text or times, rebuild its word timings to match."""
    toks = cue["text"].split()
    old = cue.get("words") or []
    if len(toks) == len(old) and old and abs(old[0]["start"] - cue["start"]) < 1e-3 \
            and abs(old[-1]["end"] - cue["end"]) < 1e-3:
        words = [{**o, "w": t} for o, t in zip(old, toks)]  # same shape: keep real timings
    else:
        from ..ai.asr import interpolate_words

        words = interpolate_words(cue["text"], cue["start"], cue["end"])
    return {**cue, "words": words}


def clip_cues(cues: list[dict], start: float, end: float) -> list[dict]:
    """Cues shifted into clip time and clamped to the clip."""
    out = []
    for c in cues:
        a, b = max(c["start"], start), min(c["end"], end)
        if b - a < 0.05:
            continue
        words = [{"w": w["w"], "start": round(max(w["start"], start) - start, 3),
                  "end": round(min(w["end"], end) - start, 3)}
                 for w in c.get("words", []) if w["end"] > start and w["start"] < end]
        out.append({**c, "start": round(a - start, 3), "end": round(b - start, 3), "words": words})
    return out


# --------------------------------------------------------------------------- text formats
def _ts(t: float, sep: str) -> str:
    ms = int(round(max(0.0, t) * 1000))
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d}{sep}{ms % 1000:03d}"


def _line(c: dict, labels: bool) -> str:
    return (f"{c['speaker']}: " if labels and c.get("speaker") else "") + c["text"]


def to_srt(cues: list[dict], labels: bool = False) -> str:
    return "".join(f"{i}\n{_ts(c['start'], ',')} --> {_ts(c['end'], ',')}\n{_line(c, labels)}\n\n"
                   for i, c in enumerate(cues, 1))


def to_vtt(cues: list[dict], labels: bool = False) -> str:
    return "WEBVTT\n\n" + "".join(f"{_ts(c['start'], '.')} --> {_ts(c['end'], '.')}\n{_line(c, labels)}\n\n"
                                   for c in cues)


# --------------------------------------------------------------------------- ASS (burn-in)
def _ass_color(hex_color: str, alpha: float = 0.0) -> str:
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{int(round(alpha * 255)):02X}{b}{g}{r}".upper()


def _ass_ts(t: float) -> str:
    cs = int(round(max(0.0, t) * 100))
    return f"{cs // 360000}:{cs % 360000 // 6000:02d}:{cs % 6000 // 100:02d}.{cs % 100:02d}"


def _esc(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def to_ass(cues: list[dict], style: dict, width: int, height: int) -> str:
    """Styled subtitles in clip time for libass. Sizes scale with the output height."""
    st = normalize_style(style)
    k = height / 1080.0
    font_px = st["size"] / 100.0 * height
    bold = -1 if st["weight"] >= 700 else 0
    font = st["font"] if st["weight"] in (400, 700) or st["font"] != "Poppins" else \
        {600: "Poppins SemiBold", 800: "Poppins ExtraBold"}.get(st["weight"], "Poppins")
    if font != st["font"]:
        bold = 0  # the weight is carried by the family name
    align = {"left": 4, "center": 5, "right": 6}[st["align"]]  # middle row: \pos anchors the centre
    margin = int(st["safe_margin"] / 100.0 * width)
    x = {"left": margin, "center": width // 2, "right": width - margin}[st["align"]]
    y = int(st["position_y"] / 100.0 * height)
    primary, hi = _ass_color(st["color"]), _ass_color(st["highlight_color"])
    if st["background"]:
        border_style, outline = 3, max(2.0, font_px * 0.18)
        outline_c = _ass_color(st["background_color"], 1 - st["background_opacity"])
        back_c = outline_c
        shadow = 0.0
    else:
        border_style, outline, shadow = 1, st["outline"] * k, st["shadow"] * k
        outline_c, back_c = _ass_color(st["outline_color"]), _ass_color("#000000", 0.5)
    head = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {width}\nPlayResY: {height}\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Cap,{font},{font_px:.1f},{primary},{primary},{outline_c},{back_c},{bold},0,0,0,100,100,0,0,"
        f"{border_style},{outline:.1f},{shadow:.1f},{align},{margin},{margin},0,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    wrap_w = width - 2 * margin
    lines = []

    def emit(start: float, end: float, text: str, first: bool) -> None:
        if end - start < 0.02:
            return
        tags = f"\\pos({x},{y})\\q0"
        if first and st["animation"] == "fade":
            tags += "\\fad(120,80)"
        if first and st["animation"] == "pop":
            tags += "\\fscx118\\fscy118\\t(0,110,\\fscx100\\fscy100)"
        lines.append(f"Dialogue: 0,{_ass_ts(start)},{_ass_ts(end)},Cap,,0,0,0,,{{{tags}}}{text}")

    def fmt(word: str) -> str:
        w = _esc(word)
        return w.upper() if st["uppercase"] else w

    for c in cues:
        label = f"{_esc(c['speaker'])}: " if st["speaker_labels"] and c.get("speaker") else ""
        words = c.get("words") or []
        text_words = [fmt(w["w"]) for w in words] or [fmt(c["text"])]
        if st["highlight"] == "none" or not words:
            emit(c["start"], c["end"], label + _wrap(text_words, font_px, wrap_w), True)
            continue
        for i, w in enumerate(words):
            ws = c["start"] if i == 0 else w["start"]
            we = words[i + 1]["start"] if i + 1 < len(words) else c["end"]
            if st["highlight"] == "single":
                emit(ws, we, f"{{\\c{hi}}}" + text_words[i], True)
            else:
                parts = [(f"{{\\c{hi}}}{t}{{\\c{primary}}}" if j == i else t) for j, t in enumerate(text_words)]
                emit(ws, we, label + _wrap(parts, font_px, wrap_w, text_words), i == 0)
    return head + "\n".join(lines) + "\n"


def _wrap(parts: list[str], font_px: float, max_w: float, plain: list[str] | None = None) -> str:
    """Balanced manual line breaks (\\N) so highlighted and plain variants wrap identically."""
    plain = plain or parts
    widths = [len(p) * font_px * 0.56 for p in plain]
    space = font_px * 0.28
    total = sum(widths) + space * (len(widths) - 1)
    if total <= max_w or len(parts) < 2:
        return " ".join(parts)
    n_lines = min(3, int(total // max_w) + 1)
    target = total / n_lines
    out, cur, acc = [], [], 0.0
    for p, w in zip(parts, widths):
        if cur and acc + w > target * 1.08 and len(out) < n_lines - 1:
            out.append(" ".join(cur))
            cur, acc = [], 0.0
        cur.append(p)
        acc += w + space
    out.append(" ".join(cur))
    return "\\N".join(out)
