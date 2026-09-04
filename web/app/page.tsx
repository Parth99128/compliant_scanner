"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
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
import { listScans } from "@/lib/api";

function Stat({ label, value, tone }: { label: string; value: number; tone: string }): React.JSX.Element {
  return (
    <div className={`rounded-md border border-slate-200 border-t-4 bg-white p-4 shadow-sm ${tone}`}>
      <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums">{value}</p>
    </div>
  );
}

export default function DashboardPage(): React.JSX.Element {
  const router = useRouter();
  const { session, ready } = useAuth();
  const mounted = useMounted();

  React.useEffect(() => {
    if (ready && !session) router.replace("/login");
  }, [ready, session, router]);

  const scans = useQuery({
    queryKey: ["scans"],
    queryFn: () => listScans(session?.token ?? ""),
    enabled: ready && !!session,
  });

  const rows = React.useMemo(() => scans.data ?? [], [scans.data]);
  const count = (v: string): number => rows.filter((r) => r.verdict === v).length;

  const dist = (
    [
      ["COMPLIANT", "Compliant", "#1c6b3a"],
      ["NON_COMPLIANT", "Non-compliant", "#a4262c"],
      ["INCOMPLETE", "Incomplete", "#b97e00"],
    ] as const
  ).map(([key, name, fill]) => ({ name, value: count(key), fill }));

  const byDay = React.useMemo(() => {
    const buckets = new Map<string, number>();
    for (const r of rows) {
      const day = r.created_at.slice(0, 10);
      buckets.set(day, (buckets.get(day) ?? 0) + 1);
    }
    return [...buckets.entries()]
      .sort(([a], [b]) => (a < b ? -1 : 1))
      .slice(-14)
      .map(([day, total]) => ({ day: day.slice(5), total }));
  }, [rows]);

  if (!mounted || !ready || !session) return <p className="text-sm text-slate-500">Loading…</p>;

  return (
    <div>
      <p className="text-xs text-slate-500">Inspect / Overview</p>
      <h1 className="text-xl font-bold">Compliance overview</h1>
      {scans.isError && (
        <p className="mt-3 rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900">
          Could not load scans. Check that the backend is running.
        </p>
      )}
      <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Total scans" value={rows.length} tone="border-t-slate-300" />
        <Stat label="Compliant" value={count("COMPLIANT")} tone="border-t-green-700" />
        <Stat label="Non-compliant" value={count("NON_COMPLIANT")} tone="border-t-red-700" />
        <Stat label="Incomplete" value={count("INCOMPLETE")} tone="border-t-amber-500" />
      </div>
      <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
        <div className="rounded-md border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-bold">Compliance mix</h2>
          <p className="text-xs text-slate-500">Share of verdicts across visible scans</p>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={dist} dataKey="value" nameKey="name" outerRadius={80} label>
                  {dist.map((d) => (
                    <Cell key={d.name} fill={d.fill} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="rounded-md border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-bold">Scan volume</h2>
          <p className="text-xs text-slate-500">Scans per day, last 14 days with data</p>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={byDay}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="day" fontSize={11} />
                <YAxis allowDecimals={false} fontSize={11} />
                <Tooltip />
                <Bar dataKey="total" fill="#16355f" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
      <div className="mt-4 rounded-md border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-bold">Field capture</h2>
        <p className="mt-1 text-[13px] text-slate-500">
          Open any row in scan history for the annotated viewer, officer review and PDF export.
          Start a new scan from “New scan” in the sidebar, or use the mobile
          capture app (Phase 4) in the field.
        </p>
      </div>
    </div>
  );
}
