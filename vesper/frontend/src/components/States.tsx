export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex min-h-[40vh] items-center justify-center" role="status">
      <span className="eyebrow animate-pulse text-smoke">{label}…</span>
    </div>
  );
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="flex min-h-[40vh] flex-col items-center justify-center gap-4 px-4 text-center" role="alert">
      <p className="display text-4xl">Something went quiet.</p>
      <p className="text-sm text-smoke">{message}</p>
      {retry && <button className="btn btn-ghost" onClick={retry}>Try again</button>}
    </div>
  );
}
