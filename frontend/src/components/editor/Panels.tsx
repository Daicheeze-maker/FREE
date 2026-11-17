import { Download, FolderOpen, Music, Plus, Trash2, X } from "lucide-react";
import { useRef, useState } from "react";
import { useSession } from "../../App";
import { api, media } from "../../lib/api";
import { clamp, fmtBytes, fmtTime } from "../../lib/format";
import type { CaptionStyle, Clip, CropPlan, Cue, ExportRow, ExportSettings, Job, Source } from "../../lib/types";
import { toastError, useApp } from "../../store";
import { Badge, Button, Field, IconButton, Input, Notice, Progress, Segmented, Select, Slider, Toggle, cx } from "../ui";

type Patch = (p: Partial<Clip>) => void;

const swatch = "h-8 w-10 cursor-pointer rounded-md border border-line bg-bg p-0.5";

/* ------------------------------------------------------------------ captions: style */
export function CaptionStylePanel({ clip, patch, onRegroup, onApplyAll }: { clip: Clip; patch: Patch; onRegroup: (n: number) => void; onApplyAll: () => void }) {
  const meta = useApp((s) => s.meta)!;
  const s = clip.style;
  const set = (v: Partial<CaptionStyle>) => patch({ style: { ...s, ...v, preset: v.preset ?? "custom" } });
  const fonts = Object.entries(meta.fonts);
  return (
    <div className="space-y-3">
      <Field label="Show captions" row><Toggle label="Show captions" checked={clip.captions_enabled} onChange={(v) => patch({ captions_enabled: v })} /></Field>
      <Field label="Preset">
        <div className="grid grid-cols-3 gap-1.5">
          {["dynamic", "minimal", "gaming", "podcast", "custom"].map((p) => (
            <button key={p} onClick={() => { patch({ style: { ...meta.caption_presets[p] } }); if (meta.caption_presets[p].max_words !== s.max_words) onRegroup(meta.caption_presets[p].max_words); }}
              className={cx("h-8 rounded-md border text-xs capitalize", s.preset === p ? "border-accent bg-accent-soft text-accent" : "border-line text-muted hover:text-text")}>{p}</button>
          ))}
        </div>
      </Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Font">
          <Select value={s.font} onChange={(e) => { const f = e.target.value; set({ font: f, weight: meta.fonts[f].includes(s.weight) ? s.weight : meta.fonts[f][0] }); }}
            options={fonts.map(([f]) => ({ value: f, label: f }))} />
        </Field>
        <Field label="Weight">
          <Select value={s.weight} onChange={(e) => set({ weight: Number(e.target.value) })} options={(meta.fonts[s.font] ?? [400]).map((w) => ({ value: w, label: String(w) }))} />
        </Field>
      </div>
      <Field label="Size"><Slider value={s.size} min={2.5} max={10} step={0.1} onChange={(v) => set({ size: v })} format={(v) => v.toFixed(1)} /></Field>
      <div className="flex flex-wrap gap-3">
        <Field label="Text"><input type="color" className={swatch} value={s.color} onChange={(e) => set({ color: e.target.value })} /></Field>
        <Field label="Highlight"><input type="color" className={swatch} value={s.highlight_color} onChange={(e) => set({ highlight_color: e.target.value })} /></Field>
        <Field label="Outline"><input type="color" className={swatch} value={s.outline_color} onChange={(e) => set({ outline_color: e.target.value })} /></Field>
        <Field label="Box"><input type="color" className={swatch} value={s.background_color} onChange={(e) => set({ background_color: e.target.value })} /></Field>
      </div>
      <Field label="Outline width"><Slider value={s.outline} min={0} max={8} step={0.5} onChange={(v) => set({ outline: v })} /></Field>
      <Field label="Shadow"><Slider value={s.shadow} min={0} max={5} step={0.5} onChange={(v) => set({ shadow: v })} /></Field>
      <Field label="Background box" row><Toggle label="Background box" checked={s.background} onChange={(v) => set({ background: v })} /></Field>
      {s.background && <Field label="Box opacity"><Slider value={s.background_opacity} min={0.1} max={1} step={0.05} onChange={(v) => set({ background_opacity: v })} format={(v) => `${Math.round(v * 100)}%`} /></Field>}
      <Field label="Vertical position"><Slider value={s.position_y} min={8} max={92} onChange={(v) => set({ position_y: v })} format={(v) => `${v}%`} /></Field>
      <Field label="Alignment"><Segmented value={s.align} onChange={(v) => set({ align: v })} size="sm" options={[{ value: "left", label: "Left" }, { value: "center", label: "Center" }, { value: "right", label: "Right" }]} /></Field>
      <Field label="Side safe margin"><Slider value={s.safe_margin} min={0} max={20} step={0.5} onChange={(v) => set({ safe_margin: v })} format={(v) => `${v}%`} /></Field>
      <Field label="Max words per caption" hint="Re-flows the caption cues.">
        <Slider value={s.max_words} min={1} max={12} onChange={(v) => { set({ max_words: v }); onRegroup(v); }} />
      </Field>
      <Field label="Highlight"><Segmented value={s.highlight} onChange={(v) => set({ highlight: v })} size="sm" options={[{ value: "none", label: "None" }, { value: "word", label: "Active word" }, { value: "single", label: "One word" }]} /></Field>
      <Field label="Animation"><Segmented value={s.animation} onChange={(v) => set({ animation: v })} size="sm" options={[{ value: "none", label: "None" }, { value: "fade", label: "Fade" }, { value: "pop", label: "Pop" }]} /></Field>
      <Field label="UPPERCASE" row><Toggle label="Uppercase" checked={s.uppercase} onChange={(v) => set({ uppercase: v })} /></Field>
      <Field label="Speaker labels" row><Toggle label="Speaker labels" checked={s.speaker_labels} onChange={(v) => set({ speaker_labels: v })} /></Field>
      <Button size="sm" onClick={onApplyAll}>Apply this style to all clips in the project</Button>
    </div>
  );
}

