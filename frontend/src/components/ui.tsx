/** Reusable design-system components. Sizes and colours come only from the tokens in styles.css. */
import { Loader2, X } from "lucide-react";
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";
import { useEffect } from "react";

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");
export { cx };

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
  icon?: ReactNode;
  loading?: boolean;
};
export function Button({ variant = "secondary", size = "md", icon, loading, children, className, disabled, ...rest }: BtnProps) {
  const variants = {
    primary: "bg-accent text-white hover:bg-accent-hover border-transparent",
    secondary: "bg-raised text-text hover:bg-hover border-line",
    ghost: "bg-transparent text-muted hover:text-text hover:bg-hover border-transparent",
    danger: "bg-transparent text-danger hover:bg-danger/10 border-danger/40",
  };
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={cx(
        "inline-flex items-center justify-center gap-1.5 rounded-md border font-medium transition-colors select-none",
        "disabled:opacity-45 disabled:pointer-events-none whitespace-nowrap",
        size === "sm" ? "h-7 px-2.5 text-xs" : "h-8 px-3 text-[13px]",
        variants[variant], className,
      )}
    >
      {loading ? <Loader2 size={14} style={{ animation: "spin 0.8s linear infinite" }} /> : icon}
      {children}
    </button>
  );
}

export function IconButton({ label, children, active, className, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string; active?: boolean }) {
  return (
    <button
      {...rest}
      aria-label={label}
      title={label}
      className={cx(
        "inline-flex h-8 w-8 items-center justify-center rounded-md transition-colors disabled:opacity-40",
        active ? "bg-accent-soft text-accent" : "text-muted hover:bg-hover hover:text-text", className,
      )}
    >
      {children}
    </button>
  );
}

export function Panel({ title, actions, children, className }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cx("rounded-lg border border-line bg-surface", className)}>
      {(title || actions) && (
        <header className="flex min-h-10 items-center justify-between gap-2 border-b border-line px-3 py-1.5">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</h2>
          <div className="flex items-center gap-1.5">{actions}</div>
        </header>
      )}
      {children}
    </section>
  );
}

export function Field({ label, hint, children, row }: { label: ReactNode; hint?: ReactNode; children: ReactNode; row?: boolean }) {
  return (
    <label className={cx("block", row && "flex items-center justify-between gap-3")}>
      <span className={cx("text-xs text-muted", !row && "mb-1 block")}>{label}</span>
      {children}
      {hint && <span className="mt-1 block text-[11px] leading-snug text-faint">{hint}</span>}
    </label>
  );
}

const inputCls = "h-8 w-full rounded-md border border-line bg-bg px-2 text-[13px] text-text placeholder:text-faint focus:border-accent focus:outline-none disabled:opacity-50";

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cx(inputCls, props.className)} />;
}

export function Select({ options, ...props }: SelectHTMLAttributes<HTMLSelectElement> & { options: { value: string | number; label: string }[] }) {
  return (
    <select {...props} className={cx(inputCls, "pr-6", props.className)}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

export function Slider({ value, min, max, step = 1, onChange, format, disabled }: { value: number; min: number; max: number; step?: number; onChange: (v: number) => void; format?: (v: number) => string; disabled?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <input type="range" className="min-w-0 flex-1" min={min} max={max} step={step} value={value} disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))} />
      <span className="tnum w-12 text-right text-xs text-muted">{format ? format(value) : value}</span>
    </div>
  );
}

export function Toggle({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <button type="button" role="switch" aria-checked={checked} aria-label={label} disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cx("relative h-5 w-9 shrink-0 rounded-full transition-colors disabled:opacity-40", checked ? "bg-accent" : "bg-line-strong")}>
      <span className={cx("absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all", checked ? "left-[18px]" : "left-0.5")} />
    </button>
  );
}

export function Segmented<T extends string>({ value, options, onChange, size = "md" }: { value: T; options: { value: T; label: ReactNode; title?: string }[]; onChange: (v: T) => void; size?: "sm" | "md" }) {
  return (
    <div className="inline-flex max-w-full flex-wrap rounded-md border border-line bg-bg p-0.5">
      {options.map((o) => (
        <button key={o.value} type="button" title={o.title} onClick={() => onChange(o.value)}
          className={cx("rounded-sm px-2.5 font-medium transition-colors", size === "sm" ? "h-6 text-[11px]" : "h-7 text-xs",
            value === o.value ? "bg-hover text-text" : "text-muted hover:text-text")}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "accent" | "ok" | "warn" | "danger" | "info" }) {
  const tones = {
    neutral: "bg-hover text-muted", accent: "bg-accent-soft text-accent", ok: "bg-ok/15 text-ok",
    warn: "bg-warn/15 text-warn", danger: "bg-danger/15 text-danger", info: "bg-info/15 text-info",
  };
  return <span className={cx("inline-flex h-5 items-center rounded-sm px-1.5 text-[11px] font-medium", tones[tone])}>{children}</span>;
}

export function Progress({ value, tone = "accent" }: { value: number; tone?: "accent" | "ok" | "danger" }) {
  const color = { accent: "bg-accent", ok: "bg-ok", danger: "bg-danger" }[tone];
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-line" role="progressbar" aria-valuenow={Math.round(value * 100)} aria-valuemin={0} aria-valuemax={100}>
      <div className={cx("h-full rounded-full transition-[width] duration-300", color)} style={{ width: `${Math.min(100, Math.max(0, value * 100))}%` }} />
    </div>
  );
}

export function Spinner({ size = 16 }: { size?: number }) {
  return <Loader2 size={size} className="text-muted" style={{ animation: "spin 0.8s linear infinite" }} />;
}

export function Empty({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      {icon && <div className="text-faint">{icon}</div>}
      <p className="text-sm font-medium text-text">{title}</p>
      {children && <div className="max-w-md text-xs text-muted">{children}</div>}
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "warn" | "danger" | "ok"; children: ReactNode }) {
  const tones = { info: "border-info/30 bg-info/10 text-text", warn: "border-warn/30 bg-warn/10 text-text", danger: "border-danger/40 bg-danger/10 text-text", ok: "border-ok/30 bg-ok/10 text-text" };
  return <div className={cx("rounded-md border px-3 py-2 text-xs leading-relaxed", tones[tone])}>{children}</div>;
}

export function Modal({ title, onClose, children, footer, wide }: { title: string; onClose: () => void; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-0 sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label={title}
        className={cx("flex max-h-[92dvh] w-full flex-col rounded-t-lg border border-line bg-surface sm:rounded-lg", wide ? "sm:max-w-3xl" : "sm:max-w-md")}>
        <header className="flex items-center justify-between border-b border-line px-4 py-2.5">
          <h2 className="text-sm font-semibold">{title}</h2>
          <IconButton label="Close" onClick={onClose}><X size={16} /></IconButton>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">{children}</div>
        {footer && <footer className="flex justify-end gap-2 border-t border-line px-4 py-2.5">{footer}</footer>}
      </div>
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="truncate text-lg font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
      </div>
      <div className="flex flex-wrap items-center gap-2">{actions}</div>
    </div>
  );
}

export function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] uppercase tracking-wide text-faint">{label}</div>
      <div className="tnum truncate text-[13px] text-text">{value}</div>
    </div>
  );
}
