"use client";

import { useRouter } from "next/navigation";
import * as React from "react";

import { useAuth } from "@/components/auth-context";
import { AlertDestructive } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ApiError, CredentialsSchema } from "@/lib/api";
import { cn } from "@/lib/utils";

function messageOf(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 409) return "This username is already registered. Try signing in instead.";
    if (e.status === 401) return "Invalid username or password.";
    if (e.status === 422) return "Username needs 3+ characters and password 6+ characters.";
    if (e.status === 0) return e.message;
    return e.message.slice(0, 220);
  }
  return "Something went wrong. Try again.";
}

export default function LoginPage(): React.JSX.Element {
  const router = useRouter();
  const { session, ready, signIn, signUp } = useAuth();
  const [mode, setMode] = React.useState<"login" | "register">("login");
  const [username, setUsername] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [role, setRole] = React.useState<"officer" | "admin">("officer");
  const [showPw, setShowPw] = React.useState(false);
  const [touched, setTouched] = React.useState(false);
  const [error, setError] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (ready && session) router.replace("/");
  }, [ready, session, router]);

  const parsed = CredentialsSchema.safeParse({ username, password, role });
  const fieldError = (name: "username" | "password"): string => {
    if (!touched) return "";
    const issue = !parsed.success
      ? parsed.error.issues.find((i) => i.path[0] === name)
      : undefined;
    return issue?.message ?? "";
  };

  async function onSubmit(ev: React.FormEvent): Promise<void> {
    ev.preventDefault();
    setTouched(true);
    setError("");
    if (!parsed.success) return;
    setBusy(true);
    try {
      if (mode === "login") await signIn(parsed.data);
      else await signUp(parsed.data);
      router.replace("/");
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="animate-rise mx-auto grid max-w-3xl grid-cols-1 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg md:grid-cols-2">
      <div className="relative bg-navy-950 p-8 text-slate-300">
        <div className="tricolor-bar absolute inset-x-0 top-0 h-1.5" aria-hidden="true" />
        <div className="flex items-center gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/drishti-logo.jpg"
            alt="DrishtiLM logo"
            className="h-14 w-14 rounded-xl object-cover object-[50%_30%] shadow-[0_0_20px_rgba(56,189,248,0.4)] ring-1 ring-white/20"
          />
          <div>
            <p className="font-display text-xl font-black leading-none text-white">
              Drishti<span className="bg-gradient-to-r from-sky-400 to-green-400 bg-clip-text text-transparent">LM</span>
            </p>
            <p className="mt-1 text-[11px] font-bold uppercase tracking-widest text-gold">
              Legal Metrology · Packaged Commodities
            </p>
          </div>
        </div>
        <h1 className="mt-2 font-display text-2xl font-black text-white">Label Compliance Scanner</h1>
        <p className="mt-1 text-[13px] font-semibold text-slate-400">सही माप, हर पैकेट · CPU-only inspection for the 2011 Rules.</p>
        <ul className="mt-6 space-y-2 border-t border-white/10 pt-4 text-[13px]">
          {[
            "OCR + calibration runs on-device",
            "Rule 7 tables verified vs gazette text",
            "Unmeasured rules never shown passed",
            "Reports unlock after officer review",
          ].map((t) => (
            <li key={t} className="flex gap-2">
              <span className="font-bold text-green-400">✓</span> {t}
            </li>
          ))}
        </ul>
      </div>
      <form onSubmit={onSubmit} noValidate className="p-8">
        <h2 className="font-display text-lg font-black text-navy-950">{mode === "login" ? "Officer sign in" : "Create officer account"}</h2>
        <p className="mb-4 text-[13px] text-slate-500">SIH26034 · JWT-secured, rate-limited API</p>
        <div className="mb-5 flex overflow-hidden rounded-md border border-slate-300 text-sm font-semibold">
          {(["login", "register"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => { setMode(m); setError(""); }}
              className={cn("flex-1 py-2", mode === m ? "bg-navy-900 text-white" : "bg-slate-50 text-slate-500")}
            >
              {m === "login" ? "Sign in" : "Register"}
            </button>
          ))}
        </div>
        <label className="mb-1 block text-[13px] font-semibold text-slate-700" htmlFor="username">Username</label>
        <input
          id="username" autoComplete="username" placeholder="e.g. inspector.mumbai"
          value={username} onChange={(e) => setUsername(e.target.value)} onBlur={() => setTouched(true)}
          className={cn("mb-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm", fieldError("username") && "border-red-600")}
        />
        {fieldError("username") && <p className="mb-2 text-xs text-red-700">{fieldError("username")}</p>}
        <label className="mb-1 mt-3 block text-[13px] font-semibold text-slate-700" htmlFor="password">Password</label>
        <div className="relative">
          <input
            id="password" type={showPw ? "text" : "password"}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            placeholder="Minimum 6 characters"
            value={password} onChange={(e) => setPassword(e.target.value)} onBlur={() => setTouched(true)}
            className={cn("mb-1 w-full rounded-md border border-slate-300 px-3 py-2 pr-16 text-sm", fieldError("password") && "border-red-600")}
          />
          <button type="button" onClick={() => setShowPw((v) => !v)} className="absolute right-2 top-1/2 -translate-y-1/2 px-2 text-xs font-bold text-slate-700">
            {showPw ? "Hide" : "Show"}
          </button>
        </div>
        {fieldError("password") && <p className="mb-2 text-xs text-red-700">{fieldError("password")}</p>}
        {mode === "register" && (
          <>
            <label className="mb-1 mt-3 block text-[13px] font-semibold text-slate-700" htmlFor="role">Role</label>
            <select id="role" value={role} onChange={(e) => setRole(e.target.value as "officer" | "admin")}
              className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm">
              <option value="officer">Officer — scan, confirm findings</option>
              <option value="admin">Admin — plus override findings</option>
            </select>
          </>
        )}
        {error && <AlertDestructive className="mt-4">{error}</AlertDestructive>}
        <Button type="submit" size="full" disabled={busy} className="mt-5">
          {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
        </Button>
      </form>
    </div>
  );
}
