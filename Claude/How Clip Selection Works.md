---
tags: [clipforge, ai, architecture]
---
# How clip selection works

Back to [[Home]] · Code: `backend/clipforge/analysis/`

The goal is complete, self-contained moments (setup → event → reaction), never a clip chosen from loudness, a face, or a keyword alone.

## Pipeline (stages 1–8, `analysis/pipeline.py`)
1. **Ingestion**: FFprobe metadata, disk-space check.
2. **Audio extraction**: FFmpeg → 16 kHz mono WAV (memory-mapped, so hour-long videos are fine); 50 ms loudness curve; voice activity segments (Silero VAD, or a loudness fallback).
3. **Transcription**: Whisper on each VAD chunk (≤14 s, split at real pauses) with one detected language for the whole video. Non-speech annotations and stock hallucinations ("Thanks for watching!") are removed.
4. **Visual analysis**: PySceneDetect content detection; one FFmpeg decode at 320 px and 1–4 fps (profile) for frame differences, the motion centroid and YuNet faces.
5. **Event detection**: builds the event timeline:
   - *Audio tagger*: laughter, scream, cheering, gasp, crying, music, impact (AudioSet labels mapped to these kinds)
   - *Signal*: loud spikes outside speech (or a clear shout), raised-voice sentences, quiet pauses
   - *Visual*: sudden movement (relative to the last 20 s, so busy gameplay is not "always sudden"), rapid cuts, face close-ups
   - *Transcript*: English + Tagalog/Taglish cue phrases (surprise, humor, teaching, emotion, statements, storytelling), questions, exclamations, fast delivery
6. **Context analysis** (optional local model): describes the frames around the strongest events, and reads the annotated transcript to propose self-contained moments. Indices it returns are checked against real transcript lines; invented lines are ignored.
7. **Clip generation**: see below.
8. **Captions**: cues grouped from words (by the preset's words-per-caption, breaking at punctuation and pauses).

Stages 9–10 (render, validation) run per export (`export/`).

## Building candidate windows (`analysis/clips.py`)
- **Anchors**: reaction events are clustered (≤3 s apart); spoken signals separately. A reaction belongs to what led up to it.
- **Window growth**: from the anchor, walk **back** through continuous speech for the setup and **forward** until both the sentence and the reaction are over. Long gaps stop the walk. Windows never start or end inside a sentence. If a moment is shorter than the minimum, lead-in and tail come from the surrounding silence, never the neighbouring sentences.
- **No-speech moments** (gameplay): the event plus lead-in, snapped to nearby scene cuts.
- **Passages**: runs of continuous speech are also scored, which catches explanations and stories with few loud signals.
- **Model proposals** (if enabled) go through the same boundary logic and scoring.

## Explainable score (0–100)
Eight sub-scores, each 0–1, weighted:

| Sub-score | Weight | From |
|---|---|---|
| Interesting content | 0.24 | transcript signals, vision-model interest, model judgement |
| Humor / entertainment | 0.14 | laughter, cheering |
| Reaction intensity | 0.14 | screams, gasps, spikes, close-ups, movement |
| Context completeness | 0.12 | spoken setup before the reaction, aftermath after it |
| Narrative coherence | 0.10 | speech coverage, no dead air (reactions count as filled time) |
| Beginning/ending quality | 0.10 | starts/ends in a pause, not mid-sentence or mid-reaction |
| Audio clarity | 0.08 | speech level versus noise floor, clipping |
| Visual relevance | 0.08 | faces present, motion, visual events |

The total is then **gated by evidence**: a clean, well-cut window with no real signal is capped at about half. **Confidence** rises with the number of independent modalities that agree. **Category** is the one whose event kinds (and the model's suggestion) are strongest, limited to the categories you chose.

Ranking removes overlaps (IoU > 0.4, or 70% of the shorter clip). If nothing reaches the evidence threshold, at most 3 weak suggestions are shown, marked **low confidence**, with a notice. With no evidence at all, there are no suggestions, plus a notice that you can still make a clip manually.

The **reason** text is generated only from measured signals ("laughter at 0:09 (73% intensity); includes the spoken setup before the reaction; starts and ends on pauses").

## Reframing (`export/reframe.py`)
- Follows **one** face consistently (largest first, then the nearest); otherwise the activity centroid (gameplay); otherwise center.
- Within a shot: if the subject stays in a small zone the crop is **locked**; otherwise zero-lag smoothing (τ 1.4 s for faces, 3 s for activity). Jumps happen only at scene cuts.
- The same crop plan drives the editor preview and the FFmpeg `crop` expression.
