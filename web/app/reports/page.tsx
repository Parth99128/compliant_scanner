"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";

import { useAuth, useMounted } from "@/components/auth-context";
import { NewScanButton } from "@/components/page-header";
import { AlertDestructive } from "@/components/ui/alert";
import { VerdictBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState, Hero, Icon, Panel, StatCard } from "@/components/ui/ministry";
import { useToast } from "@/components/ui/toaster";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError, fetchBlob, listScans } from "@/lib/api";

export default function ReportsPage(): React.JSX.Element {
  const router = useRouter();
  const { session, ready } = useAuth();
  const mounted = useMounted();
  const { notifyError } = useToast();
  const [busyId, setBusyId] = React.useState<string | null>(null);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    if (ready && !session) router.replace("/login");
  }, [ready, session, router]);

  const scans = useQuery({
    queryKey: ["scans"],
    queryFn: () => listScans(session?.token ?? ""),
    enabled: ready && !!session,
  });

  if (!mounted || !ready || !session) return <p className="text-sm text-slate-500">Loading…</p>;

  const finals = (scans.data ?? []).filter((s) => s.status === "final");
  const clean = finals.filter((s) => s.verdict === "COMPLIANT").length;
  const flagged = finals.length - clean;

  async function download(id: string): Promise<void> {
    if (!session || busyId) return;
    setError("");
    setBusyId(id);
    try {
      const blob = await fetchBlob(`/scans/${id}/report`, session.token);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `scan-${id}.pdf`;
      a.click();
      window.setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Report download failed.";
      setError(msg);
      notifyError(e, msg);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="animate-rise flex flex-col gap-4">
      <Hero
        kicker="Signed records"
        kickerHi="हस्ताक्षरित रिकॉर्ड"
        title="Reports"
        description="Only finalized scans appear here — reports unlock after officer review, each carrying findings, evidence and audit trail."
        actions={<NewScanButton />}
        meta={
          <span className="flex items-center gap-1.5">
            <Icon name="file" size={14} />
            {finals.length} finalized report{finals.length === 1 ? "" : "s"}
          </span>
        }
      />
      {error && <AlertDestructive>{error}</AlertDestructive>}
      {scans.isError && (
        <AlertDestructive>Could not load scans. Check that the backend is running.</AlertDestructive>
      )}

      <div className="grid grid-cols-3 gap-3">
        <StatCard icon="file" label="Finalized" tone="navy" value={scans.isPending ? "–" : finals.length} />
        <StatCard icon="check" label="Compliant" tone="green" value={scans.isPending ? "–" : clean} />
        <StatCard icon="alert" label="Flagged" tone="red" value={scans.isPending ? "–" : flagged} />
      </div>

      <Panel title="Exportable reports" description="Signed PDFs with Rule 7 tables, findings and audit trail.">
        {finals.length === 0 ? (
          <EmptyState icon="file" title={scans.isPending ? "Loading…" : "No finalized reports yet"}
            body={scans.isPending ? undefined : "Confirm a review on any scan to export it here."}
            action={scans.isPending ? undefined : (
              <Link href="/scans" className="rounded-lg bg-navy-900 px-4 py-2 text-sm font-bold text-white">
                Go to scan history
              </Link>
            )} />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Scan ID</TableHead>
                <TableHead>Label</TableHead>
                <TableHead>Verdict</TableHead>
                <TableHead>Engine</TableHead>
                <TableHead>Created</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {finals.map((s) => (
                <TableRow key={s.id}>
                  <TableCell>
                    <Link href={`/scans/${s.id}`} className="font-mono text-xs text-navy-800 hover:underline">
                      {s.id}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <span className="block max-w-64 truncate font-medium" title={s.preview}>
                      {s.preview || <span className="text-slate-400">—</span>}
                    </span>
                  </TableCell>
                  <TableCell>
                    <VerdictBadge verdict={s.verdict} />
                  </TableCell>
                  <TableCell>
                    <code className="text-xs">{s.ocr_engine}</code>
                  </TableCell>
                  <TableCell className="whitespace-nowrap tabular-nums">
                    {s.created_at.slice(0, 16).replace("T", " ")}
                  </TableCell>
                  <TableCell>
                    <Button variant="outline" size="sm" disabled={busyId !== null} onClick={() => download(s.id)}>
                      <Icon name="download" size={14} />
                      {busyId === s.id ? "Working…" : "PDF"}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Panel>
    </div>
  );
}
