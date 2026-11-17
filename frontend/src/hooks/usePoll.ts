import { useCallback, useEffect, useRef, useState } from "react";

/** Fetch on mount and then on an interval (when `interval` is non-null). Returns data + manual reload. */
export function usePoll<T>(fn: () => Promise<T>, interval: number | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const reload = useCallback(async () => {
    try {
      const d = await fnRef.current();
      setData(d);
      setError(null);
      return d;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return null;
    }
  }, []);
  useEffect(() => {
    let alive = true;
    reload();
    if (interval == null) return;
    const id = setInterval(() => alive && reload(), interval);
    return () => { alive = false; clearInterval(id); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [interval, reload, ...deps]);
  return { data, error, reload, setData };
}
