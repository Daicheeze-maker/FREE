import { Download, FolderOpen, Pencil, Play, Search, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../App";
import { Thumb, statusBadge } from "../components/ProjectCard";
import { Badge, Button, Empty, IconButton, Input, Modal, PageHeader, Panel, Segmented, Select } from "../components/ui";
import { usePoll } from "../hooks/usePoll";
import { api, media } from "../lib/api";
import { fmtBytes, fmtDate, fmtDuration } from "../lib/format";
import type { ExportRow, Project } from "../lib/types";
import { toastError, useApp } from "../store";

export default function Library() {
  const { local } = useSession();
  const toast = useApp((s) => s.toast);
  const [tab, setTab] = useState<"projects" | "clips">("projects");
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const projects = usePoll<Project[]>(() => api.get(`/projects?q=${encodeURIComponent(q)}&status=${status}`), 5000, [q, status]);
  const clips = usePoll<ExportRow[]>(() => api.get("/clips/recent?limit=200"), 8000);
  const [rename, setRename] = useState<Project | null>(null);
  const [del, setDel] = useState<Project | null>(null);
  const [name, setName] = useState("");
  const [delExports, setDelExports] = useState(false);

  async function doRename() {
    if (!rename) return;
    try { await api.patch(`/projects/${rename.id}`, { name }); setRename(null); projects.reload(); } catch (e) { toastError(e); }
  }
  async function doDelete() {
    if (!del) return;
    try {
      await api.del(`/projects/${del.id}?delete_exports=${delExports}`);
      toast("ok", "Project deleted.");
      setDel(null); projects.reload(); clips.reload();
    } catch (e) { toastError(e); }
  }
  const shownClips = (clips.data ?? []).filter((c) => !q || (c.title ?? "").toLowerCase().includes(q.toLowerCase()));

  return (
    <div>
      <PageHeader title="Library" subtitle="Saved projects and exported clips"
        actions={<Segmented value={tab} onChange={setTab} options={[{ value: "projects", label: "Projects" }, { value: "clips", label: "Exported clips" }]} />} />
      <div className="mb-3 flex flex-wrap gap-2">
        <div className="relative min-w-48 flex-1">
          <Search size={14} className="pointer-events-none absolute left-2.5 top-2.5 text-faint" />
          <Input className="pl-8" placeholder="Search by name" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        {tab === "projects" && (
          <Select className="w-44" value={status} onChange={(e) => setStatus(e.target.value)}
            options={[{ value: "", label: "All projects" }, { value: "analyzed", label: "Analyzed" }, { value: "imported", label: "Not analyzed" }, { value: "analyzing", label: "Analyzing" }]} />
        )}
      </div>

      {tab === "projects" ? (
        <Panel>
          {projects.data?.length ? (
            <ul className="divide-y divide-line">
              {projects.data.map((p) => (
                <li key={p.id} className="flex items-center gap-3 px-3 py-2.5">
                  <Link to={`/project/${p.id}`} className="shrink-0"><Thumb src={media.projectThumb(p.id)} className="h-12 w-20 rounded-sm" /></Link>
                  <div className="min-w-0 flex-1">
                    <Link to={`/project/${p.id}`} className="block truncate text-[13px] font-medium hover:underline">{p.name}</Link>
                    <div className="tnum mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-faint">
                      {statusBadge(p)}
                      {p.source && <span>{fmtDuration(p.source.duration)} · {p.source.width}×{p.source.height} · {fmtBytes(p.source.size_bytes)}</span>}
                      <span className="hidden sm:inline">· {fmtDate(p.updated_at)}</span>
                      {p.export_count > 0 && <span>· {p.export_count} exported</span>}
                    </div>
                  </div>
                  <IconButton label="Rename" onClick={() => { setRename(p); setName(p.name); }}><Pencil size={14} /></IconButton>
                  <IconButton label="Delete" onClick={() => { setDel(p); setDelExports(false); }}><Trash2 size={14} /></IconButton>
                </li>
              ))}
            </ul>
          ) : <Empty title={q || status ? "No projects match" : "No projects yet"}>{!q && !status && <Link to="/import" className="text-accent hover:underline">Import a video</Link>}</Empty>}
        </Panel>
      ) : (
        <Panel>
          {shownClips.length ? (
            <ul className="divide-y divide-line">
              {shownClips.map((e) => (
                <li key={e.id} className="flex items-center gap-3 px-3 py-2.5">
                  <div className="min-w-0 flex-1">
                    <Link to={`/clip/${e.clip_id}`} className="block truncate text-[13px] font-medium hover:underline">{e.title || "Clip"}</Link>
                    <div className="tnum mt-0.5 text-[11px] text-faint">
                      {fmtDate(e.created_at)} · {e.validation?.info ? `${e.validation.info.width}×${e.validation.info.height}` : ""} · {e.duration ? fmtDuration(e.duration) : ""} · {fmtBytes(e.size_bytes)}
                    </div>
                    <div className="mt-0.5 truncate font-mono text-[10px] text-faint">{e.path}</div>
                  </div>
                  {e.exists ? (
                    <>
                      <a className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-hover hover:text-text" title="Play" href={media.exportFile(e.id)} target="_blank" rel="noreferrer"><Play size={15} /></a>
                      <a className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-hover hover:text-text" title="Download" href={media.exportFile(e.id, true)}><Download size={15} /></a>
                      {local && <IconButton label="Show in folder" onClick={() => api.post(`/media/export/${e.id}/reveal`).catch(toastError)}><FolderOpen size={15} /></IconButton>}
                    </>
                  ) : <Badge tone="warn">file moved or deleted</Badge>}
                </li>
              ))}
            </ul>
          ) : <Empty title="No exported clips yet">Open a project, pick a suggestion and export it.</Empty>}
        </Panel>
      )}

      {rename && (
        <Modal title="Rename project" onClose={() => setRename(null)}
          footer={<><Button onClick={() => setRename(null)}>Cancel</Button><Button variant="primary" onClick={doRename} disabled={!name.trim()}>Save</Button></>}>
          <Input autoFocus value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && doRename()} />
        </Modal>
      )}
      {del && (
        <Modal title="Delete project" onClose={() => setDel(null)}
          footer={<><Button onClick={() => setDel(null)}>Cancel</Button><Button variant="danger" onClick={doDelete}>Delete project</Button></>}>
          <div className="space-y-3 text-xs leading-relaxed text-muted">
            <p>This removes <span className="text-text">{del.name}</span>, its transcript, analysis and clip edits.</p>
            <p>{del.source?.origin === "local"
              ? "Your original video file stays where it is — ClipForge never deletes files it did not create."
              : "The copy of the video stored inside ClipForge is deleted too."}</p>
            {del.export_count > 0 && (
              <label className="flex items-center gap-2 text-text">
                <input type="checkbox" className="accent-[var(--color-accent)]" checked={delExports} onChange={(e) => setDelExports(e.target.checked)} />
                Also delete the {del.export_count} exported video file{del.export_count === 1 ? "" : "s"}
              </label>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
