"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";

import { useAuth, useMounted } from "@/components/auth-context";
import { NewScanButton } from "@/components/page-header";
import { ScanThumb } from "@/components/scan-thumb";
import { Badge, VerdictBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState, Hero, Icon, Panel, inputCls } from "@/components/ui/ministry";
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
  const statusParam = params.get("status");
  const validStatus = (v: string | null): "all" | "pending_review" | "final" =>
    v === "pending_review" || v === "final" ? v : "all";
  const [status, setStatus] = React.useState<"all" | "pending_review" | "final">(() =>
    validStatus(statusParam)
  );

  // Dashboard cards link here with ?verdict=… — same-page navigation does not
  // remount, so adopt the URL params when they change.
  React.useEffect(() => {
    setVerdict(
      verdictParam === "COMPLIANT" || verdictParam === "NON_COMPLIANT" || verdictParam === "INCOMPLETE"
        ? verdictParam
        : "all"
    );
    setSearch(queryParam);
    setStatus(validStatus(statusParam));
  }, [verdictParam, queryParam, statusParam]);
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
    queryKey: ["scans", debouncedQ, verdict, status],
    queryFn: () => listScans(session?.token ?? "", { q: debouncedQ || undefined, verdict, status }),
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
    <div className="animate-rise flex flex-col gap-4">
      <Hero
        kicker="Repository"
        kickerHi="भंडार"
        title="Product repository"
        description="Every scan your account has run, searchable and filterable."
        actions={<NewScanButton />}
        meta={
          <span className="flex items-center gap-1.5" aria-live="polite">
            <Icon name="db" size={14} />
            {scans.isFetching ? "Filtering… " : ""}
            {sorted.length} of {scans.data?.length ?? 0} records
          </span>
        }
      />
      <Panel>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-56 flex-1 sm:max-w-xs sm:flex-none">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
              <Icon name="search" size={16} />
            </span>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search products, brands, label text…"
              aria-label="Search repository"
              className={`${inputCls} pl-9`}
            />
          </div>
          <span className="hidden h-5 w-px bg-slate-200 sm:block" aria-hidden="true" />
          {(["all", "COMPLIANT", "NON_COMPLIANT", "INCOMPLETE"] as const).map((v) => (
            <button
              key={v}
              onClick={() => {
                setVerdict(v);
                setPage(0);
              }}
              aria-pressed={verdict === v}
              className={`rounded-full border px-3 py-1.5 text-xs font-bold transition-colors ${
                verdict === v ? "border-navy-900 bg-navy-900 text-white shadow-sm" : "border-slate-300 bg-white text-slate-600 hover:border-navy-300"
              }`}
            >
              {v === "all" ? "All" : v.charAt(0) + v.slice(1).toLowerCase().replace("_", "-")}
            </button>
          ))}
          <span className="hidden h-5 w-px bg-slate-200 sm:block" aria-hidden="true" />
          {(["all", "pending_review", "final"] as const).map((s) => (
            <button
              key={s}
              onClick={() => {
                setStatus(s);
                setPage(0);
              }}
              aria-pressed={status === s}
              className={`rounded-full border px-3 py-1.5 text-xs font-bold transition-colors ${
                status === s ? "border-saffron-600 bg-saffron-500 text-navy-950 shadow-sm" : "border-slate-300 bg-white text-slate-600 hover:border-saffron-400"
              }`}
            >
              {s === "all" ? "Any review" : s === "final" ? "Final" : "Pending review"}
            </button>
          ))}
        </div>
      </Panel>
      {scans.isError && (
        <p className="mb-3 rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900">
          Could not load the repository. Check that the backend is running.
        </p>
      )}
      <Panel>
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
                <TableCell colSpan={7}>
                  <EmptyState icon="search" title="No records match"
                    body="Try a different search, or run a scan from the Scan tab." />
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
      </Panel>
      <div className="flex items-center gap-2 text-sm">
        <span className="mr-auto text-xs text-slate-500">
          Page {safePage + 1} of {pageCount} · {sorted.length} records
        </span>
        <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={safePage === 0}>
          Previous
        </Button>
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
