"""Unit tests that need no AI models: media, timestamps, captions, clip engine, reframing."""
from __future__ import annotations

import numpy as np
import pytest

from clipforge.analysis import clips as C
from clipforge.analysis.speech_events import speech_events, text_match
from clipforge.audio import features
from clipforge.captions import engine as cap
from clipforge.errors import ClipForgeError, MediaError
from clipforge.export import reframe


# ---------------------------------------------------------------- media / import
def test_probe_reads_real_metadata(data_dir, fixtures_dir):
    from clipforge.media import ffmpeg as ff

    info = ff.probe(fixtures_dir / "speech_scene.mp4")
    assert (info.width, info.height) == (640, 360)
    assert info.fps == 25
    assert abs(info.duration - 42.0) < 0.2
    assert info.has_audio and info.video_codec == "h264" and info.audio_codec == "aac"


def test_corrupted_video_gives_readable_error(data_dir, fixtures_dir):
    from clipforge.importing import local

    with pytest.raises(MediaError) as e:
        local.create_project(fixtures_dir / "corrupted.mp4")
    assert "corrupted" in str(e.value).lower() or "could not be read" in str(e.value).lower()


def test_unsupported_extension_and_missing_file(data_dir, tmp_path):
    from clipforge.importing import local

    f = tmp_path / "notes.txt"
    f.write_text("hello")
    with pytest.raises(ClipForgeError, match="not a supported video type"):
        local.create_project(f)
    with pytest.raises(ClipForgeError, match="does not exist"):
        local.create_project(tmp_path / "nope.mp4")


def test_import_persists_and_blocks_duplicates(data_dir, fixtures_dir):
    from clipforge.importing import local

    res = local.create_project(fixtures_dir / "no_audio.mp4")
    assert res["source"]["has_audio"] is False
    assert res["source"]["thumb_path"] and open(res["source"]["thumb_path"], "rb").read(2) == b"\xff\xd8"
    with pytest.raises(local.DuplicateImport) as e:
        local.create_project(fixtures_dir / "no_audio.mp4")
    assert e.value.project_id == res["project"]["id"]


def test_audio_extraction_and_loudness(data_dir, fixtures_dir, tmp_path):
    from clipforge.audio.io import SR, Wav, extract_wav

    out = tmp_path / "a.wav"
    seen = []
    extract_wav(fixtures_dir / "speech_scene.mp4", out, 42.0, on_progress=seen.append)
    wav = Wav(out)
    assert abs(wav.duration - 42.0) < 0.2 and seen and max(seen) > 0.9
    assert len(wav.read(1.0, 2.0)) == SR
    rms = features.loudness_curve(wav)
    # speech at ~3 s is far louder than the room tone at ~12 s
    assert rms[int(3 / features.HOP)] > rms[int(12 / features.HOP)] + 20
    spikes = features.energy_spikes(rms, speech=[(1.3, 8.2), (15.2, 23.7), (27.2, 30.9), (36.7, 38.8)])
    assert any(34.8 <= e["start"] <= 35.2 for e in spikes), "the noise burst at 35 s must be detected"
    assert not any(e["start"] < 9 for e in spikes), "someone starting to talk is not a loud spike"
    wav.close()


# ---------------------------------------------------------------- timestamps / captions
def test_timestamp_formats():
    cues = [{"start": 0.0, "end": 1.5, "text": "Kumusta ka?", "speaker": "Ana"},
            {"start": 3661.25, "end": 3662.0, "text": "Okay lang", "speaker": ""}]
    srt = cap.to_srt(cues)
    assert "1\n00:00:00,000 --> 00:00:01,500\nKumusta ka?" in srt
    assert "01:01:01,250 --> 01:01:02,000" in srt
    vtt = cap.to_vtt(cues, labels=True)
    assert vtt.startswith("WEBVTT") and "00:00:00.000 --> 00:00:01.500\nAna: Kumusta ka?" in vtt
    assert cap._ass_ts(3661.25) == "1:01:01.25"


SEGS = [{"start": 10.0, "end": 12.0, "text": "Hello there my friend.",
         "words": [{"w": "Hello", "start": 10.0, "end": 10.5}, {"w": "there", "start": 10.5, "end": 11.0},
                   {"w": "my", "start": 11.0, "end": 11.3}, {"w": "friend.", "start": 11.3, "end": 12.0}]},
        {"start": 13.0, "end": 14.0, "text": "Tara na!", "words": [{"w": "Tara", "start": 13.0, "end": 13.5},
                                                                     {"w": "na!", "start": 13.5, "end": 14.0}]}]


