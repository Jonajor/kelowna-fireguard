import { useState, useEffect, useCallback, useRef } from "react";

export function usePolledData(fetchFn, intervalMs = 30000, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const mountedRef = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const result = await fetchFn();
      if (mountedRef.current && result) {
        setData(result);
        setError(null);
        setLastUpdated(new Date());
      }
    } catch (err) {
      if (mountedRef.current) setError(err.message);
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, [fetchFn, ...deps]);

  useEffect(() => {
    mountedRef.current = true;
    refresh();
    const timer = setInterval(refresh, intervalMs);
    return () => { mountedRef.current = false; clearInterval(timer); };
  }, [refresh, intervalMs]);

  return { data, loading, error, lastUpdated, refresh };
}
