---
tags: [clipforge, guide]
---
# User guide

Back to [[Home]]

## 1. Import a video
**Dashboard** or **Import**:
- **Browse this computer**: pick a file; it is used where it is (no copy).
- **Drop a file** or **Upload a copy**: the file is copied into ClipForge's data folder.
- **Paste a full path**, e.g. `D:\Streams\2024-05-01.mkv`.
- **YouTube link**: check the link, confirm you own it or have permission, then download. Private, age-restricted, members-only and DRM videos are refused.

Supported: MP4, MOV, MKV, WebM, AVI, M4V (anything your FFmpeg can decode). Corrupted files are rejected with a message. Importing the same file twice opens the existing project. Formats a browser cannot play (MKV, HEVC, 10-bit) get a 720p preview copy automatically. Analysis and exports always use the original.

## 2. Analysis settings
On the project page choose:
- **What to look for**: Funny, Reactions, Unexpected, Epic, Conversations, Educational, Emotional, Important statements
- **Shortest / longest clip** and **number of suggestions**
- **Aspect ratio** (9:16 default), **spoken language**, **caption style**
- **Analysis intensity**: Performance / Balanced / Quality (frame and audio sampling density)
- Advanced: audio normalization, whether to use the local vision model

## 3. Watch the analysis
Eight stages with measured progress: ingestion, audio extraction, transcription, visual analysis, event detection, context analysis, clip generation, captions. The transcript appears as it is produced. You can **Pause**, **Resume** or **Cancel**. A failed or cancelled analysis can be **Resumed**, and finished stages are not redone.

## 4. Review suggestions
Each card shows a real thumbnail, category, score, time range, confidence and the reason it was picked. Click the thumbnail to preview the clip and see the eight sub-scores and transcript. You can:
- **Reject** a suggestion (or restore it from *Rejected*)
- **Custom AI search**: describe a moment ("when they talk about the boss fight"). With the vision/context model this is a semantic search; without it, a transcript text match (labelled as such).
- **Manual clip**: set start/end on the video yourself
- **Export** directly, or **Edit**

Scores estimate how interesting the content is. They are not a prediction of views. See [[How Clip Selection Works]].

## 5. Edit
- **Left**: *Clip* (title, exact start/end, restore AI boundaries) · *Style* (presets Dynamic / Minimal / Gaming / Podcast / Custom; font, size, colours, outline, shadow, box, position, alignment, words per caption, highlight, animation, uppercase, speaker labels, safe margin, apply to all clips) · *Captions* (edit text, nudge times by 0.1 s, add or delete captions, reset from transcript) · *Crop* (aspect ratio and framing) · *Audio* (volume, mute, background music)
- **Center**: preview with the real crop path and styled captions
- **Bottom**: timeline with scenes, waveform, captions and detected events; drag the orange handles to trim
- **Right**: export settings and past exports with their validation report

Edits save automatically and are exactly what gets rendered. The preview closely matches the render; the burned-in captions come from the same cues and style.

**Framing modes:** Smart subject (follows the main face, or on-screen activity for gameplay), Face tracking, Center crop, Manual (position + zoom), Fit + blur (whole frame on a blurred background, so nothing is cut), Original. For gameplay with important HUD or text, use Fit + blur or Original.

## 6. Export
Presets for TikTok, YouTube Shorts, Instagram Reels and general use set encoding only (1080×1920 H.264/AAC MP4). Length limits change often, so check the platform's help page; the preset links to it. Options: resolution, frame rate, H.264/H.265, quality or bitrate, audio bitrate, loudness normalization, burn captions, extra SRT/VTT files, file name, output folder.

Every export is checked before it is kept: streams present, resolution, duration, a full decode of every frame, and caption timing. Only a validated file reaches your output folder.

## 7. Library
Search and filter projects, rename, delete, reopen. Deleting a project never deletes your original video. Exported files are deleted only if you tick that option. *Exported clips* lists every export with play, download and show-in-folder.

## Phone access
1. On the PC: Settings → **Privacy & devices** → turn on **Allow devices on my network**, then restart ClipForge.
2. On the phone (same Wi-Fi), open the address shown, e.g. `http://192.168.1.20:8756`.
3. Enter the 6-digit PIN shown on the PC.

The phone gets the full studio with a mobile layout: upload videos from the phone, review clips, edit, export, and download the finished MP4 to the phone. All processing still happens on the PC. If the phone cannot connect, allow ClipForge through Windows Firewall for **Private** networks. Turn this off on networks you do not trust.
