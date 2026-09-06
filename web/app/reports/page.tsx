"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";

import { useAuth, useMounted } from "@/components/auth-context";
import { NewScanButton, PageHeader } from "@/components/page-header";
import { AlertDestructive } from "@/components/ui/alert";
import { VerdictBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
    <div>
      <PageHeader
        title="Reports"
        description="Only finalized scans appear here — reports unlock after officer review."
        actions={<NewScanButton />}
      />
      {error && <AlertDestructive className="mb-3">{error}</AlertDestructive>}
      {scans.isError && (
        <AlertDestructive className="mb-3">Could not load scans. Check that the backend is running.</AlertDestructive>
      )}
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
          {finals.length === 0 ? (
            <TableRow>
              <TableCell colSpan={6} className="text-center text-slate-500">
                {scans.isPending
                  ? "Loading…"
                  : "No finalized reports yet. Confirm a review on any scan to export it here."}
              </TableCell>
            </TableRow>
          ) : (
            finals.map((s) => (
              <TableRow key={s.id}>
                <TableCell>
                  <Link href={`/scans/${s.id}`} className="font-mono text-xs hover:underline">
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
                    {busyId === s.id ? "Working…" : "PDF"}
                  </Button>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
