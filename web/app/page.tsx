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
import { NewScanButton, PageHeader } from "@/components/page-header";
import { VerdictBadge } from "@/components/ui/badge";
import { statsOverview } from "@/lib/api";

const SLICE: Record<string, string> = {
  Compliant: "#1c6b3a",
  "Non-compliant": "#a4262c",
  Incomplete: "#b97e00",
};

function Skeleton({ className }: { className?: string }): React.JSX.Element {
  return <div className={`animate-pulse rounded-md bg-slate-200 ${className ?? ""}`} />;
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
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
    );

  if (!session) return <LandingPage />;

  const d = stats.data;
  const dist = d
    ? (["COMPLIANT", "NON_COMPLIANT", "INCOMPLETE"] as const).map((v) => ({
        name: v === "COMPLIANT" ? "Compliant" : v === "NON_COMPLIANT" ? "Non-compliant" : "Incomplete",
        value: d.by_verdict[v] ?? 0,
      }))
    : [];
  const volume = (d?.by_day ?? []).map(([day, total]) => ({ day: day.slice(5), total }));
  const topRules = (d?.top_failed_rules ?? []).map(([rule, count]) => ({ rule, count }));
  const maxRule = Math.max(1, ...topRules.map((r) => r.count));

  return (
    <div className="animate-rise">
      <PageHeader
        title="Compliance overview"
        description="Inspection results across your scans. Select a card to open the matching records."
        actions={<NewScanButton />}
      />

      {stats.isError && (
        <p className="mt-3 rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900">
          Could not load statistics. Check that the backend is running.
        </p>
      )}

      <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          { k: "Inspections", v: d?.total ?? 0, href: "/scans", dot: "bg-navy-800", tv: "text-navy-950" },
          { k: "Compliant", v: d?.by_verdict["COMPLIANT"] ?? 0, href: "/scans?verdict=COMPLIANT", dot: "bg-igreen-700", tv: "text-green-800" },
          { k: "Violations", v: d?.by_verdict["NON_COMPLIANT"] ?? 0, href: "/scans?verdict=NON_COMPLIANT", dot: "bg-red-700", tv: "text-red-800" },
          { k: "Needs measurement", v: d?.by_verdict["INCOMPLETE"] ?? 0, href: "/scans?verdict=INCOMPLETE", dot: "bg-saffron-500", tv: "text-amber-800" },
        ].map((s) => (
          <Link
            key={s.k}
            href={s.href}
            className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md focus-visible:outline-none"
          >
            <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest text-slate-500">
              <span className={`inline-block h-2 w-2 rounded-sm ${s.dot}`} aria-hidden="true" />
              {s.k}
            </p>
            <p className={`mt-1 font-display text-3xl font-black tabular-nums ${s.tv}`}>
              {stats.isPending ? "–" : <CountUp to={s.v} />}
            </p>
            <p className="mt-1 text-[11px] font-semibold text-slate-400">View records →</p>
          </Link>
        ))}
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-5">
        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
          <h2 className="text-sm font-bold">Compliance mix</h2>
          <p className="text-xs text-slate-500">Share of verdicts across your scans</p>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={dist} dataKey="value" nameKey="name" outerRadius={78} label>
                  {dist.map((s) => (
                    <Cell key={s.name} fill={SLICE[s.name] ?? "#64748b"} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm lg:col-span-3">
          <h2 className="text-sm font-bold">Inspection volume</h2>
          <p className="text-xs text-slate-500">Scans per day, last 14 days with data</p>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={volume}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="day" fontSize={11} />
                <YAxis allowDecimals={false} fontSize={11} />
                <Tooltip />
                <Bar dataKey="total" fill="#16355f" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-5">
        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm lg:col-span-3">
          <h2 className="text-sm font-bold">Top violated rules</h2>
          <p className="mb-3 text-xs text-slate-500">Where enforcement attention pays off</p>
          {topRules.length === 0 ? (
            <p className="text-[13px] text-slate-500">{stats.isPending ? "Loading…" : "No violations recorded."}</p>
          ) : (
            <div className="flex flex-col gap-2.5">
              {topRules.map((r) => (
                <div key={r.rule}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <code className="font-bold">{r.rule}</code>
                    <span className="font-bold tabular-nums text-red-800">{r.count}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                    <div className="h-full rounded-full bg-red-700" style={{ width: `${(r.count / maxRule) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-bold">Recent inspections</h2>
            <Link href="/scans" className="text-xs font-bold text-slate-700 hover:underline">
              View all
            </Link>
          </div>
          <div className="flex flex-col gap-1">
            {(d?.recent ?? []).map((s) => (
              <Link
                key={s.id}
                href={`/scans/${s.id}`}
                className="flex items-center gap-2.5 rounded-md px-2 py-2 hover:bg-slate-50"
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
              <p className="text-[13px] text-slate-500">
                No scans yet. <Link href="/scan" className="font-bold text-slate-700 hover:underline">Run your first scan</Link>.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
