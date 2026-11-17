import { Maximize2, ZoomIn, ZoomOut } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { clamp, fmtTime } from "../../lib/format";
import type { Cue, TimelineData } from "../../lib/types";
import { IconButton, cx } from "../ui";

interface Props {
  duration: number;
  start: number;
  end: number;
  time: number;
  cues: Cue[];
  data: TimelineData | null;
  showCaptions: boolean;
  onSeek: (t: number) => void;
  onTrim: (start: number, end: number) => void;
  onSelectCue: (id: string) => void;
  activeCue: string | null;
}

const EVENT_COLOR: Record<string, string> = { audio: "var(--color-info)", visual: "var(--color-ok)", speech: "var(--color-warn)" };

function initialView(start: number, end: number, duration: number): [number, number] {
  const pad = Math.max(4, (end - start) * 0.35);
  return [Math.max(0, start - pad), Math.min(duration, end + pad)];
}

/** Timeline with video track (scenes), audio waveform, subtitle track, detected events and trim handles. */
export function Timeline({ duration, start, end, time, cues, data, showCaptions, onSeek, onTrim, onSelectCue, activeCue }: Props) {
  const [view, setView] = useState<[number, number]>(() => initialView(start, end, duration));
  const trackRef = useRef<HTMLDivElement>(null);
  const drag = useRef<null | "start" | "end" | "seek">(null);
  const [v0, v1] = view;
  const span = Math.max(0.5, v1 - v0);
  const pct = (t: number) => `${((t - v0) / span) * 100}%`;
  const timeAt = (clientX: number) => {
    const r = trackRef.current!.getBoundingClientRect();
    return v0 + clamp((clientX - r.left) / r.width, 0, 1) * span;
  };

  // keep the clip visible if it was changed from the side panel
  useEffect(() => { if (!drag.current && (start < v0 || end > v1)) setView(initialView(start, end, duration)); }, [start, end]);  // eslint-disable-line

  const zoom = (f: number) => {
    const mid = (start + end) / 2, half = clamp((span * f) / 2, 1, duration);
    setView([Math.max(0, mid - half), Math.min(duration, mid + half)]);
  };

  function down(kind: "start" | "end" | "seek", e: React.PointerEvent) {
    e.stopPropagation();
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    drag.current = kind;
    if (kind === "seek") onSeek(clamp(timeAt(e.clientX), start, end));
  }
  function move(e: React.PointerEvent) {
    if (!drag.current) return;
    const t = Math.round(timeAt(e.clientX) * 20) / 20;  // 50 ms steps
    if (drag.current === "start") onTrim(clamp(t, 0, end - 0.5), end);
    else if (drag.current === "end") onTrim(start, clamp(t, start + 0.5, duration));
    else onSeek(clamp(t, start, end));
  }
  const up = () => { drag.current = null; };

  const ticks = useMemo(() => {
    const steps = [0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600];
    const step = steps.find((s) => span / s <= 10) ?? 600;
    const out: number[] = [];
    for (let t = Math.ceil(v0 / step) * step; t <= v1; t += step) out.push(t);
    return out;
  }, [v0, v1, span]);

  const wave = useMemo(() => {
    const peaks = data?.peaks ?? [];
    if (!peaks.length) return "";
    const n = peaks.length, a = Math.floor((v0 / duration) * n), b = Math.ceil((v1 / duration) * n);
    const pts: string[] = [];
    const cols = Math.min(400, Math.max(1, b - a));
    for (let i = 0; i < cols; i++) {
      const lo = a + Math.floor((i * (b - a)) / cols), hi = Math.max(lo + 1, a + Math.floor(((i + 1) * (b - a)) / cols));
      let m = 0;
      for (let j = lo; j < hi && j < n; j++) m = Math.max(m, peaks[j]);
      const x = (i / cols) * 100, h = Math.max(1, m * 46);
      pts.push(`M${x.toFixed(2)},${(50 - h).toFixed(1)}V${(50 + h).toFixed(1)}`);
    }
    return pts.join("");
  }, [data, v0, v1, duration]);

  const scenes = (data?.scenes ?? []).filter((s) => s.end > v0 && s.start < v1);
  const events = (data?.events ?? []).filter((e) => e.end > v0 && e.start < v1 && e.kind !== "pause" && !e.kind.startsWith("speech_"));
  const visCues = cues.filter((c) => c.end > v0 && c.start < v1);

  return (
    <div className="select-none border-t border-line bg-surface">
      <div className="flex items-center gap-1 border-b border-line px-2 py-1">
        <span className="tnum text-xs text-muted">In {fmtTime(start, true)} · Out {fmtTime(end, true)} · <span className="text-text">{(end - start).toFixed(1)}s</span></span>
        <span className="flex-1" />
        <IconButton label="Zoom out" onClick={() => zoom(1.6)}><ZoomOut size={14} /></IconButton>
        <IconButton label="Zoom in" onClick={() => zoom(0.6)}><ZoomIn size={14} /></IconButton>
        <IconButton label="Fit clip" onClick={() => setView(initialView(start, end, duration))}><Maximize2 size={14} /></IconButton>
      </div>
      <div className="flex">
        <div className="hidden w-16 shrink-0 flex-col border-r border-line text-[10px] uppercase tracking-wide text-faint sm:flex">
          <div className="h-5" /><Label h="h-7">Video</Label><Label h="h-10">Audio</Label><Label h="h-7">Subs</Label><Label h="h-4">Events</Label>
        </div>
        <div ref={trackRef} className="relative min-w-0 flex-1 touch-none overflow-hidden" onPointerDown={(e) => down("seek", e)} onPointerMove={move} onPointerUp={up} onPointerCancel={up}>
          <div className="relative h-5 border-b border-line">
            {ticks.map((t) => <span key={t} className="tnum absolute top-0.5 -translate-x-1/2 text-[10px] text-faint" style={{ left: pct(t) }}>{fmtTime(t)}</span>)}
          </div>
          <div className="relative h-7 border-b border-line">
            {scenes.map((s, i) => <div key={i} className="absolute inset-y-1 rounded-sm border border-line-strong bg-raised" style={{ left: pct(Math.max(s.start, v0)), width: `${((Math.min(s.end, v1) - Math.max(s.start, v0)) / span) * 100}%` }} />)}
          </div>
          <div className="relative h-10 border-b border-line">
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full"><path d={wave} stroke="var(--color-muted)" strokeWidth="0.18" vectorEffect="non-scaling-stroke" style={{ strokeWidth: 1 }} /></svg>
            {!data?.peaks.length && <span className="absolute inset-0 flex items-center justify-center text-[10px] text-faint">no audio waveform</span>}
          </div>
          <div className="relative h-7 border-b border-line">
            {showCaptions && visCues.map((c) => (
              <button key={c.id} onPointerDown={(e) => e.stopPropagation()} onClick={() => { onSelectCue(c.id); onSeek(clamp(c.start + 0.01, start, end)); }}
                title={c.text}
                className={cx("absolute inset-y-1 overflow-hidden truncate rounded-sm border px-1 text-left text-[10px] leading-[18px]",
                  activeCue === c.id ? "border-accent bg-accent-soft text-text" : "border-line-strong bg-hover text-muted")}
                style={{ left: pct(c.start), width: `${((c.end - c.start) / span) * 100}%` }}>{c.text}</button>
            ))}
          </div>
          <div className="relative h-4">
            {events.map((e) => <span key={e.id} title={`${e.label} (${fmtTime(e.start)})`} className="absolute top-1 h-2 min-w-1 rounded-full opacity-80"
              style={{ left: pct(Math.max(e.start, v0)), width: `${Math.max(0.4, ((Math.min(e.end, v1) - Math.max(e.start, v0)) / span) * 100)}%`, background: EVENT_COLOR[e.modality] }} />)}
          </div>

          {/* outside-the-clip shading, clip frame, handles and playhead */}
          <div className="pointer-events-none absolute inset-y-5 left-0 bg-bg/70" style={{ width: pct(start) }} />
          <div className="pointer-events-none absolute inset-y-5 right-0 bg-bg/70" style={{ left: pct(end) }} />
          <div className="pointer-events-none absolute inset-y-5 border-y-2 border-accent" style={{ left: pct(start), width: `${((end - start) / span) * 100}%` }} />
          {(["start", "end"] as const).map((k) => (
            <div key={k} role="slider" aria-label={k === "start" ? "Clip start" : "Clip end"} aria-valuenow={k === "start" ? start : end} tabIndex={0}
              onPointerDown={(e) => down(k, e)}
              onKeyDown={(e) => {
                const d = e.key === "ArrowLeft" ? -0.1 : e.key === "ArrowRight" ? 0.1 : 0;
                if (!d) return;
                if (k === "start") onTrim(clamp(start + d, 0, end - 0.5), end); else onTrim(start, clamp(end + d, start + 0.5, duration));
              }}
              className="absolute inset-y-5 z-10 flex w-4 -translate-x-1/2 cursor-ew-resize touch-none items-center justify-center"
              style={{ left: pct(k === "start" ? start : end) }}>
              <div className="h-full w-1.5 rounded-sm bg-accent" />
            </div>
          ))}
          <div className="pointer-events-none absolute inset-y-0 z-20 w-px bg-white" style={{ left: pct(clamp(time, v0, v1)) }}><div className="-ml-1 h-2 w-2 rounded-full bg-white" /></div>
        </div>
      </div>
    </div>
  );
}

function Label({ children, h }: { children: React.ReactNode; h: string }) {
  return <div className={cx("flex items-center border-b border-line px-2", h)}>{children}</div>;
}
