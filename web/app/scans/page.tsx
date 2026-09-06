"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";

import { useAuth, useMounted } from "@/components/auth-context";
import { NewScanButton, PageHeader } from "@/components/page-header";
import { ScanThumb } from "@/components/scan-thumb";
import { Badge, VerdictBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { listScans, type ScanSummary } from "@/lib/api";

type SortKey = "created_at" | "verdict" | "ocr_engine";

function compareRows(a: ScanSummary, b: ScanSummary, key: SortKey, dir: 1 | -1): number {
  const av = a[key] ?? "";
  const bv = b[key] ?? "";
  return av < bv ? -dir : av > bv ? dir : 0;
}

function HistoryInner(): React.JSX.Element {
  const router = useRouter();
  const params = useSearchParams();
  const { session, ready } = useAuth();
  const mounted = useMounted();
  const [sortKey, setSortKey] = React.useState<SortKey>("created_at");
  const [sortDir, setSortDir] = React.useState<1 | -1>(-1);
  const [page, setPage] = React.useState(0);
  const [search, setSearch] = React.useState(params.get("q") ?? "");
  const [verdict, setVerdict] = React.useState(() => {
    const v = params.get("verdict");
    return v === "COMPLIANT" || v === "NON_COMPLIANT" || v === "INCOMPLETE" ? v : "all";
  });
  const verdictParam = params.get("verdict");
  const queryParam = params.get("q") ?? "";

  // Dashboard cards link here with ?verdict=… — same-page navigation does not
  // remount, so adopt the URL params when they change.
  React.useEffect(() => {
    setVerdict(
      verdictParam === "COMPLIANT" || verdictParam === "NON_COMPLIANT" || verdictParam === "INCOMPLETE"
        ? verdictParam
        : "all"
    );
    setSearch(queryParam);
  }, [verdictParam, queryParam]);
  const token = session?.token ?? "";

  // Debounced query text: without this every keystroke fires a full-table
  // backend search, which feels exactly like a freeze on big repositories.
  const [debouncedQ, setDebouncedQ] = React.useState(search);
  React.useEffect(() => {
    const t = window.setTimeout(() => setDebouncedQ(search), 350);
    return () => window.clearTimeout(t);
  }, [search]);

  React.useEffect(() => {
    if (ready && !session) router.replace("/login");
  }, [ready, session, router]);

  const scans = useQuery({
    queryKey: ["scans", debouncedQ, verdict],
    queryFn: () => listScans(session?.token ?? "", { q: debouncedQ || undefined, verdict }),
    enabled: ready && !!session,
  });

  // Plain memo sort + paginate. (Deliberately no table-library row pipeline:
  // function-returning hooks miscompile under React Compiler into stale tables.)
  const PAGE_SIZE = 10;
  const sorted = React.useMemo(() => {
    const rows = [...(scans.data ?? [])];
    rows.sort((a, b) => compareRows(a, b, sortKey, sortDir));
    return rows;
  }, [scans.data, sortKey, sortDir]);
  const pageCount = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pageRows = sorted.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);

  function toggleSort(key: SortKey): void {
    if (key === sortKey) {
      setSortDir((d) => (d === 1 ? -1 : 1));
    } else {
      setSortKey(key);
      setSortDir(-1);
    }
    setPage(0);
  }

  function sortArrow(key: SortKey): string {
    if (key !== sortKey) return "";
    return sortDir === 1 ? "▲" : "▼";
  }

  if (!mounted || !ready || !session) return <p className="text-sm text-slate-500">Loading…</p>;

  return (
    <div className="animate-rise">
      <PageHeader
        title="Product repository"
        description="Every scan your account has run, searchable and filterable."
        actions={<NewScanButton />}
      />
      <div className="mb-3 mt-4 flex flex-wrap items-center gap-2">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search products, brands, label text…"
          aria-label="Search repository"
          className="min-w-56 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm sm:max-w-xs sm:flex-none"
        />
        {(["all", "COMPLIANT", "NON_COMPLIANT", "INCOMPLETE"] as const).map((v) => (
          <button
            key={v}
            onClick={() => {
              setVerdict(v);
              setPage(0);
            }}
            aria-pressed={verdict === v}
            className={`rounded-full border px-3 py-1.5 text-xs font-bold ${
              verdict === v ? "border-navy-900 bg-navy-900 text-white" : "border-slate-300 bg-white text-slate-600"
            }`}
          >
            {v === "all" ? "All" : v.charAt(0) + v.slice(1).toLowerCase().replace("_", "-")}
          </button>
        ))}
        <span className="ml-auto text-xs text-slate-500" aria-live="polite">
          {scans.isFetching ? "Filtering… " : ""}
          {sorted.length} of {scans.data?.length ?? 0} records
        </span>
      </div>
      {scans.isError && (
        <p className="mb-3 rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900">
          Could not load the repository. Check that the backend is running.
        </p>
      )}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Photo</TableHead>
            <TableHead>
              <button className="font-bold uppercase" onClick={() => toggleSort("created_at")}>
                Date {sortArrow("created_at")}
              </button>
            </TableHead>
            <TableHead>Product</TableHead>
            <TableHead>
              <button className="font-bold uppercase" onClick={() => toggleSort("verdict")}>
                Status {sortArrow("verdict")}
              </button>
            </TableHead>
            <TableHead>Review</TableHead>
            <TableHead>
              <button className="font-bold uppercase" onClick={() => toggleSort("ocr_engine")}>
                Engine {sortArrow("ocr_engine")}
              </button>
            </TableHead>
            <TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {pageRows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={7} className="py-10 text-center">
                <p className="font-bold text-slate-700">No records match</p>
                <p className="text-xs text-slate-500">Try a different search, or run a scan from the Scan tab.</p>
              </TableCell>
            </TableRow>
          ) : (
            pageRows.map((row) => (
              <TableRow key={row.id}>
                <TableCell>
                  <ScanThumb
                    id={row.id}
                    token={token}
                    hasImage={row.has_image}
                    alt={row.product_name || row.preview || "Label capture"}
                  />
                </TableCell>
                <TableCell>
                  <span className="whitespace-nowrap tabular-nums">
                    {row.created_at.slice(0, 16).replace("T", " ")}
                  </span>
                </TableCell>
                <TableCell>
                  <span className="block max-w-56">
                    <span className="block truncate text-[13px] font-bold" title={row.product_name || row.preview}>
                      {row.product_name || row.preview || <span className="font-normal text-slate-400">—</span>}
                    </span>
                    {(row.brand_name || row.category) && (
                      <span className="block truncate text-[11px] text-slate-500">
                        {[row.brand_name, row.category].filter(Boolean).join(" · ")}
                      </span>
                    )}
                  </span>
                </TableCell>
                <TableCell>
                  <VerdictBadge verdict={row.verdict} />
                </TableCell>
                <TableCell>
                  <Badge tone={row.status === "final" ? "blue" : "slate"}>
                    {row.status === "final" ? "Final" : "Pending"}
                  </Badge>
                </TableCell>
                <TableCell>
                  <code className="text-xs">{row.ocr_engine}</code>
                </TableCell>
                <TableCell>
                  <Link href={`/scans/${row.id}`} className="font-semibold text-slate-700 hover:underline">
                    Details
                  </Link>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
      <div className="mt-3 flex items-center gap-2 text-sm">
        <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={safePage === 0}>
          Previous
        </Button>
        <span className="text-xs text-slate-500">
          Page {safePage + 1} of {pageCount}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
          disabled={safePage >= pageCount - 1}
        >
          Next
        </Button>
      </div>
    </div>
  );
}

export default function ScansPage(): React.JSX.Element {
  return (
    <React.Suspense fallback={<p className="text-sm text-slate-500">Loading…</p>}>
      <HistoryInner />
    </React.Suspense>
  );
}