def test_caption_cues_stay_synchronised_with_words():
    cues = cap.build_cues(SEGS, 9.0, 15.0, max_words=2)
    assert [c["text"] for c in cues] == ["Hello there", "my friend.", "Tara na!"]
    for c in cues:  # a cue starts with its first word and never ends before its last word
        assert c["start"] == c["words"][0]["start"] and c["end"] >= c["words"][-1]["end"]
    assert all(a["end"] <= b["start"] for a, b in zip(cues, cues[1:]))
    # trimming the clip shifts captions by exactly the new start, so sync is preserved
    shifted = cap.clip_cues(cues, 10.5, 13.6)
    assert shifted[0]["start"] == 0.0 and shifted[0]["words"][-1]["w"] == "there"
    assert abs(shifted[-1]["start"] - 2.5) < 1e-6 and shifted[-1]["end"] <= 3.1 + 1e-6


def test_editing_text_keeps_or_rebuilds_word_timing():
    cue = cap.build_cues(SEGS, 9.0, 15.0, max_words=8)[0]
    same = cap.retime_words({**cue, "text": "Hello there my friends."})
    assert [w["start"] for w in same["words"]] == [w["start"] for w in cue["words"]]  # real timings kept
    changed = cap.retime_words({**cue, "text": "Hello there my very good friend."})
    assert len(changed["words"]) == 6
    assert changed["words"][0]["start"] == cue["start"] and abs(changed["words"][-1]["end"] - cue["end"]) < 1e-3


def test_ass_output_matches_style():
    cues = cap.clip_cues(cap.build_cues(SEGS, 9.0, 15.0, 3), 10.0, 14.0)
    ass = cap.to_ass(cues, {"preset": "dynamic"}, 1080, 1920)
    assert "PlayResX: 1080" in ass and "Poppins ExtraBold" in ass
    assert ass.count("Dialogue:") == sum(len(c["words"]) for c in cues)  # one event per highlighted word
    assert "HELLO" in ass  # dynamic preset is uppercase
    plain = cap.to_ass(cues, {"preset": "minimal"}, 1920, 1080)
    assert plain.count("Dialogue:") == len(cues) and "Hello" in plain


def test_tagalog_text_is_preserved_not_translated():
    segs = [{"start": 0.0, "end": 2.0, "text": "Grabe, ang galing mo talaga!", "words": []}]
    cues = cap.build_cues(segs, 0, 5, 6)
    assert cues[0]["text"] == "Grabe, ang galing mo talaga!"
    kinds = {e["kind"] for e in speech_events(segs)}
    assert "speech_surprise" in kinds and "speech_exclaim" in kinds
    assert text_match("galing talaga", segs[0]["text"]) == 1.0


# ---------------------------------------------------------------- clip decision engine
def _inputs(**kw):
    segs = [
        {"idx": 0, "start": 20.0, "end": 24.0, "text": "So I walk into the meeting wearing two different shoes."},
        {"idx": 1, "start": 24.2, "end": 27.0, "text": "And my boss says, nice style, is that a new trend?"},
        {"idx": 2, "start": 40.0, "end": 45.0, "text": "Anyway the quarterly numbers are in the spreadsheet."},
        {"idx": 3, "start": 45.3, "end": 50.0, "text": "Please review them before Friday afternoon."},
    ]
    events = [{"kind": "laughter", "modality": "audio", "start": 27.3, "end": 31.0, "intensity": 0.8,
               "confidence": 0.8, "label": "laughter"}] + speech_events(segs)
    base = dict(duration=120.0, segments=segs, speech=[(20.0, 27.0), (40.0, 50.0)], events=events,
                scenes=[(0.0, 120.0)], track=[], rms_db=np.full(2400, -30.0), min_len=6.0, max_len=30.0)
    base.update(kw)
    return C.Inputs(**base)


def test_joke_clip_keeps_setup_and_full_reaction():
    cands = C.generate(_inputs())
    top = cands[0]
    assert top["category"] == "funny"
    assert top["start"] <= 20.0, "the setup sentence must be included"
    assert top["end"] >= 31.0, "the laughter must be complete"
    assert top["end"] < 40.0, "the unrelated next topic must not be included"
    assert "laughter" in top["reason"] and 0 < top["score"] <= 100
    assert set(top["scores"]) == set(C.SCORE_LABELS)


def test_boundaries_never_cut_a_sentence():
    inp = _inputs()
    for c in C.generate(inp):
        for s in inp.segments:
            assert not (s["start"] + 0.15 < c["start"] < s["end"] - 0.15), "starts mid-sentence"
            assert not (s["start"] + 0.15 < c["end"] < s["end"] - 0.15), "ends mid-sentence"
        assert c["end"] - c["start"] <= inp.max_len + 0.01


def test_no_signals_means_no_candidates():
    inp = _inputs(segments=[], speech=[], events=[])
    assert C.generate(inp) == []


