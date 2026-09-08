"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import * as React from "react";

import { useAuth, useMounted } from "@/components/auth-context";
import { AlertDestructive } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Hero, Icon, Panel } from "@/components/ui/ministry";
import { healthCheck } from "@/lib/api";

export default function SettingsPage(): React.JSX.Element {
  const router = useRouter();
  const { session, ready, signOut } = useAuth();
  const mounted = useMounted();

  React.useEffect(() => {
    if (ready && !session) router.replace("/login");
  }, [ready, session, router]);

  const health = useQuery({
    queryKey: ["health"],
    queryFn: healthCheck,
    enabled: ready && !!session,
    retry: 1,
  });

  if (!mounted || !ready || !session) return <p className="text-sm text-slate-500">Loading…</p>;

  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "same-origin proxy";

  return (
    <div className="animate-rise flex flex-col gap-4">
      <Hero
        kicker="Console"
        kickerHi="सेटिंग्स"
        title="Settings"
        description="Session, connection and environment details for this installation."
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Officer session" description="Who is signed in on this device.">
          <div className="flex items-center gap-3">
            <span className="grid h-12 w-12 place-items-center rounded-full bg-navy-900 font-display text-lg font-black text-gold">
              {session.username.slice(0, 1).toUpperCase()}
            </span>
            <div>
              <p className="font-bold text-navy-950">{session.username}</p>
              <p className="flex items-center gap-1 text-xs text-slate-500">
                <Icon name="shield" size={13} /> JWT session · expires after inactivity
              </p>
            </div>
            <Button variant="outline" size="sm" className="ml-auto" onClick={signOut}>
              <Icon name="logout" size={14} /> Sign out
            </Button>
          </div>
          {/** Session tokens live in this browser only — clearing site data signs you out. */}
          <p className="mt-3 text-xs leading-relaxed text-slate-500">
            Tokens never leave this browser except as an Authorization header to the API.
            Clearing site data signs you out everywhere on this device.
          </p>
        </Panel>

        <Panel
          title="Backend connection"
          description="Live status of the checking service."
          actions={
            <Button variant="outline" size="sm" onClick={() => void health.refetch()} disabled={health.isFetching}>
              <Icon name="refresh" size={14} /> {health.isFetching ? "Checking…" : "Recheck"}
            </Button>
          }
        >
          <dl className="grid grid-cols-[130px_1fr] gap-x-2 gap-y-2 text-[13px]">
            <dt className="text-slate-500">Endpoint</dt>
            <dd><code className="break-all text-xs">{apiBase}</code></dd>
            <dt className="text-slate-500">Status</dt>
            <dd className="font-bold">
              {health.isPending ? (
                <span className="text-slate-500">Checking…</span>
              ) : health.isSuccess ? (
                <span className="flex items-center gap-1.5 text-green-800">
                  <Icon name="check" size={15} /> Online — API reachable
                </span>
              ) : (
                <span className="flex items-center gap-1.5 text-red-800">
                  <Icon name="alert" size={15} /> Unreachable — start the backend
                </span>
              )}
            </dd>
            <dt className="text-slate-500">Request ID</dt>
            <dd className="font-mono text-xs">{health.data?.request_id ?? "—"}</dd>
          </dl>
          {health.isError && (
            <AlertDestructive className="mt-3">Cannot reach the API server. Is the backend running?</AlertDestructive>
          )}
        </Panel>
      </div>

      <Panel title="About this installation" description="DrishtiLM · SIH26034 demo prototype.">
        <ul className="grid grid-cols-1 gap-2 text-[13px] text-slate-600 sm:grid-cols-2">
          {[
            ["Stack", "Next.js console · FastAPI engine · PostgreSQL records"],
            ["Pipeline", "OpenCV cleanup → Tesseract OCR → Regex + spaCy → Rule engine"],
            ["Rules", "Rule 6 declarations · Rule 7 print-size tables (Gazette-verified)"],
            ["Safety", "Unmeasured rules return NOT_ASSESSABLE — never a silent pass"],
          ].map(([k, v]) => (
            <li key={k} className="rounded-lg border border-slate-100 bg-slate-50/60 px-3 py-2">
              <span className="block text-[11px] font-bold uppercase tracking-widest text-slate-400">{k}</span>
              <span className="font-medium text-slate-700">{v}</span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs leading-relaxed text-slate-500">
          Not an official government portal. Unverified rule citations need legal review before
          enforcement use. National Consumer Helpline: <strong className="text-slate-700">1915</strong>.
        </p>
      </Panel>
    </div>
  );
}