/* ------------------------------------------------------------------ captions: text + timing */
export function CaptionTextPanel({ cues, setCues, time, activeCue, setActiveCue, seek, wordTiming, clip, onReset }: {
  cues: Cue[]; setCues: (c: Cue[]) => void; time: number; activeCue: string | null; setActiveCue: (id: string | null) => void;
  seek: (t: number) => void; wordTiming: string; clip: Clip; onReset: () => void;
}) {
  const inClip = cues.filter((c) => c.end > clip.start && c.start < clip.end);
  const update = (id: string, v: Partial<Cue>) => setCues(cues.map((c) => (c.id === id ? { ...c, ...v } : c)));
  const add = () => {
    const t = clamp(time, clip.start, clip.end - 0.5);
    setCues([...cues, { id: Math.random().toString(36).slice(2, 10), start: t, end: Math.min(clip.end, t + 1.5), text: "New caption", speaker: "", words: [] }].sort((a, b) => a.start - b.start));
  };
  return (
    <div className="space-y-2">
      <p className="text-[11px] leading-relaxed text-faint">
        {wordTiming === "word" ? "Word timings come from the speech model." : "This speech model gives sentence timing only; word highlight timing inside each caption is estimated."}
        {" "}Times are in the source video. Edits are saved automatically.
      </p>
      <div className="flex gap-1.5">
        <Button size="sm" icon={<Plus size={13} />} onClick={add}>Add at playhead</Button>
        <Button size="sm" variant="ghost" onClick={onReset}>Reset from transcript</Button>
      </div>
      <ul className="space-y-1.5">
        {inClip.map((c) => {
          const live = time >= c.start && time < c.end;
          return (
            <li key={c.id} className={cx("rounded-md border p-2", activeCue === c.id ? "border-accent" : live ? "border-line-strong bg-raised" : "border-line")} onFocus={() => setActiveCue(c.id)}>
              <div className="mb-1 flex items-center gap-1">
                <button className="tnum text-[11px] text-muted hover:text-text" onClick={() => seek(c.start)}>{fmtTime(c.start, true)}</button>
                <TimeNudge value={c.start} onChange={(v) => update(c.id, { start: Math.min(v, c.end - 0.1) })} />
                <span className="text-faint">→</span>
                <span className="tnum text-[11px] text-muted">{fmtTime(c.end, true)}</span>
                <TimeNudge value={c.end} onChange={(v) => update(c.id, { end: Math.max(v, c.start + 0.1) })} />
                <span className="flex-1" />
                <IconButton label="Delete caption" className="h-6 w-6" onClick={() => setCues(cues.filter((x) => x.id !== c.id))}><Trash2 size={12} /></IconButton>
              </div>
              <textarea value={c.text} rows={Math.max(1, Math.ceil(c.text.length / 34))} onChange={(e) => update(c.id, { text: e.target.value })}
                className="w-full resize-none rounded-sm border border-transparent bg-bg px-1.5 py-1 text-[13px] focus:border-accent focus:outline-none" />
              {clip.style.speaker_labels && <Input className="mt-1 h-7 text-xs" placeholder="Speaker" value={c.speaker} onChange={(e) => update(c.id, { speaker: e.target.value })} />}
            </li>
          );
        })}
        {!inClip.length && <li className="py-4 text-center text-xs text-muted">No captions in this clip range.</li>}
      </ul>
    </div>
  );
}

