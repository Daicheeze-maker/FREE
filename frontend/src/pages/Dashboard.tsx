import { Download, Film, HardDrive, Play } from "lucide-react";
import { Link } from "react-router-dom";
import { useSession } from "../App";
import { ImportPanel } from "../components/ImportPanel";
import { ProjectCard } from "../components/ProjectCard";
import { Badge, Empty, PageHeader, Panel, Progress, Stat } from "../components/ui";
import { usePoll } from "../hooks/usePoll";
import { api, media } from "../lib/api";
import { fmtBytes, fmtDate, fmtDuration, fmtEta } from "../lib/format";
import type { ExportRow, Job, Project } from "../lib/types";

export default function Dashboard() {
  const { local } = useSession();
  const projects = usePoll<Project[]>(() => api.get("/projects"), 4000);
  const jobs = usePoll<Job[]>(() => api.get("/jobs?active=true"), 1500);
  const clips = usePoll<ExportRow[]>(() => api.get("/clips/recent?limit=8"), 6000);
  const status = usePoll<any>(() => api.get("/system/status"), 15000);
  const names = Object.fromEntries((projects.data ?? []).map((p) => [p.id, p.name]));
  const st = status.data;

  return (
    <div className="space-y-5">
      <PageHeader title="Dashboard" subtitle="Your AI watches. Your AI listens. Your AI finds the moments." />
      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <ImportPanel isLocal={local} compact />
        <div className="space-y-4">
          <Panel title="Processing">
            {jobs.data?.length ? (
              <ul className="divide-y divide-line">
                {jobs.data.map((j) => (
                  <li key={j.id} className="space-y-1.5 px-3 py-2.5">
                    <div className="flex items-center justify-between gap-2 text-xs">
                      <Link to={j.project_id ? `/project/${j.project_id}` : "/settings"} className="min-w-0 truncate text-text hover:underline">
                        {j.type === "model_download" ? "Model download" : names[j.project_id ?? ""] ?? j.type}
                      </Link>
                      <Badge tone={j.status === "running" ? "accent" : "neutral"}>{j.status}</Badge>
                    </div>
                    <Progress value={j.progress} />
                    <div className="flex justify-between text-[11px] text-faint">
                      <span className="truncate">{j.stage?.replace(/_/g, " ") ?? "waiting"}</span>
                      <span className="tnum">{Math.round(j.progress * 100)}% {fmtEta(j.eta_seconds)}</span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : <p className="px-3 py-4 text-xs text-muted">Nothing is running.</p>}
          </Panel>
          <Panel title="Storage">
            <div className="grid grid-cols-2 gap-3 p-3">
              <Stat label="Free space" value={st ? `${st.disk.free_gb} GB` : "–"} />
              <Stat label="Disk size" value={st ? `${st.disk.total_gb} GB` : "–"} />
              <div className="col-span-2"><Stat label="Data folder" value={<span className="font-mono text-[11px]">{st?.data_dir ?? "–"}</span>} /></div>
              {st && st.disk.free_gb < 10 && <p className="col-span-2 text-[11px] text-warn">Low disk space: analysis and exports may fail.</p>}
            </div>
          </Panel>
        </div>
      </div>

      <section>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">Recent projects</h2>
          <Link to="/library" className="text-xs text-muted hover:text-text">View all</Link>
        </div>
        {projects.data?.length ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {projects.data.slice(0, 8).map((p) => <ProjectCard key={p.id} project={p} />)}
          </div>
        ) : (
          <Panel><Empty icon={<Film size={24} />} title="No projects yet">Import a video above to let the AI find its best moments.</Empty></Panel>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Recent clips</h2>
        {clips.data?.length ? (
          <Panel>
            <ul className="divide-y divide-line">
              {clips.data.map((e) => (
                <li key={e.id} className="flex items-center gap-3 px-3 py-2">
                  <HardDrive size={14} className="shrink-0 text-faint" />
                  <div className="min-w-0 flex-1">
                    <Link to={`/clip/${e.clip_id}`} className="block truncate text-[13px] hover:underline">{e.title || "Clip"}</Link>
                    <div className="tnum text-[11px] text-faint">{fmtDate(e.created_at)} · {e.duration ? fmtDuration(e.duration) : ""} · {fmtBytes(e.size_bytes)}</div>
                  </div>
                  {e.exists ? (
                    <>
                      <a href={media.exportFile(e.id)} target="_blank" rel="noreferrer" className="text-muted hover:text-text" title="Play"><Play size={15} /></a>
                      <a href={media.exportFile(e.id, true)} className="text-muted hover:text-text" title="Download"><Download size={15} /></a>
                    </>
                  ) : <Badge tone="warn">file moved</Badge>}
                </li>
              ))}
            </ul>
          </Panel>
        ) : <p className="text-xs text-muted">Exported clips will appear here.</p>}
      </section>
    </div>
  );
}
