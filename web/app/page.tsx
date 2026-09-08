"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import * as React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useAuth, useMounted } from "@/components/auth-context";
import { LandingPage } from "@/components/landing";
import { CountUp } from "@/components/motion";
import { NewScanButton } from "@/components/page-header";
import { VerdictBadge } from "@/components/ui/badge";
import { EmptyState, Hero, Icon, Panel, StatCard } from "@/components/ui/ministry";
import { statsOverview } from "@/lib/api";

const SLICE: Record<string, string> = {
  Compliant: "#1c6b3a",
  "Non-compliant": "#a4262c",
  Incomplete: "#b97e00",
};

function Skeleton({ className }: { className?: string }): React.JSX.Element {
  return <div className={`animate-pulse rounded-xl bg-slate-200 ${className ?? ""}`} />;
}

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

export default function DashboardPage(): React.JSX.Element {
  const { session, ready } = useAuth();
  const mounted = useMounted();

  const stats = useQuery({
    queryKey: ["stats"],
    queryFn: () => statsOverview(session?.token ?? ""),
    enabled: ready && !!session,
  });

  if (!mounted || !ready)
    return (
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-32" />
        ))}
      </div>
    );

  if (!session) return <LandingPage />;

  const today = new Date().toLocaleDateString("en-IN", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
  const d = stats.data;
  const compliant = d?.by_verdict["COMPLIANT"] ?? 0;
  const violations = d?.by_verdict["NON_COMPLIANT"] ?? 0;
  const incomplete = d?.by_verdict["INCOMPLETE"] ?? 0;
  const dist = (["COMPLIANT", "NON_COMPLIANT", "INCOMPLETE"] as const).map((v) => ({
    name: v === "COMPLIANT" ? "Compliant" : v === "NON_COMPLIANT" ? "Non-compliant" : "Incomplete",
    value: d?.by_verdict[v] ?? 0,
  }));
  const volume = (d?.by_day ?? []).map(([day, total]) => ({ day: day.slice(5), total }));
  const topRules = (d?.top_failed_rules ?? []).map(([rule, count]) => ({ rule, count }));
  const maxRule = Math.max(1, ...topRules.map((r) => r.count));

  return (
    <div className="animate-rise flex flex-col gap-4">
      <Hero
        kicker="Field Console"
        kickerHi="क्षेत्रीय कंसोल"
        title={`${greeting()}, ${session.username}`}
        description={`${today} · Inspection results across your scans. Select a card to open the matching records.`}
        actions={<NewScanButton />}
        meta={
          <>
            <span className="flex items-center gap-1.5">
              <Icon name="db" size={14} /> {d?.total ?? 0} inspections on record
            </span>
            <span className="flex items-center gap-1.5">
              <Icon name="shield" size={14} /> Rule 7 tables Gazette-verified
            </span>
          </>
        }
      />

      {stats.isError && (
        <p className="rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900">
          Could not load statistics. Check that the backend is running.
        </p>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard icon="file" label="Inspections" tone="navy" href="/scans"
          value={stats.isPending ? "–" : <CountUp to={d?.total ?? 0} />} sub="View records →" />
        <StatCard icon="check" label="Compliant" tone="green" href="/scans?verdict=COMPLIANT"
          value={stats.isPending ? "–" : <CountUp to={compliant} />} sub="View records →" />
        <StatCard icon="alert" label="Violations" tone="red" href="/scans?verdict=NON_COMPLIANT"
          value={stats.isPending ? "–" : <CountUp to={violations} />} sub="Needs enforcement →" />
        <StatCard icon="clock" label="Needs measurement" tone="amber" href="/scans?verdict=INCOMPLETE"
          value={stats.isPending ? "–" : <CountUp to={incomplete} />} sub="Retake & verify →" />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <Panel title="Compliance mix" description="Share of verdicts across your scans" className="lg:col-span-2">
          <div className="h-60">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={dist} dataKey="value" nameKey="name" outerRadius={82} label>
                  {dist.map((s) => (
                    <Cell key={s.name} fill={SLICE[s.name] ?? "#64748b"} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel title="Inspection volume" description="Scans per day, last 14 days with data" className="lg:col-span-3">
          <div className="h-60">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={volume}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="day" fontSize={11} />
                <YAxis allowDecimals={false} fontSize={11} />
                <Tooltip />
                <Bar dataKey="total" fill="#0b2a4a" radius={[5, 5, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <Panel title="Top violated rules" description="Where enforcement attention pays off" className="lg:col-span-3">
          {topRules.length === 0 ? (
            <EmptyState icon="shield" title={stats.isPending ? "Loading…" : "No violations recorded"}
              body={stats.isPending ? undefined : "Every assessed scan is compliant so far."} />
          ) : (
            <ol className="flex flex-col gap-3">
              {topRules.map((r, i) => (
                <li key={r.rule} className="flex items-center gap-3">
                  <span className="grid h-7 w-7 flex-none place-items-center rounded-full bg-red-700 text-xs font-black text-white">
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex items-center justify-between gap-2 text-xs">
                      <code className="truncate font-bold">{r.rule}</code>
                      <span className="font-black tabular-nums text-red-800">{r.count}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                      <div className="h-full rounded-full bg-gradient-to-r from-red-700 to-saffron-500" style={{ width: `${(r.count / maxRule) * 100}%` }} />
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </Panel>
        <Panel
          title="Recent inspections"
          className="lg:col-span-2"
          actions={<Link href="/scans" className="text-xs font-bold text-navy-800 hover:underline">View all →</Link>}
        >
          <div className="flex flex-col gap-1">
            {(d?.recent ?? []).map((s) => (
              <Link
                key={s.id}
                href={`/scans/${s.id}`}
                className="flex items-center gap-2.5 rounded-lg px-2 py-2 transition-colors hover:bg-navy-50"
              >
                <VerdictBadge verdict={s.verdict} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-bold">
                    {s.product_name || s.preview || <span className="text-slate-400">Untitled scan</span>}
                  </span>
                  <span className="block text-[11px] text-slate-500">
                    {s.created_at.slice(0, 16).replace("T", " ")} · {s.status === "final" ? "Final" : "Pending"}
                  </span>
                </span>
              </Link>
            ))}
            {!stats.isPending && (d?.recent ?? []).length === 0 && (
              <EmptyState icon="camera" title="No scans yet"
                body="Run your first inspection to populate this console."
                action={<Link href="/scan" className="rounded-lg bg-navy-900 px-4 py-2 text-sm font-bold text-white">Run your first scan</Link>} />
            )}
          </div>
        </Panel>
      </div>
    </div>
  );
}
