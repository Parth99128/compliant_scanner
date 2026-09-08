"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";

import { useAuth } from "@/components/auth-context";
import { AlertDestructive } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon, inputCls, labelCls } from "@/components/ui/ministry";
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

const ASSURANCES = [
  { title: "On-device inspection", body: "OCR + calibration never leaves the machine" },
  { title: "Gazette-verified rules", body: "Rule 7 tables checked against official text" },
  { title: "Honest verdicts", body: "Unmeasured rules are never shown passed" },
  { title: "Officer-signed reports", body: "PDFs unlock only after human review" },
];

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
    <div className="animate-rise w-full max-w-4xl overflow-hidden rounded-2xl border border-navy-900/10 bg-white shadow-[0_24px_60px_-24px_rgba(7,28,51,0.45)]">
      <div className="grid grid-cols-1 md:grid-cols-[1.05fr_1fr]">
        {/* Ministry panel */}
        <div className="relative overflow-hidden bg-navy-950 p-7 text-slate-300 sm:p-9">
          <div className="tricolor-bar absolute inset-x-0 top-0 h-1.5" aria-hidden="true" />
          <div aria-hidden="true" className="pointer-events-none absolute -right-20 -top-24 h-64 w-64 rounded-full bg-saffron-500/10" />
          <div aria-hidden="true" className="pointer-events-none absolute -bottom-24 -left-16 h-56 w-56 rounded-full bg-white/[0.04]" />
          <Link href="/" className="relative flex items-center gap-3" aria-label="Back to home">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/drishti-logo.jpg"
              alt="DrishtiLM logo"
              className="h-14 w-14 rounded-2xl border border-gold/50 object-cover object-[50%_30%] shadow-[0_0_24px_rgba(201,162,39,0.35)]"
            />
            <span>
              <span className="block font-display text-[22px] font-black leading-none text-white">
                Drishti<span className="bg-gradient-to-r from-sky-400 to-green-400 bg-clip-text text-transparent">LM</span>
              </span>
              <span className="mt-1 block text-[10px] font-bold uppercase tracking-[0.2em] text-gold">
                Legal Metrology · Field Console
              </span>
            </span>
          </Link>
          <h1 className="relative mt-6 font-display text-[26px] font-black leading-tight text-white">
            Label compliance, verified at the shelf.
          </h1>
          <p className="relative mt-2 text-[13px] leading-relaxed text-slate-400">
            सही माप, हर पैकेट — CPU-only inspection for the Packaged Commodities Rules, 2011.
          </p>
          <ul className="relative mt-6 space-y-3 border-t border-white/10 pt-5">
            {ASSURANCES.map((a) => (
              <li key={a.title} className="flex gap-3">
                <span className="grid h-6 w-6 flex-none place-items-center rounded-full bg-igreen-700 text-[13px] font-black text-white">
                  ✓
                </span>
                <span>
                  <span className="block text-[13px] font-bold text-white">{a.title}</span>
                  <span className="block text-xs text-slate-400">{a.body}</span>
                </span>
              </li>
            ))}
          </ul>
          <p className="relative mt-6 flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2.5 text-xs text-slate-300">
            <Icon name="phone" size={15} />
            Consumer Helpline <span className="font-black text-white">1915</span>
            <span className="text-slate-500">· Dept. of Consumer Affairs</span>
          </p>
        </div>

        {/* Form panel */}
        <form onSubmit={onSubmit} noValidate className="p-7 sm:p-9">
          <div className="grid grid-cols-2 gap-1 rounded-xl border border-navy-100 bg-navy-50 p-1 text-sm font-bold" role="tablist" aria-label="Account mode">
            {(["login", "register"] as const).map((m) => (
              <button
                key={m}
                type="button"
                role="tab"
                aria-selected={mode === m}
                onClick={() => { setMode(m); setError(""); }}
                className={cn(
                  "rounded-lg py-2.5 transition-all",
                  mode === m ? "bg-navy-900 text-white shadow" : "text-slate-500 hover:text-navy-900"
                )}
              >
                {m === "login" ? "Sign in" : "Register"}
              </button>
            ))}
          </div>

          <h2 className="mt-6 font-display text-xl font-black tracking-tight text-navy-950">
            {mode === "login" ? "Officer sign in" : "Create officer account"}
          </h2>
          <p className="mb-5 mt-1 text-[13px] text-slate-500">
            {mode === "login"
              ? "Access the field console with your department credentials."
              : "Join the inspection force. Choose a role for this account."}
          </p>

          <label className={labelCls} htmlFor="username">Username</label>
          <div className="relative">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
              <Icon name="idcard" size={17} />
            </span>
            <input
              id="username" autoComplete="username" placeholder="e.g. inspector.mumbai"
              value={username} onChange={(e) => setUsername(e.target.value)} onBlur={() => setTouched(true)}
              className={cn(inputCls, "pl-9", fieldError("username") && "border-red-600")}
            />
          </div>
          {fieldError("username") && <p className="mb-2 mt-1 text-xs font-semibold text-red-700">{fieldError("username")}</p>}

          <label className={cn(labelCls, "mt-4")} htmlFor="password">Password</label>
          <div className="relative">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
              <Icon name="shield" size={17} />
            </span>
            <input
              id="password" type={showPw ? "text" : "password"}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              placeholder="Minimum 6 characters"
              value={password} onChange={(e) => setPassword(e.target.value)} onBlur={() => setTouched(true)}
              className={cn(inputCls, "pl-9 pr-16", fieldError("password") && "border-red-600")}
            />
            <button type="button" onClick={() => setShowPw((v) => !v)}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded px-2 py-1 text-xs font-bold text-navy-800 hover:bg-navy-50">
              {showPw ? "Hide" : "Show"}
            </button>
          </div>
          {fieldError("password") && <p className="mb-2 mt-1 text-xs font-semibold text-red-700">{fieldError("password")}</p>}

          {mode === "register" && (
            <div className="mt-4">
              <span className={labelCls} id="role-label">Role</span>
              <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-labelledby="role-label">
                {(
                  [
                    { v: "officer", t: "Officer", d: "Scan & confirm findings", icon: "shield" },
                    { v: "admin", t: "Admin", d: "Plus override findings", icon: "scale" },
                  ] as const
                ).map((o) => (
                  <button
                    key={o.v}
                    type="button"
                    role="radio"
                    aria-checked={role === o.v}
                    onClick={() => setRole(o.v)}
                    className={cn(
                      "flex items-start gap-2.5 rounded-xl border-2 p-3 text-left transition-all",
                      role === o.v
                        ? "border-navy-900 bg-navy-50 shadow-sm"
                        : "border-slate-200 bg-white hover:border-slate-300"
                    )}
                  >
                    <span className={cn("grid h-8 w-8 flex-none place-items-center rounded-lg", role === o.v ? "bg-navy-900 text-white" : "bg-slate-100 text-slate-500")}>
                      <Icon name={o.icon} size={17} />
                    </span>
                    <span>
                      <span className="block text-[13px] font-bold text-navy-950">{o.t}</span>
                      <span className="block text-[11px] text-slate-500">{o.d}</span>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {error && <AlertDestructive className="mt-4">{error}</AlertDestructive>}
          <Button type="submit" size="full" disabled={busy} className="mt-5 !h-12 !text-[15px] shadow-md">
            {busy ? <><span className="spinner" /> Please wait…</> : mode === "login" ? "Sign in to console" : "Create account"}
          </Button>
          <p className="mt-4 text-center text-xs text-slate-500">
            JWT-secured · rate-limited API · SIH26034 demo prototype
          </p>
        </form>
      </div>
    </div>
  );
}
