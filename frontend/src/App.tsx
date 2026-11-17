import { Clapperboard, FolderKanban, LayoutDashboard, Settings as SettingsIcon, Upload, X } from "lucide-react";
import { createContext, useContext, useEffect, useState } from "react";
import { HashRouter, NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Button, Input, Notice, Progress, Spinner, cx } from "./components/ui";
import { usePoll } from "./hooks/usePoll";
import { api } from "./lib/api";
import type { Job, Meta } from "./lib/types";
import Dashboard from "./pages/Dashboard";
import Editor from "./pages/Editor";
import ImportPage from "./pages/Import";
import Library from "./pages/Library";
import ProjectPage from "./pages/Project";
import SettingsPage from "./pages/Settings";
import Setup from "./pages/Setup";
import { useApp } from "./store";

interface Session { authenticated: boolean; local: boolean; needs_pin: boolean }
const SessionCtx = createContext<Session>({ authenticated: false, local: false, needs_pin: false });
export const useSession = () => useContext(SessionCtx);

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/import", label: "Import", icon: Upload },
  { to: "/library", label: "Library", icon: FolderKanban },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<any>(null);
  const setMeta = useApp((s) => s.setMeta);

  const boot = async () => {
    try {
      const s = await api.get<Session>("/session");
      setSession(s);
      if (s.authenticated) {
        const [meta, st] = await Promise.all([api.get<Meta>("/meta"), api.get("/system/status")]);
        setMeta(meta);
        setStatus(st);
      }
      setError(null);
    } catch (e: any) {
      setError("ClipForge's local engine is not responding. Make sure the application is running, then try again.");
    }
  };
  useEffect(() => { boot(); }, []);

  if (error) return <Centered><Notice tone="danger">{error}</Notice><Button onClick={boot}>Try again</Button></Centered>;
  if (!session) return <Centered><Spinner size={22} /></Centered>;
  if (!session.authenticated) return <Pair onPaired={boot} />;
  if (!status) return <Centered><Spinner size={22} /></Centered>;

  return (
    <SessionCtx.Provider value={session}>
      <HashRouter>
        {!status.setup_complete && session.local ? (
          <Setup onDone={boot} />
        ) : (
          <Shell>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/import" element={<ImportPage />} />
              <Route path="/library" element={<Library />} />
              <Route path="/project/:id" element={<ProjectPage />} />
              <Route path="/clip/:id" element={<Editor />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Shell>
        )}
        <Toasts />
      </HashRouter>
    </SessionCtx.Provider>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return <div className="flex h-full flex-col items-center justify-center gap-3 p-6">{children}</div>;
}

function Logo() {
  return (
    <div className="flex items-center gap-2">
      <div className="flex h-7 w-7 items-center justify-center rounded-md bg-accent"><Clapperboard size={15} className="text-bg" /></div>
      <div className="leading-tight">
        <div className="text-[13px] font-semibold tracking-tight">ClipForge</div>
        <div className="text-[10px] uppercase tracking-widest text-faint">AI Studio</div>
      </div>
    </div>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  const loc = useLocation();
  const fullBleed = loc.pathname.startsWith("/clip/");
  return (
    <div className="flex h-full flex-col md:flex-row">
      <aside className="hidden w-52 shrink-0 flex-col border-r border-line bg-surface md:flex">
        <div className="px-3 py-3.5"><Logo /></div>
        <nav className="flex-1 space-y-0.5 px-2">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end}
              className={({ isActive }) => cx("flex h-8 items-center gap-2.5 rounded-md px-2.5 text-[13px] transition-colors",
                isActive ? "bg-hover text-text" : "text-muted hover:bg-hover/60 hover:text-text")}>
              <n.icon size={15} />{n.label}
            </NavLink>
          ))}
        </nav>
        <JobsWidget />
        <div className="border-t border-line px-3 py-2 text-[11px] text-faint">Local processing · v0.1.0</div>
      </aside>
      <header className="flex items-center justify-between border-b border-line bg-surface px-3 py-2 md:hidden">
        <Logo /><JobsWidget compact />
      </header>
      <main className={cx("min-h-0 min-w-0 flex-1 overflow-y-auto", fullBleed ? "lg:overflow-hidden" : "px-4 py-4 md:px-6 md:py-5")}>
        <div className={cx(fullBleed ? "h-full" : "mx-auto max-w-6xl")}>{children}</div>
      </main>
      <nav className="flex shrink-0 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] md:hidden">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end}
            className={({ isActive }) => cx("flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px]", isActive ? "text-accent" : "text-muted")}>
            <n.icon size={18} />{n.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

const JOB_NAMES: Record<string, string> = { analysis: "Analyzing", export: "Exporting", youtube: "Downloading", model_download: "Model download", proxy: "Preparing preview", search: "Searching" };

/** Live status of background work, read from the job queue. */
function JobsWidget({ compact }: { compact?: boolean }) {
  const { data } = usePoll<Job[]>(() => api.get("/jobs?active=true"), 1500);
  const jobs = data ?? [];
  if (!jobs.length) return compact ? null : <div className="px-3 py-2 text-[11px] text-faint">No background work</div>;
  const j = jobs.find((x) => x.status === "running") ?? jobs[0];
  if (compact) return <div className="flex items-center gap-2 text-xs text-muted"><Spinner size={13} />{JOB_NAMES[j.type] ?? j.type} <span className="tnum">{Math.round(j.progress * 100)}%</span></div>;
  return (
    <div className="space-y-1.5 border-t border-line px-3 py-2.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-text">{JOB_NAMES[j.type] ?? j.type}{j.status === "paused" ? " (paused)" : ""}</span>
        <span className="tnum text-muted">{Math.round(j.progress * 100)}%</span>
      </div>
      <Progress value={j.progress} />
      {jobs.length > 1 && <div className="text-[11px] text-faint">{jobs.length - 1} more queued</div>}
    </div>
  );
}

function Toasts() {
  const toasts = useApp((s) => s.toasts);
  const dismiss = useApp((s) => s.dismiss);
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-16 z-[60] flex flex-col items-center gap-2 px-3 md:bottom-4 md:items-end md:pr-4">
      {toasts.map((t) => (
        <div key={t.id} role="status" className={cx("pointer-events-auto flex max-w-md items-start gap-2 rounded-md border bg-raised px-3 py-2 text-xs shadow-lg",
          t.kind === "error" ? "border-danger/50" : t.kind === "ok" ? "border-ok/40" : "border-line-strong")}>
          <span className="leading-relaxed">{t.text}</span>
          <button aria-label="Dismiss" onClick={() => dismiss(t.id)} className="text-faint hover:text-text"><X size={13} /></button>
        </div>
      ))}
    </div>
  );
}

/** Shown on a phone or another device: enter the PIN displayed on the PC. */
function Pair({ onPaired }: { onPaired: () => void }) {
  const [pin, setPin] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null);
    try { await api.post("/pair", { pin }); onPaired(); } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }
  return (
    <Centered>
      <form onSubmit={submit} className="w-full max-w-xs space-y-4 rounded-lg border border-line bg-surface p-5">
        <Logo />
        <div>
          <h1 className="text-sm font-semibold">Connect this device</h1>
          <p className="mt-1 text-xs text-muted">Enter the 6-digit PIN shown on your PC in ClipForge → Settings → Privacy &amp; devices.</p>
        </div>
        <Input inputMode="numeric" autoFocus maxLength={6} placeholder="000000" value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
          className="h-11 text-center font-mono text-lg tracking-[0.4em]" />
        {err && <Notice tone="danger">{err}</Notice>}
        <Button variant="primary" type="submit" loading={busy} disabled={pin.length !== 6} className="w-full">Connect</Button>
      </form>
    </Centered>
  );
}
