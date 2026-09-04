"use client";

import {
  ColumnDef,
  SortingState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";

import { useAuth, useMounted } from "@/components/auth-context";
import { Badge, VerdictBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { listScans, type ScanSummary } from "@/lib/api";

const columns: ColumnDef<ScanSummary>[] = [
  {
    accessorKey: "created_at",
    header: ({ column }) => (
      <button className="font-bold uppercase" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Date {column.getIsSorted() === "asc" ? "▲" : column.getIsSorted() === "desc" ? "▼" : ""}
      </button>
    ),
    cell: ({ row }) => <span className="whitespace-nowrap tabular-nums">{row.original.created_at.slice(0, 16).replace("T", " ")}</span>,
  },
  {
    accessorKey: "preview",
    header: "Label",
    cell: ({ row }) => (
      <span className="block max-w-64 truncate font-medium" title={row.original.preview}>
        {row.original.preview || <span className="text-slate-400">—</span>}
      </span>
    ),
    enableSorting: false,
  },
  {
    accessorKey: "verdict",
    header: ({ column }) => (
      <button className="font-bold uppercase" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Status {column.getIsSorted() === "asc" ? "▲" : column.getIsSorted() === "desc" ? "▼" : ""}
      </button>
    ),
    cell: ({ row }) => <VerdictBadge verdict={row.original.verdict} />,
    filterFn: "equalsString",
  },
  {
    accessorKey: "status",
    header: "Review",
    cell: ({ row }) => (
      <Badge tone={row.original.status === "final" ? "blue" : "slate"}>
        {row.original.status === "final" ? "Final" : "Pending"}
      </Badge>
    ),
  },
  {
    accessorKey: "ocr_engine",
    header: ({ column }) => (
      <button className="font-bold uppercase" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}>
        Engine {column.getIsSorted() === "asc" ? "▲" : column.getIsSorted() === "desc" ? "▼" : ""}
      </button>
    ),
    cell: ({ row }) => <code className="text-xs">{row.original.ocr_engine}</code>,
  },
  {
    id: "actions",
    header: "",
    cell: ({ row }) => (
      <Link href={`/scans/${row.original.id}`} className="font-semibold text-slate-700 hover:underline">
        Details
      </Link>
    ),
  },
];

export default function ScansPage(): React.JSX.Element {
  const router = useRouter();
  const { session, ready } = useAuth();
  const mounted = useMounted();
  const [sorting, setSorting] = React.useState<SortingState>([{ id: "created_at", desc: true }]);
  const [globalFilter, setGlobalFilter] = React.useState("");
  const [verdict, setVerdict] = React.useState("all");

  React.useEffect(() => {
    if (ready && !session) router.replace("/login");
  }, [ready, session, router]);

  const scans = useQuery({
    queryKey: ["scans"],
    queryFn: () => listScans(session?.token ?? ""),
    enabled: ready && !!session,
  });

  const table = useReactTable({
    data: scans.data ?? [],
    columns,
    state: { sorting, globalFilter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 10 } },
  });

  React.useEffect(() => {
    table.getColumn("verdict")?.setFilterValue(verdict === "all" ? undefined : verdict);
  }, [verdict, table]);

  if (!mounted || !ready || !session) return <p className="text-sm text-slate-500">Loading…</p>;

  return (
    <div>
      <p className="text-xs text-slate-500">Inspect / Scan history</p>
      <h1 className="text-xl font-bold">Scan history</h1>
      <div className="mb-3 mt-4 flex flex-wrap items-center gap-2">
        <input
          value={globalFilter}
          onChange={(e) => setGlobalFilter(e.target.value)}
          placeholder="Search label, engine, ID…"
          className="min-w-56 rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        {(["all", "COMPLIANT", "NON_COMPLIANT", "INCOMPLETE"] as const).map((v) => (
          <button
            key={v}
            onClick={() => setVerdict(v)}
            className={`rounded-full border px-3 py-1 text-xs font-bold ${
              verdict === v ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 bg-white text-slate-600"
            }`}
          >
            {v === "all" ? "All" : v.charAt(0) + v.slice(1).toLowerCase().replace("_", "-")}
          </button>
        ))}
        <span className="ml-auto text-xs text-slate-500">
          {table.getFilteredRowModel().rows.length} of {scans.data?.length ?? 0} scans
        </span>
      </div>
      {scans.isError && (
        <p className="mb-3 rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900">
          Could not load scans. Check that the backend is running.
        </p>
      )}
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((hg) => (
            <TableRow key={hg.id}>
              {hg.headers.map((h) => (
                <TableHead key={h.id}>{flexRender(h.column.columnDef.header, h.getContext())}</TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={6} className="text-center text-slate-500">
                {scans.isPending ? "Loading…" : "No scans match."}
              </TableCell>
            </TableRow>
          ) : (
            table.getRowModel().rows.map((row) => (
              <TableRow key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>
                ))}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
      <div className="mt-3 flex items-center gap-2 text-sm">
        <Button variant="outline" size="sm" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>
          Previous
        </Button>
        <span className="text-xs text-slate-500">
          Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount() || 1}
        </span>
        <Button variant="outline" size="sm" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>
          Next
        </Button>
      </div>
    </div>
  );
}
