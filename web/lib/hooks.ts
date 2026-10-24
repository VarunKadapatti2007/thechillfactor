"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { DataOrigin, Result } from "./api";

export interface AsyncState<T> {
  data: T | null;
  origin: DataOrigin | null;
  loading: boolean;
  error: string | null;
  retry: () => void;
}

// Runs `fn` whenever `key` changes; ignores stale responses. key=null means idle.
export function useAsync<T>(fn: () => Promise<Result<T>>, key: string | null): AsyncState<T> {
  const [state, setState] = useState<Omit<AsyncState<T>, "retry">>({ data: null, origin: null, loading: false, error: null });
  const [nonce, setNonce] = useState(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    if (key === null) {
      setState({ data: null, origin: null, loading: false, error: null });
      return;
    }
    let live = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    fnRef.current()
      .then((r) => live && setState({ data: r.data, origin: r.origin, loading: false, error: null }))
      .catch((e: unknown) => live && setState({ data: null, origin: null, loading: false, error: e instanceof Error ? e.message : String(e) }));
    return () => {
      live = false;
    };
  }, [key, nonce]);

  const retry = useCallback(() => setNonce((n) => n + 1), []);
  return { ...state, retry };
}

export function useMediaQuery(q: string): boolean {
  const [m, setM] = useState(() => typeof window !== "undefined" && window.matchMedia(q).matches);
  useEffect(() => {
    const mq = window.matchMedia(q);
    setM(mq.matches);
    const h = (e: MediaQueryListEvent) => setM(e.matches);
    mq.addEventListener("change", h);
    return () => mq.removeEventListener("change", h);
  }, [q]);
  return m;
}

export function useLocalStorage(key: string, initial: string): [string, (v: string) => void] {
  const [v, setV] = useState(initial);
  useEffect(() => {
    try {
      const s = window.localStorage.getItem(key);
      if (s !== null) setV(s);
    } catch {}
  }, [key]);
  const set = useCallback(
    (nv: string) => {
      setV(nv);
      try {
        window.localStorage.setItem(key, nv);
      } catch {}
    },
    [key],
  );
  return [v, set];
}
