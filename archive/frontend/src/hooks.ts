import { DependencyList, useCallback, useEffect, useMemo, useState } from 'react';

export function useAsyncData<T>(loader: () => Promise<T>, deps: DependencyList = [], enabled = true) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(Boolean(enabled));
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const memoizedLoader = useCallback(loader, deps);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await memoizedLoader();
      setData(next);
      setLoaded(true);
      return next;
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [memoizedLoader]);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    void run();
  }, [enabled, run]);

  return { data, loading, error, reload: run, setData, loaded };
}

export function useLocalStorage<T>(key: string, initialValue: T) {
  const [value, setValue] = useState<T>(() => {
    if (typeof window === 'undefined') return initialValue;
    try {
      const raw = window.localStorage.getItem(key);
      return raw ? (JSON.parse(raw) as T) : initialValue;
    } catch {
      return initialValue;
    }
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(key, JSON.stringify(value));
  }, [key, value]);

  return [value, setValue] as const;
}

export function useIncrementalCount(total: number, initialCount = 5, step = 5, resetKey?: string) {
  const [visibleCount, setVisibleCount] = useState(Math.min(total, initialCount));

  useEffect(() => {
    setVisibleCount(Math.min(total, initialCount));
  }, [total, initialCount, resetKey]);

  useEffect(() => {
    setVisibleCount((current) => Math.min(total, Math.max(current, initialCount)));
  }, [total, initialCount]);

  const hasMore = visibleCount < total;
  const loadMore = useCallback(() => {
    setVisibleCount((current) => Math.min(total, current + step));
  }, [step, total]);

  return useMemo(
    () => ({ visibleCount, hasMore, loadMore }),
    [hasMore, loadMore, visibleCount],
  );
}