function TimeNudge({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <span className="inline-flex">
      <button className="h-5 w-5 rounded-sm text-[11px] text-faint hover:bg-hover hover:text-text" title="-0.1s" onClick={() => onChange(Math.max(0, value - 0.1))}>‹</button>
      <button className="h-5 w-5 rounded-sm text-[11px] text-faint hover:bg-hover hover:text-text" title="+0.1s" onClick={() => onChange(value + 0.1)}>›</button>
    </span>
  );
}

/* ------------------------------------------------------------------ visual: aspect + crop */
export function VisualPanel({ clip, patch, plan }: { clip: Clip; patch: Patch; plan: CropPlan | null }) {
  const modes = [
    { value: "smart", label: "Smart subject" }, { value: "face", label: "Face tracking" }, { value: "center", label: "Center crop" },
    { value: "manual", label: "Manual" }, { value: "fit_blur", label: "Fit + blur" }, { value: "original", label: "Original" },
  ];
  return (
    <div className="space-y-3">
      <Field label="Aspect ratio">
        <Segmented value={clip.aspect} onChange={(v) => patch({ aspect: v })} size="sm"
          options={[{ value: "9:16", label: "9:16" }, { value: "1:1", label: "1:1" }, { value: "16:9", label: "16:9" }, { value: "original", label: "Source" }]} />
      </Field>
      <Field label="Framing">
        <div className="grid grid-cols-2 gap-1.5">
          {modes.map((m) => (
            <button key={m.value} onClick={() => patch({ crop_mode: m.value })}
              className={cx("h-8 rounded-md border text-xs", clip.crop_mode === m.value ? "border-accent bg-accent-soft text-accent" : "border-line text-muted hover:text-text")}>{m.label}</button>
          ))}
        </div>
      </Field>
      {plan && <Notice>{plan.note}</Notice>}
      {clip.crop_mode === "manual" && (
        <>
          <Field label="Horizontal position"><Slider value={clip.crop.x} min={0} max={1} step={0.005} onChange={(v) => patch({ crop: { ...clip.crop, x: v } })} format={(v) => `${Math.round(v * 100)}%`} /></Field>
          <Field label="Vertical position"><Slider value={clip.crop.y} min={0} max={1} step={0.005} onChange={(v) => patch({ crop: { ...clip.crop, y: v } })} format={(v) => `${Math.round(v * 100)}%`} /></Field>
          <Field label="Zoom"><Slider value={clip.crop.zoom} min={1} max={3} step={0.05} onChange={(v) => patch({ crop: { ...clip.crop, zoom: v } })} format={(v) => `${v.toFixed(2)}×`} /></Field>
        </>
      )}
      <p className="text-[11px] leading-relaxed text-faint">For gameplay, “Smart subject” follows on-screen activity instead of faces. Use “Fit + blur” or “Original” when the HUD or on-screen text must stay visible.</p>
    </div>
  );
}

/* ------------------------------------------------------------------ audio */
export function AudioPanel({ clip, patch, onMusic, onRemoveMusic, source }: { clip: Clip; patch: Patch; onMusic: (f: File) => void; onRemoveMusic: () => void; source: Source }) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <div className="space-y-3">
      {!source.has_audio && <Notice tone="warn">The source video has no audio track.</Notice>}
      <Field label="Mute original audio" row><Toggle label="Mute original audio" checked={clip.mute} onChange={(v) => patch({ mute: v })} /></Field>
      <Field label="Original volume"><Slider value={clip.volume} min={0} max={2} step={0.05} disabled={clip.mute} onChange={(v) => patch({ volume: v })} format={(v) => `${Math.round(v * 100)}%`} /></Field>
      <div className="border-t border-line pt-3">
        <p className="mb-1.5 text-xs text-muted">Background music</p>
        {clip.music_path ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2 rounded-md border border-line px-2 py-1.5 text-xs"><Music size={13} className="text-accent" /><span className="min-w-0 flex-1 truncate">{clip.music_path.split(/[\\/]/).pop()}</span>
              <IconButton label="Remove music" className="h-6 w-6" onClick={onRemoveMusic}><X size={12} /></IconButton></div>
            <Field label="Music volume"><Slider value={clip.music_volume} min={0} max={1.5} step={0.05} onChange={(v) => patch({ music_volume: v })} format={(v) => `${Math.round(v * 100)}%`} /></Field>
            <p className="text-[11px] text-faint">Music loops if it is shorter than the clip.</p>
          </div>
        ) : <Button size="sm" icon={<Music size={13} />} onClick={() => ref.current?.click()}>Add music file</Button>}
        <input ref={ref} type="file" accept="audio/*,.mp3,.wav,.m4a,.aac,.ogg,.flac" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) onMusic(f); e.target.value = ""; }} />
        <p className="mt-2 text-[11px] text-faint">Only use music you have the rights to publish.</p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ export */
