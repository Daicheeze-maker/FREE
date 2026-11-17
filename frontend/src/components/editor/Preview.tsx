import { Pause, Play, SkipBack, Volume2, VolumeX } from "lucide-react";
import { useEffect, useRef, useState, type RefObject } from "react";
import { media } from "../../lib/api";
import { clamp, fmtTime } from "../../lib/format";
import type { CaptionStyle, Clip, CropPlan, Cue, Source } from "../../lib/types";
import { IconButton, cx } from "../ui";

/** Crop-box centre at clip time t, using the same rule as the renderer (linear, hard switch at cuts). */
export function cropAt(plan: CropPlan, t: number): [number, number] {
  const k = plan.keys;
  if (k.length === 1 || t <= k[0][0]) return [k[0][1], k[0][2]];
  for (let i = 0; i < k.length - 1; i++) {
    const a = k[i], b = k[i + 1];
    if (t < b[0]) {
      if ((plan.cuts ?? []).some((c) => Math.abs(c - b[0]) < 0.002)) return [a[1], a[2]];
      const f = (t - a[0]) / Math.max(1e-3, b[0] - a[0]);
      return [a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2])];
    }
  }
  const last = k[k.length - 1];
  return [last[1], last[2]];
}

const ASPECT: Record<string, number> = { "9:16": 9 / 16, "16:9": 16 / 9, "1:1": 1 };

interface Props {
  clip: Clip;
  source: Source;
  cues: Cue[];
  plan: CropPlan | null;
  videoRef: RefObject<HTMLVideoElement | null>;
  onTime: (t: number) => void;
  onPlaying: (p: boolean) => void;
  playing: boolean;
  hasMusic: boolean;
}

/** Live preview: real video, crop path applied with CSS, captions drawn with the clip's style. */
export function Preview({ clip, source, cues, plan, videoRef, onTime, onPlaying, playing, hasMusic }: Props) {
  const frameRef = useRef<HTMLDivElement>(null);
  const blurRef = useRef<HTMLCanvasElement>(null);
  const musicRef = useRef<HTMLAudioElement>(null);
  const [now, setNow] = useState(clip.start);
  const clipRef = useRef(clip);
  clipRef.current = clip;
  const planRef = useRef(plan);
  planRef.current = plan;
  const effective = plan?.effective ?? "center";
  const srcAspect = source.width / source.height;
  const outAspect = effective === "original" || !ASPECT[clip.aspect] ? srcAspect : ASPECT[clip.aspect];

  // One animation-frame loop drives crop position, clip bounds, the blurred backdrop and caption timing.
  useEffect(() => {
    let raf = 0, lastSent = 0;
    const loop = () => {
      const v = videoRef.current, c = clipRef.current, p = planRef.current;
      if (v) {
        if (!v.paused && v.currentTime >= c.end) { v.pause(); v.currentTime = c.start; }
        if (v.currentTime < c.start - 0.25 || v.currentTime > c.end + 0.25) v.currentTime = c.start;
        const t = v.currentTime;
        setNow(t);
        if (performance.now() - lastSent > 100) { lastSent = performance.now(); onTime(t); }
        if (p && p.effective !== "original" && p.effective !== "fit_blur") {
          const [cx_, cy_] = cropAt(p, t - c.start);
          const [bw, bh] = p.box;
          v.style.width = `${100 / bw}%`;
          v.style.height = `${100 / bh}%`;
          v.style.left = `${(-(cx_ - bw / 2) / bw) * 100}%`;
          v.style.top = `${(-(cy_ - bh / 2) / bh) * 100}%`;
        }
        const cv = blurRef.current;
        if (cv && p?.effective === "fit_blur" && v.readyState >= 2) {
          const g = cv.getContext("2d");
          if (g) {
            const s = Math.max(cv.width / v.videoWidth, cv.height / v.videoHeight);
            const w = v.videoWidth * s, h = v.videoHeight * s;
            g.drawImage(v, (cv.width - w) / 2, (cv.height - h) / 2, w, h);
          }
        }
        const m = musicRef.current;
        if (m && m.duration) {
          if (!v.paused && m.paused) { m.currentTime = (t - c.start) % m.duration; m.play().catch(() => {}); }
          if (v.paused && !m.paused) m.pause();
        }
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [videoRef, onTime]);

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    v.volume = clamp(clip.volume, 0, 1);
    v.muted = clip.mute;
    if (musicRef.current) musicRef.current.volume = clamp(clip.music_volume, 0, 1);
  }, [clip.volume, clip.mute, clip.music_volume, videoRef]);

  const toggle = () => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) { if (v.currentTime >= clip.end - 0.05) v.currentTime = clip.start; v.play().catch(() => {}); } else v.pause();
  };
  const cropped = effective !== "original" && effective !== "fit_blur";
  const rel = clamp(now - clip.start, 0, clip.end - clip.start);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex min-h-0 flex-1 items-center justify-center p-2">
        <div ref={frameRef} className="relative max-h-full max-w-full overflow-hidden rounded-md bg-black"
          style={{ aspectRatio: String(outAspect), height: outAspect < 1 ? "100%" : undefined, width: outAspect >= 1 ? "100%" : undefined, containerType: "size" }}
          onClick={toggle}>
          {effective === "fit_blur" && <canvas ref={blurRef} width={90} height={Math.round(90 / outAspect)} className="absolute inset-0 h-full w-full scale-125 blur-[14px]" />}
          <video ref={videoRef} src={media.video(clip.project_id)} playsInline preload="auto"
            onPlay={() => onPlaying(true)} onPause={() => onPlaying(false)}
            onLoadedMetadata={(e) => { e.currentTarget.currentTime = clip.start; }}
            className={cx("absolute", cropped ? "max-w-none object-fill" : "inset-0 h-full w-full object-contain")}
            style={cropped ? undefined : { width: "100%", height: "100%", left: 0, top: 0 }} />
          {clip.captions_enabled && <CaptionOverlay cues={cues} style={clip.style} t={now} />}
          {hasMusic && <audio ref={musicRef} src={`/api/media/music/${clip.id}?v=${encodeURIComponent(clip.music_path ?? "")}`} loop preload="auto" />}
        </div>
      </div>
      <div className="flex items-center gap-1 border-t border-line px-2 py-1.5">
        <IconButton label="Back to start" onClick={() => { const v = videoRef.current; if (v) v.currentTime = clip.start; }}><SkipBack size={15} /></IconButton>
        <IconButton label={playing ? "Pause" : "Play"} onClick={toggle} className="bg-accent text-white hover:bg-accent-hover hover:text-white">{playing ? <Pause size={15} /> : <Play size={15} />}</IconButton>
        <span className="tnum ml-1 text-xs text-muted">{fmtTime(rel, true)} / {fmtTime(clip.end - clip.start, true)}</span>
        <span className="flex-1" />
        <span className="hidden text-[11px] text-faint sm:inline">Preview approximates the final render</span>
        {clip.mute ? <VolumeX size={14} className="text-faint" /> : <Volume2 size={14} className="text-faint" />}
      </div>
    </div>
  );
}

