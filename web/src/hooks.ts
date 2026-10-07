import { DependencyList, useCallback, useEffect, useRef, useState } from "react";
import { frenchError } from "./format";

export interface Loaded<T> {
  data: T | null;
  error: string;
  loading: boolean;
  reload: () => Promise<void>;
  setData: (value: T | null) => void;
}

/** Load data when the dependencies change. Late answers from an earlier call are ignored. */
export function useLoad<T>(fn: () => Promise<T>, deps: DependencyList): Loaded<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const ticket = useRef(0);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(fn, deps);

  const reload = useCallback(async () => {
    const mine = ++ticket.current;
    setLoading(true);
    try {
      const result = await run();
      if (mine === ticket.current) {
        setData(result);
        setError("");
      }
    } catch (e) {
      if (mine === ticket.current) setError(frenchError(e));
    } finally {
      if (mine === ticket.current) setLoading(false);
    }
  }, [run]);

  useEffect(() => {
    void reload();
    return () => {
      ticket.current++;
    };
  }, [reload]);

  return { data, error, loading, reload, setData };
}

/** State kept in localStorage; reading or writing never throws (private mode, blocked storage). */
export function useStored<T>(key: string, initial: T): [T, (value: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? initial : (JSON.parse(raw) as T);
    } catch {
      return initial;
    }
  });
  const save = useCallback(
    (next: T) => {
      setValue(next);
      try {
        localStorage.setItem(key, JSON.stringify(next));
      } catch {
        /* ignore */
      }
    },
    [key],
  );
  return [value, save];
}