export function ExportPanel({ clip, patch, exports, job, onExport }: { clip: Clip; patch: Patch; exports: ExportRow[]; job: Job | null; onExport: () => void }) {
  const meta = useApp((s) => s.meta)!;
  const { local } = useSession();
  const cfg = clip.export_settings;
  const set = (v: Partial<ExportSettings>) => patch({ export_settings: { ...cfg, ...v } });
  const presets = meta.platform_presets;
  const applyPreset = (k: string) => {
    const p = presets[k];
    patch({ aspect: p.aspect, export_settings: { ...cfg, preset: k, resolution: p.resolution, fps: p.fps, codec: p.codec, quality: p.quality, audio_bitrate: p.audio_bitrate, normalize: p.normalize } });
  };
  const running = job && ["queued", "running", "paused"].includes(job.status);
  return (
    <div className="space-y-3">
      <Field label="Platform preset" hint={presets[cfg.preset]?.advice}>
        <Select value={cfg.preset} onChange={(e) => applyPreset(e.target.value)} options={Object.entries(presets).map(([k, p]) => ({ value: k, label: p.label }))} />
      </Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Resolution"><Select value={cfg.resolution} onChange={(e) => set({ resolution: e.target.value })} options={[{ value: "1080p", label: "1080p" }, { value: "720p", label: "720p" }, { value: "original", label: "Original" }]} /></Field>
        <Field label="Frame rate"><Select value={String(cfg.fps)} onChange={(e) => set({ fps: e.target.value === "source" ? "source" : Number(e.target.value) })} options={[{ value: "source", label: "Same as source" }, { value: "24", label: "24" }, { value: "30", label: "30" }, { value: "60", label: "60" }]} /></Field>
        <Field label="Codec"><Select value={cfg.codec} onChange={(e) => set({ codec: e.target.value })} options={[{ value: "h264", label: "H.264" }, { value: "h265", label: "H.265" }]} /></Field>
        <Field label="Quality"><Select value={cfg.quality} onChange={(e) => set({ quality: e.target.value })} options={[{ value: "draft", label: "Draft" }, { value: "standard", label: "Standard" }, { value: "high", label: "High" }]} /></Field>
        <Field label="Video bitrate (kbps)" hint="0 = use quality setting"><Input type="number" min={0} value={cfg.video_bitrate} onChange={(e) => set({ video_bitrate: Math.max(0, Number(e.target.value) || 0) })} /></Field>
        <Field label="Audio bitrate"><Select value={cfg.audio_bitrate} onChange={(e) => set({ audio_bitrate: Number(e.target.value) })} options={[128, 160, 192, 256, 320].map((v) => ({ value: v, label: `${v} kbps` }))} /></Field>
      </div>
      <Field label="Normalize loudness" row><Toggle label="Normalize loudness" checked={cfg.normalize} onChange={(v) => set({ normalize: v })} /></Field>
      <Field label="Burn captions into video" row><Toggle label="Burn captions" checked={cfg.burn_captions} onChange={(v) => set({ burn_captions: v })} /></Field>
      <Field label="Also save .srt" row><Toggle label="Also save SRT" checked={cfg.sidecar_srt} onChange={(v) => set({ sidecar_srt: v })} /></Field>
      <Field label="Also save .vtt" row><Toggle label="Also save VTT" checked={cfg.sidecar_vtt} onChange={(v) => set({ sidecar_vtt: v })} /></Field>
      <Field label="File name"><Input placeholder={clip.title} value={cfg.filename} onChange={(e) => set({ filename: e.target.value })} /></Field>
      {local && <Field label="Output folder" hint="Empty = default export folder"><Input value={cfg.output_dir} onChange={(e) => set({ output_dir: e.target.value })} /></Field>}

      {running && job ? (
        <div className="space-y-1.5 rounded-md border border-line p-2">
          <div className="flex justify-between text-xs"><span>{job.stage === "validate" ? "Validating file" : "Rendering"}</span><span className="tnum text-muted">{Math.round(job.progress * 100)}%</span></div>
          <Progress value={job.progress} />
          <Button size="sm" variant="ghost" onClick={() => api.post(`/jobs/${job.id}/cancel`).catch(toastError)}>Cancel</Button>
        </div>
      ) : <Button variant="primary" className="w-full" icon={<Download size={14} />} onClick={onExport}>Export MP4</Button>}
      {job?.status === "failed" && <Notice tone="danger">{job.error}</Notice>}
      <div className="flex gap-1.5">
        <a className="text-xs text-muted underline hover:text-text" href={`/api/clips/${clip.id}/subtitles.srt`}>Download SRT</a>
        <a className="text-xs text-muted underline hover:text-text" href={`/api/clips/${clip.id}/subtitles.vtt`}>Download VTT</a>
      </div>

      {exports.length > 0 && (
        <div className="space-y-1.5 border-t border-line pt-3">
          <p className="text-xs text-muted">Exports of this clip</p>
          {exports.map((e) => (
            <div key={e.id} className="rounded-md border border-line p-2 text-xs">
              <div className="flex items-center gap-1.5">
                <Badge tone={e.status === "completed" ? (e.validation?.ok ? "ok" : "warn") : e.status === "failed" ? "danger" : "neutral"}>{e.status === "completed" ? "validated" : e.status}</Badge>
                {e.validation?.info && <span className="tnum text-faint">{e.validation.info.width}×{e.validation.info.height} · {fmtBytes(e.size_bytes)}</span>}
                <span className="flex-1" />
                {e.exists && <a className="text-muted hover:text-text" title="Download" href={media.exportFile(e.id, true)}><Download size={13} /></a>}
                {e.exists && local && <button className="text-muted hover:text-text" title="Show in folder" onClick={() => api.post(`/media/export/${e.id}/reveal`).catch(toastError)}><FolderOpen size={13} /></button>}
              </div>
              {e.exists && e.status === "completed" && <video src={media.exportFile(e.id)} controls preload="none" className="mt-1.5 max-h-56 w-full rounded-sm bg-black" />}
              {e.validation?.checks && (
                <details className="mt-1"><summary className="cursor-pointer text-[11px] text-faint">Validation checks</summary>
                  <ul className="mt-1 space-y-0.5">{e.validation.checks.map((c) => <li key={c.name} className={cx("text-[11px]", c.ok ? "text-muted" : "text-danger")}>{c.ok ? "✓" : "✗"} {c.name}: {c.detail}</li>)}</ul>
                </details>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ clip info / AI suggestion */
export function ClipInfo({ clip, patch, candidate, source }: { clip: Clip; patch: Patch; candidate: any; source: Source }) {
  const meta = useApp((s) => s.meta)!;
  const [title, setTitle] = useState(clip.title);
  return (
    <div className="space-y-3">
      <Field label="Title"><Input value={title} onChange={(e) => setTitle(e.target.value)} onBlur={() => title.trim() && title !== clip.title && patch({ title: title.trim() })} /></Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Start (s)"><Input type="number" step={0.1} value={clip.start.toFixed(2)} onChange={(e) => patch({ start: clamp(Number(e.target.value), 0, clip.end - 0.5) })} /></Field>
        <Field label="End (s)"><Input type="number" step={0.1} value={clip.end.toFixed(2)} onChange={(e) => patch({ end: clamp(Number(e.target.value), clip.start + 0.5, source.duration) })} /></Field>
      </div>
      {candidate && candidate.source !== "manual" && (
        <div className="space-y-1.5 rounded-md border border-line p-2.5">
          <div className="flex flex-wrap items-center gap-1.5"><Badge tone="accent">{meta.categories[candidate.category]}</Badge><span className="tnum text-xs">score {Math.round(candidate.score)}</span><span className="tnum text-[11px] text-faint">confidence {Math.round(candidate.confidence * 100)}%</span></div>
          <p className="tnum text-[11px] text-faint">AI suggested {fmtTime(candidate.start, true)} – {fmtTime(candidate.end, true)}</p>
          <p className="text-xs leading-relaxed text-muted">{candidate.reason}</p>
          {(Math.abs(candidate.start - clip.start) > 0.05 || Math.abs(candidate.end - clip.end) > 0.05) &&
            <Button size="sm" variant="ghost" onClick={() => patch({ start: candidate.start, end: candidate.end })}>Restore AI boundaries</Button>}
        </div>
      )}
    </div>
  );
}
