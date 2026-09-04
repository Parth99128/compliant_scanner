"use client";

import * as React from "react";

import { clearSession, loadSession, login as apiLogin, register as apiRegister, saveSession, type Credentials } from "@/lib/api";

interface Session {
  token: string;
  username: string;
}

interface AuthCtx {
  session: Session | null;
  ready: boolean;
  signIn: (c: Credentials) => Promise<void>;
  signUp: (c: Credentials) => Promise<void>;
  signOut: () => void;
}

const Ctx = React.createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }): React.JSX.Element {
  // Lazy initializer reads SecureStore-equivalent synchronously: no effect,
  // no cascading render. Server prerender gets null, client hydration gets truth.
  const [session, setSession] = React.useState<Session | null>(() => loadSession());
  const ready = true;

  // A 401 anywhere (usually an expired JWT) clears storage in lib/api and
  // broadcasts here; the !session guards then route back to sign-in.
  React.useEffect(() => {
    const onUnauthorized = (): void => setSession(null);
    window.addEventListener("lmpc:unauthorized", onUnauthorized);
    return () => window.removeEventListener("lmpc:unauthorized", onUnauthorized);
  }, []);

  const signIn = React.useCallback(async (c: Credentials) => {
    const t = await apiLogin(c);
    saveSession(t.access_token, c.username);
    setSession({ token: t.access_token, username: c.username });
  }, []);

  const signUp = React.useCallback(async (c: Credentials) => {
    const t = await apiRegister(c);
    saveSession(t.access_token, c.username);
    setSession({ token: t.access_token, username: c.username });
  }, []);

  const signOut = React.useCallback(() => {
    clearSession();
    setSession(null);
  }, []);

  const value = React.useMemo(
    () => ({ session, ready, signIn, signUp, signOut }),
    [session, ready, signIn, signUp, signOut]
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const ctx = React.useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

/**
 * True only after client mount. Session comes from localStorage, which does
 * not exist during SSR — rendering session-dependent UI before mount causes
 * a hydration mismatch (server: signed-out, client: signed-in). Gate such
 * subtrees on this flag so both renders agree.
 */
export function useMounted(): boolean {
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- mount gate is the documented hydration fix
    setMounted(true);
  }, []);
  return mounted;
}