function rgba(hex: string, a: number) {
  const h = hex.replace("#", "");
  return `rgba(${parseInt(h.slice(0, 2), 16)},${parseInt(h.slice(2, 4), 16)},${parseInt(h.slice(4, 6), 16)},${a})`;
}

/** Captions rendered from the same cues and style that the exporter burns in. Sizes are relative to the frame height. */
export function CaptionOverlay({ cues, style: s, t }: { cues: Cue[]; style: CaptionStyle; t: number }) {
  const cue = cues.find((c) => t >= c.start && t < c.end);
  if (!cue) return null;
  const words = cue.words?.length ? cue.words : [{ w: cue.text, start: cue.start, end: cue.end }];
  let active = -1;
  for (let i = 0; i < words.length; i++) if (t >= words[i].start) active = i;
  const px = (v: number) => `${(v / 1080) * 100}cqh`;
  const show = s.highlight === "single" ? [words[Math.max(0, active)]] : words;
  const anim = s.animation === "pop" ? "cap-pop 110ms ease-out" : s.animation === "fade" ? "cap-fade 120ms ease-out" : undefined;
  return (
    <div className="pointer-events-none absolute" style={{ left: `${s.safe_margin}%`, right: `${s.safe_margin}%`, top: `${s.position_y}%`, transform: "translateY(-50%)", textAlign: s.align }}>
      <span key={cue.id + (s.highlight === "single" ? active : "")}
        style={{
          display: "inline-block", animation: anim, fontFamily: `"${s.font}", sans-serif`, fontWeight: s.weight, fontSize: `${s.size}cqh`,
          lineHeight: 1.18, color: s.color, textTransform: s.uppercase ? "uppercase" : undefined, textWrap: "balance",
          WebkitTextStroke: s.background || !s.outline ? undefined : `${px(s.outline * 2)} ${s.outline_color}`, paintOrder: "stroke fill",
          textShadow: s.background || !s.shadow ? undefined : `${px(s.shadow)} ${px(s.shadow)} 0 rgba(0,0,0,0.5)`,
          background: s.background ? rgba(s.background_color, s.background_opacity) : undefined,
          padding: s.background ? "0.12em 0.4em" : undefined, borderRadius: s.background ? "0.12em" : undefined,
        }}>
        {s.speaker_labels && cue.speaker ? `${cue.speaker}: ` : ""}
        {show.map((w, i) => {
          const isActive = s.highlight === "single" || (s.highlight === "word" && i === active);
          return <span key={i} style={{ color: isActive ? s.highlight_color : undefined }}>{w.w}{i < show.length - 1 ? " " : ""}</span>;
        })}
      </span>
    </div>
  );
}