def test_weak_content_is_flagged_low_confidence_and_overlaps_removed():
    segs = [{"idx": i, "start": i * 5.0, "end": i * 5.0 + 4.6, "text": "We then continue along the road."}
            for i in range(8)]
    inp = _inputs(segments=segs, speech=[(0.0, 40.0)], events=speech_events(segs))
    cands = C.generate(inp)
    assert len(cands) <= 3 and all(c["low_confidence"] for c in cands)
    for i, a in enumerate(cands):
        for b in cands[i + 1:]:
            assert C._iou(a, b)[0] <= 0.4


def test_loudness_alone_does_not_beat_a_complete_moment():
    inp = _inputs()
    inp.events.append({"kind": "energy_spike", "modality": "audio", "start": 80.0, "end": 80.4,
                       "intensity": 1.0, "confidence": 0.6, "label": "bang"})
    cands = C.generate(inp)
    assert cands[0]["category"] == "funny"


# ---------------------------------------------------------------- reframing
def _track(xs, faces=True):
    return [{"t": i * 0.5, "motion": 0.01, "mc": [x, 0.5],
             "faces": [[x, 0.4, 0.15, 0.25, 0.95]] if faces else []} for i, x in enumerate(xs)]


def test_face_reframe_is_stable_and_inside_frame():
    xs = [0.3 + 0.01 * ((i % 3) - 1) for i in range(40)]  # a face jittering slightly around x=0.3
    plan = reframe.plan("smart", "9:16", {}, 1920, 1080, 0.0, 19.5, _track(xs), [(0.0, 20.0)])
    assert plan["effective"] == "face" and len(plan["keys"]) == 1, "small jitter must give a locked-off crop"
    bw = plan["box"][0]
    assert abs(bw - (1080 * 9 / 16) / 1920) < 0.01
    cx = plan["keys"][0][1]
    assert abs(cx - 0.3) < 0.02 and cx - bw / 2 >= 0


def test_reframe_follows_a_moving_face_smoothly_and_jumps_only_on_cuts():
    xs = [0.2 + 0.6 * i / 39 for i in range(40)]  # walks left to right
    plan = reframe.plan("face", "9:16", {}, 1920, 1080, 0.0, 19.5, _track(xs), [(0.0, 10.0), (10.0, 20.0)])
    keys = plan["keys"]
    assert len(keys) > 2 and plan["cuts"] == [10.0]
    speeds = [abs(b[1] - a[1]) / (b[0] - a[0]) for a, b in zip(keys, keys[1:]) if abs(b[0] - 10.0) > 0.01]
    assert max(speeds) < 0.1, "crop must not whip across the frame"
    bw = plan["box"][0]
    assert all(bw / 2 - 1e-6 <= k[1] <= 1 - bw / 2 + 1e-6 for k in keys)
    e = reframe.expr([[k[0], k[1] - bw / 2, 0] for k in keys], 1, 1920, plan["cuts"])
    assert e.startswith("if(lt(t,") and e.count("(") == e.count(")")


def test_gaming_footage_without_faces_does_not_pretend_to_track_faces():
    plan = reframe.plan("face", "9:16", {}, 1920, 1080, 0.0, 10.0, _track([0.5] * 20, faces=False), [(0.0, 10.0)])
    assert plan["effective"] == "center" and "No face" in plan["note"]


def test_manual_and_other_modes():
    p = reframe.plan("manual", "1:1", {"x": 1.0, "y": 0.5, "zoom": 1.0}, 1920, 1080, 0, 5, [], [])
    assert p["keys"][0][1] == pytest.approx(1 - p["box"][0] / 2, abs=1e-3)  # clamped to the right edge
    assert reframe.plan("fit_blur", "9:16", {}, 1920, 1080, 0, 5, [], [])["effective"] == "fit_blur"
    assert reframe.plan("smart", "original", {}, 1920, 1080, 0, 5, [], [])["effective"] == "original"
    assert reframe.output_size("9:16", "1080p", 1920, 1080, 606, 1080) == (1080, 1920)
    assert reframe.output_size("original", "720p", 1920, 1080, 1920, 1080) == (1280, 720)


# ---------------------------------------------------------------- language model plumbing
def test_json_extraction_and_local_url_rules(data_dir):
    from clipforge import settings
    from clipforge.ai import llm

    assert llm.extract_json('Sure!\n```json\n[{"a": 1}]\n```') == [{"a": 1}]
    assert llm.extract_json('<think>hmm</think>{"interest": 7}') == {"interest": 7}
    with pytest.raises(ClipForgeError):
        llm.extract_json("no json here")
    assert llm.is_local_url("http://127.0.0.1:8080/v1") and llm.is_local_url("http://192.168.1.20:1234/v1")
    assert not llm.is_local_url("https://api.example.com/v1")
    assert llm.get_client() is None  # disabled by default
    settings.update({"llm_enabled": True, "llm_base_url": "https://api.example.com/v1"})
    with pytest.raises(ClipForgeError, match="Allow cloud AI"):
        llm.get_client()  # a cloud address is refused until the user explicitly opts in
