import { createContext, ReactNode, useCallback, useContext, useMemo, useSyncExternalStore } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { api } from "./api";
import { getSession, Role, Session, setSession, subscribe, User } from "./session";

interface Auth {
  user: User | null;
  signIn: (session: Session) => void;
  login: (email: string, password: string) => Promise<User>;
  register: (email: string, name: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<Auth | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const session = useSyncExternalStore(subscribe, getSession);

  const login = useCallback(async (email: string, password: string) => {
    const s = await api.login(email, password);
    setSession(s);
    return s.user;
  }, []);

  const register = useCallback(async (email: string, name: string, password: string) => {
    const s = await api.register(email, name, password);
    setSession(s);
    return s.user;
  }, []);

  const logout = useCallback(async () => {
    const s = getSession();
    setSession(null); // leave first: the screen must not wait for the network
    if (s) await api.logout(s.refresh_token).catch(() => undefined);
  }, []);

  const value = useMemo<Auth>(
    () => ({ user: session?.user ?? null, signIn: setSession, login, register, logout }),
    [session, login, register, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): Auth {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

/** Sends visitors who are not signed in to the login page, and brings them back afterwards. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return <>{children}</>;
}

/** Screens that belong to one role. The server enforces this too; this only avoids dead ends. */
export function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const { user } = useAuth();
  if (user && user.role !== role) return <Navigate to="/" replace />;
  return <>{children}</>;
}
