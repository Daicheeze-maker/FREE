"""Generate the test videos used by the automated tests.

    python backend/tests/make_fixture.py [output_dir] [--laugh path/to/laughter.wav]

Requires an FFmpeg build with the `flite` speech-synthesis filter (standard on most
Linux distributions). The generated `speech_scene.mp4` is committed in tests/fixtures so
the tests also run where flite is unavailable (e.g. common Windows FFmpeg builds).

speech_scene.mp4 (42 s, 640x360) contains, at known times:
  1.0 s   a spoken story ("...my cat was sitting inside eating the cake.")
  9.5 s   optional real laughter (only when --laugh is given)
  15.0 s  a spoken tip ("Here is an important tip. ...")
  27.0 s  a question and its answer
  35.0 s  a loud noise burst
  36.5 s  "Wait, what was that? No way!"
  scene changes at 14 s and 26 s
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

LINES = [
    (1.0, "Okay so here is the craziest thing that happened to me yesterday. "
          "I opened the fridge and my cat was sitting inside eating the cake."),
    (15.0, "Here is an important tip. The best way to learn editing is to cut one short video every single day. "
           "Remember, practice matters more than gear."),
    (27.0, "Do you know why this works? Because small habits add up over time."),
    (36.5, "Wait, what was that? No way!"),
]
DURATION = 42


def ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-y", "-v", "error", *args], check=True)


def make(out_dir: Path, laugh: str | None = None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / "_tmp"
    tmp.mkdir(exist_ok=True)
    inputs, filters, labels = [], [], []
    for i, (t, text) in enumerate(LINES):
        wav = tmp / f"s{i}.wav"
        txt = tmp / f"s{i}.txt"
        txt.write_text(text)
        ff("-f", "lavfi", "-i", f"flite=textfile={txt.as_posix()}:voice=slt", "-ar", "44100", str(wav))
        inputs += ["-i", str(wav)]
        filters.append(f"[{i}:a]adelay={int(t * 1000)}:all=1[s{i}]")
        labels.append(f"[s{i}]")
    n = len(LINES)
    inputs += ["-f", "lavfi", "-t", "0.5", "-i", "anoisesrc=color=white:amplitude=0.9:sample_rate=44100"]
    filters.append(f"[{n}:a]adelay=35000:all=1[burst]")
    labels.append("[burst]")
    n += 1
    if laugh:
        inputs += ["-t", "4.5", "-i", laugh]
        filters.append(f"[{n}:a]aresample=44100,volume=1.6,adelay=9500:all=1[laugh]")
        labels.append("[laugh]")
        n += 1
    # quiet room tone so silence is not digital zero
    inputs += ["-f", "lavfi", "-t", str(DURATION), "-i", "anoisesrc=color=pink:amplitude=0.003:sample_rate=44100"]
    labels.append(f"[{n}:a]")
    filters.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,"
                   f"atrim=0:{DURATION},aformat=channel_layouts=stereo[a]")
    video = ("testsrc2=s=640x360:r=25:d=14[v0];smptehdbars=s=640x360:r=25:d=12[v1];"
             "rgbtestsrc=s=640x360:r=25:d=16[v2];[v0][v1][v2]concat=n=3:v=1:a=0[v]")
    ff(*inputs, "-filter_complex", video + ";" + ";".join(filters), "-map", "[v]", "-map", "[a]",
       "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "96k", "-t", str(DURATION), str(out_dir / "speech_scene.mp4"))
    # video with no audio track
    ff("-f", "lavfi", "-i", "testsrc2=s=320x180:r=25:d=6", "-c:v", "libx264", "-preset", "veryfast",
       "-pix_fmt", "yuv420p", str(out_dir / "no_audio.mp4"))
    # still picture with near silence: nothing interesting happens
    ff("-f", "lavfi", "-i", "color=c=gray:s=320x180:r=25:d=20", "-f", "lavfi", "-t", "20",
       "-i", "anoisesrc=color=pink:amplitude=0.002", "-c:v", "libx264", "-preset", "veryfast",
       "-pix_fmt", "yuv420p", "-c:a", "aac", str(out_dir / "boring.mp4"))
    # corrupted file: valid extension, garbage content
    (out_dir / "corrupted.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + bytes(range(256)) * 40)
    for f in tmp.iterdir():
        f.unlink()
    tmp.rmdir()


if __name__ == "__main__":
    args = sys.argv[1:]
    laugh = None
    if "--laugh" in args:
        i = args.index("--laugh")
        laugh = args[i + 1]
        del args[i:i + 2]
    make(Path(args[0]) if args else Path(__file__).parent / "fixtures", laugh)
    print("fixtures written")
