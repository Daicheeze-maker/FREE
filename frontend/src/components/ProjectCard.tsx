import { Film } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { media } from "../lib/api";
import { fmtDuration } from "../lib/format";
import type { Project } from "../lib/types";
import { Badge, Progress } from "./ui";

export function statusBadge(p: Project) {
  if (p.source_missing) return <Badge tone="danger">source missing</Badge>;
  if (p.active_job) return <Badge tone="accent">{p.active_job.type === "proxy" ? "preparing" : "analyzing"}</Badge>;
  if (p.status === "analyzed") return <Badge tone="ok">{p.clip_count} clip{p.clip_count === 1 ? "" : "s"}</Badge>;
  return <Badge>not analyzed</Badge>;
}

/** Real thumbnail extracted from the video; a neutral icon tile if the frame could not be read. */
export function Thumb({ src, className }: { src: string; className?: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <div className={`flex items-center justify-center bg-raised text-faint ${className ?? ""}`}><Film size={20} /></div>;
  return <img src={src} alt="" loading="lazy" onError={() => setFailed(true)} className={`bg-raised object-cover ${className ?? ""}`} />;
}

export function ProjectCard({ project: p }: { project: Project }) {
  return (
    <Link to={`/project/${p.id}`} className="group overflow-hidden rounded-lg border border-line bg-surface transition-colors hover:border-line-strong">
      <div className="relative aspect-video">
        <Thumb src={media.projectThumb(p.id)} className="h-full w-full" />
        {p.source && <span className="tnum absolute bottom-1 right-1 rounded-sm bg-black/75 px-1 text-[11px]">{fmtDuration(p.source.duration)}</span>}
      </div>
      <div className="space-y-1.5 p-2.5">
        <p className="truncate text-[13px] font-medium">{p.name}</p>
        <div className="flex items-center justify-between gap-2">
          {statusBadge(p)}
          {p.source && <span className="tnum text-[11px] text-faint">{p.source.width}×{p.source.height}</span>}
        </div>
        {p.active_job && <Progress value={p.active_job.progress} />}
      </div>
    </Link>
  );
}
