/** Login session kept in sessionStorage: it survives a page reload but ends when the tab is closed. */
export type Role = "mandataire" | "investigateur";

export interface User {
  id: number;
  email: string;
  display_name: string;
  role: Role;
  expert_id: number | null;
}

export interface Session {
  access_token: string;
  refresh_token: string;
  user: User;
}

const KEY = "locard.session";
let current: Session | null = read();
const listeners = new Set<() => void>();

function read(): Session | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function getSession(): Session | null {
  return current;
}

export function setSession(next: Session | null): void {
  current = next;
  try {
    if (next) sessionStorage.setItem(KEY, JSON.stringify(next));
    else sessionStorage.removeItem(KEY);
  } catch {
    /* storage unavailable (private mode): the session then lasts until reload */
  }
  listeners.forEach((fn) => fn());
}

export function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
