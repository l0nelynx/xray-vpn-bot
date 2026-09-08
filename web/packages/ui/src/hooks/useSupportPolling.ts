import { useCallback, useEffect, useRef, useState } from "react";

/** Quiet background refresh, latest-request wins, refresh on foreground. */
export function useSupportPolling<T>(
  key: string,
  fetcher: () => Promise<T>,
  interval = 8000,
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fetchRef = useRef(fetcher);
  fetchRef.current = fetcher;
  const generation = useRef(0);
  const pending = useRef(false);
  const reload = useCallback(async () => {
    const request = ++generation.current;
    pending.current = true;
    try {
      const next = await fetchRef.current();
      if (request === generation.current) {
        setData(next);
        setError(null);
      }
      return next;
    } catch (e) {
      if (request === generation.current)
        setError(e instanceof Error ? e.message : String(e));
      return null;
    } finally {
      if (request === generation.current) pending.current = false;
    }
  }, []);
  useEffect(() => {
    setData(null);
    setError(null);
    void reload();
    const refresh = () => {
      if (!document.hidden && !pending.current) void reload();
    };
    const timer = window.setInterval(refresh, interval);
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      generation.current++;
      pending.current = false;
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [key, interval, reload]);
  return { data, error, reload, setData };
}
