"""Transcript-derived signals (English + Tagalog/Taglish cue words, questions, exclamations).

These are weak signals on their own and are only ever combined with audio/visual
evidence and context by the decision engine — a keyword never selects a clip by itself.
"""
from __future__ import annotations

import re

LEXICON: dict[str, list[str]] = {
    "speech_surprise": [
        "no way", "oh my god", "omg", "what the", "holy", "insane", "crazy", "wow", "wait what", "are you serious",
        "i can't believe", "unbelievable", "let's go", "clutch", "what just happened",
        "grabe", "hala", "naku", "diyos ko", "ano ba", "ano yun", "totoo ba", "seryoso", "lupit", "lupet",
        "ang galing", "sobra", "ay nako", "putik", "shet",
    ],
    "speech_humor": [
        "haha", "hahaha", "lol", "joke", "kidding", "funny", "hilarious", "i'm dead", "laughing",
        "nakakatawa", "tawa", "biro", "charot", "joke lang", "loko", "kulit",
    ],
    "speech_educational": [
        "the reason", "how to", "here's how", "here is how", "the key", "important", "remember", "tip", "step one",
        "first of all", "the trick", "for example", "that means", "in other words", "the difference", "you need to",
        "you should", "make sure", "the best way", "mistake", "lesson",
        "ibig sabihin", "paano", "tandaan", "mahalaga", "halimbawa", "kailangan mong", "dapat", "ang dahilan",
        "unang", "pangalawa", "ganito",
    ],
    "speech_emotional": [
        "i love", "i miss", "i'm sorry", "i cried", "crying", "afraid", "scared", "proud of", "grateful",
        "thank you so much", "heartbroken", "hurt", "lonely", "happiest", "hardest",
        "mahal", "salamat", "patawad", "pasensya", "iyak", "umiyak", "takot", "lungkot", "nalulungkot", "masaya",
        "miss ko", "nasaktan",
    ],
    "speech_statement": [
        "the truth is", "honestly", "i believe", "the thing is", "never", "always", "the biggest", "the most",
        "nobody", "everyone", "the problem is", "the point is", "what people don't", "unpopular opinion",
        "sa totoo lang", "naniniwala", "ang totoo", "ang problema", "walang", "lahat ng",
    ],
    "speech_story": [
        "so then", "and then", "one time", "yesterday", "suddenly", "all of a sudden", "turns out", "guess what",
        "you won't believe", "long story short",
        "tapos", "bigla", "kahapon", "nung", "noong", "alam mo ba", "kwento",
    ],
}

_WORD = re.compile(r"[\w']+", re.UNICODE)


def _contains(text: str, phrase: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text) is not None


def speech_events(segments: list[dict]) -> list[dict]:
    """One event per sentence per matched signal family."""
    events = []
    for seg in segments:
        text = seg["text"].lower()
        base = {"modality": "speech", "start": seg["start"], "end": seg["end"]}
        for kind, phrases in LEXICON.items():
            hits = [p for p in phrases if _contains(text, p)]
            if hits:
                events.append({**base, "kind": kind, "intensity": round(min(0.8, 0.3 + 0.15 * len(hits)), 3),
                               "confidence": 0.4, "label": f"said: {', '.join(hits[:3])}", "data": {"hits": hits}})
        if "?" in seg["text"]:
            events.append({**base, "kind": "speech_question", "intensity": 0.3, "confidence": 0.6,
                           "label": "question asked"})
        if "!" in seg["text"]:
            events.append({**base, "kind": "speech_exclaim", "intensity": 0.35, "confidence": 0.5,
                           "label": "exclamation"})
        words = _WORD.findall(seg["text"])
        dur = max(0.2, seg["end"] - seg["start"])
        if len(words) >= 6 and len(words) / dur > 4.2:  # unusually fast delivery
            events.append({**base, "kind": "fast_speech", "intensity": 0.3, "confidence": 0.4,
                           "label": f"fast delivery ({len(words) / dur:.1f} words/s)"})
    return events


def text_match(query: str, text: str) -> float:
    """Share of query words found in the text (used by search when no language model is configured)."""
    q = {w for w in _WORD.findall(query.lower()) if len(w) > 2}
    if not q:
        return 0.0
    t = set(_WORD.findall(text.lower()))
    return len(q & t) / len(q)
