"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import * as React from "react";

import { useAuth, useMounted } from "@/components/auth-context";
import { AlertDestructive } from "@/components/ui/alert";
import { Badge, VerdictBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toaster";
import { ApiError, explainScan, fetchBlob, getScan, reviewScan, updateProduct, type Check } from "@/lib/api";
import { cn } from "@/lib/utils";

function verdictClasses(v: string): string {
  if (v === "COMPLIANT") return "border-green-300 bg-green-50";
  if (v === "INCOMPLETE") return "border-amber-300 bg-amber-50";
  return "border-red-300 bg-red-50";
}

function verdictTitle(v: string): string {
  if (v === "COMPLIANT") return "Compliant";
  if (v === "INCOMPLETE") return "Incomplete — measurement needed";
  return "Non-compliant";
}

function RuleCard({ check }: { check: Check }): React.JSX.Element {
  const bar =
    check.status === "PASS"
      ? "border-l-green-700"
      : check.status === "NOT_ASSESSABLE"
        ? "border-l-amber-500 bg-amber-50/50"
        : "border-l-red-700";
  return (
    <div className={cn("rounded-md border border-slate-200 border-l-4 bg-white p-3", bar)}>
      <div className="flex flex-wrap items-center gap-1.5">
        <code className="text-xs font-bold">{check.rule_id}</code>
        {check.status === "PASS" ? (
          <Badge tone="green">Pass</Badge>
        ) : check.status === "NOT_ASSESSABLE" ? (
          <Badge tone="amber">Not assessable</Badge>
        ) : check.status === "NOT_FOUND" ? (
          <Badge tone="red">Not found</Badge>
        ) : (
          <Badge tone="red">Fail</Badge>
        )}
        {check.citation_verified ? <Badge tone="blue">Verified</Badge> : <Badge>Unverified</Badge>}
      </div>
      <p className="mt-0.5 text-xs text-slate-500">{check.citation}</p>
      <p className="mt-1.5 text-[13px]">{check.message}</p>
      {(check.observed || check.expected) && (
        <div className="mt-2 rounded border border-slate-100 bg-slate-50 px-2.5 py-1.5 text-xs text-slate-600">
          <p>Observed: {check.observed ?? "—"}</p>
          <p>Expected: {check.expected ?? "—"}</p>
        </div>
      )}
      {check.remedy && <p className="mt-1.5 text-xs text-amber-900">Remedy: {check.remedy}</p>}
    </div>
  );
}

function reviewedNote(d: { reviewed_by: string | null; reviewed_at: string | null }): string {
  const who = d.reviewed_by ? ` by ${d.reviewed_by}` : "";
  const when = d.reviewed_at ? ` at ${d.reviewed_at.slice(0, 16).replace("T", " ")}` : "";
  return `${who}${when}`;
}

export default function ScanDetailPage(): React.JSX.Element {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const router = useRouter();
  const { session, ready } = useAuth();
  const mounted = useMounted();
  const { notifyError } = useToast();
  const queryClient = useQueryClient();
  const [heatmap, setHeatmap] = React.useState(true);
  const [notes, setNotes] = React.useState("");
  const [actionError, setActionError] = React.useState("");
  const [busy, setBusy] = React.useState<"review" | "pdf" | "explain" | null>(null);
  const [explanation, setExplanation] = React.useState("");
  const [showOcr, setShowOcr] = React.useState(false);
  const [editingProduct, setEditingProduct] = React.useState(false);
  const [pName, setPName] = React.useState("");
  const [pBrand, setPBrand] = React.useState("");
  const [pCat, setPCat] = React.useState("");
  const [imgSize, setImgSize] = React.useState<{ id: string; w: number; h: number } | null>(null);

  React.useEffect(() => {
    if (ready && !session) router.replace("/login");
  }, [ready, session, router]);

  const detail = useQuery({
    queryKey: ["scan", id],
    queryFn: () => getScan(id, session?.token ?? ""),
    enabled: ready && !!session,
  });

  const image = useQuery({
    queryKey: ["scan-image", id],
    queryFn: async () => {
      const blob = await fetchBlob(`/scans/${id}/image`, session?.token ?? "");
      return URL.createObjectURL(blob);
    },
    // Always try: pre-image rows 404 into the "no capture" placeholder below.
    enabled: ready && !!session,
    staleTime: Infinity,
    retry: false,
  });

  React.useEffect(() => {
    const url = image.data;
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [image.data]);

  if (!mounted || !ready || !session) return <p className="text-sm text-slate-500">Loading…</p>;
  if (detail.isPending) return <p className="text-sm text-slate-500">Loading scan…</p>;
  if (detail.isError)
    return (
      <AlertDestructive>
        Could not load this scan. It may not exist or belong to another officer.
      </AlertDestructive>
    );

  const d = detail.data;
  const unassessed = d.results.filter((r) => r.status === "NOT_ASSESSABLE").length;
  const lowConf = d.ocr_confidence < 60;

  async function doReview(decision: "confirm" | "override"): Promise<void> {
    if (!session) return;
    if (decision === "override" && !notes.trim()) {
      setActionError("Override requires a written justification for the audit trail.");
      return;
    }
    setActionError("");
    setBusy("review");
    try {
      await reviewScan(id, session.token, decision, notes || "verified on screen");
      setNotes("");
      await queryClient.invalidateQueries({ queryKey: ["scan", id] });
      await queryClient.invalidateQueries({ queryKey: ["scans"] });
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Review failed. Try again.";
      setActionError(msg);
      notifyError(e, msg);
    } finally {
      setBusy(null);
    }
  }

  async function downloadPdf(): Promise<void> {
    if (!session) return;
    setActionError("");
    setBusy("pdf");
    try {
      const blob = await fetchBlob(`/scans/${id}/report`, session.token);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `scan-${id}.pdf`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Report download failed.";
      setActionError(msg);
      notifyError(e, msg);
    } finally {
      setBusy(null);
    }
  }

  async function doExplain(): Promise<void> {
    if (!session) return;
    setActionError("");
    setExplanation("");
    setBusy("explain");
    try {
      setExplanation(await explainScan(id, session.token));
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Explanation failed.";
      setActionError(msg);
      notifyError(e, msg);
    } finally {
      setBusy(null);
    }
  }

  async function saveProduct(): Promise<void> {
    if (!session) return;
    setActionError("");
    setBusy("review");
    try {
      await updateProduct(id, session.token, { product_name: pName, brand_name: pBrand, category: pCat });
      setEditingProduct(false);
      await queryClient.invalidateQueries({ queryKey: ["scan", id] });
      await queryClient.invalidateQueries({ queryKey: ["scans"] });
      await queryClient.invalidateQueries({ queryKey: ["stats"] });
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Saving product failed.";
      setActionError(msg);
      notifyError(e, msg);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <p className="text-xs text-slate-500">
        <Link href="/scans" className="hover:underline">Scan history</Link> / <code>{d.id}</code>
      </p>
      <div className="mt-1 flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-bold">Scan detail</h1>
        <VerdictBadge verdict={d.verdict} />
        <Badge tone={d.status === "final" ? "blue" : "slate"}>{d.status === "final" ? "Final" : "Pending review"}</Badge>
      </div>

      <div className={cn("mt-4 rounded-md border p-4", verdictClasses(d.verdict))}>
        <p className="text-base font-bold">{verdictTitle(d.verdict)}</p>
        <p className="mt-0.5 text-[13px] text-slate-600">
          {d.verdict === "COMPLIANT" && "All assessable declarations passed. No blocking violations."}
          {d.verdict === "NON_COMPLIANT" && "One or more mandatory declarations failed or are missing."}
          {d.verdict === "INCOMPLETE" && (
            <>
              {unassessed} rule{unassessed === 1 ? "" : "s"} could not run on an uncalibrated image.{" "}
              <strong>Unmeasured is not a pass.</strong>
            </>
          )}
        </p>
      </div>

      {actionError && <AlertDestructive className="mt-3">{actionError}</AlertDestructive>}

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-5">
        <div className="xl:col-span-3">
          <div className="rounded-md border border-slate-200 bg-white p-4 shadow-sm lg:sticky lg:top-6">
            <div className="mb-2 flex flex-wrap items-center gap-3">
              <h2 className="text-sm font-bold">Label capture</h2>
              <span className="text-xs text-slate-500">{d.boxes.length} OCR words</span>
              <label className="ml-auto flex cursor-pointer items-center gap-1.5 text-xs font-semibold text-slate-600">
                <input type="checkbox" checked={heatmap} onChange={(e) => setHeatmap(e.target.checked)} className="accent-slate-900" />
                Confidence heatmap
              </label>
            </div>
            {image.data ? (
              <div className="relative overflow-hidden rounded border border-slate-200 bg-slate-950">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={image.data}
                  alt="Scanned label"
                  className="block w-full"
                  onLoad={(e) => setImgSize({ id, w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })}
                />
                {imgSize && imgSize.id === id && (
                <svg
                  className="pointer-events-none absolute inset-0 h-full w-full"
                  viewBox={`0 0 ${d.coord_w ?? imgSize.w} ${d.coord_h ?? imgSize.h}`}
                  preserveAspectRatio="none"
                  role="img"
                  aria-label={`${d.boxes.length} OCR word boxes`}
                >
                  {d.boxes.slice(0, 500).map((b, i) => (
                    <rect
                      key={i}
                      x={b.x}
                      y={b.y}
                      width={b.w}
                      height={b.h}
                      fill="none"
                      stroke={!heatmap ? "#4ade80" : b.confidence >= 60 ? "#4ade80" : "#f87171"}
                      strokeWidth={Math.max(imgSize.w, imgSize.h) / 400}
                    >
                      <title>{`${b.text} (${Math.round(b.confidence)}%)`}</title>
                    </rect>
                  ))}
                </svg>
                )}
              </div>
            ) : image.isPending ? (
              <div className="grid h-56 place-items-center text-sm text-slate-500">Loading capture…</div>
            ) : (
              <div className="grid h-56 place-items-center rounded border border-dashed border-slate-300 bg-slate-50 text-sm text-slate-500">
                {image.error instanceof ApiError && image.error.status === 404
                  ? "No stored capture — this scan predates image storage. New scans include the photo."
                  : "Stored capture could not be loaded."}
              </div>
            )}
            <div className="mt-2 flex gap-4 text-[11px] text-slate-500">
              <span><i className="mr-1 inline-block h-0 w-4 border-t-2 border-green-400 align-middle" />High confidence (≥60%)</span>
              <span><i className="mr-1 inline-block h-0 w-4 border-t-2 border-red-400 align-middle" />Low confidence — verify on pack</span>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-4 xl:col-span-2">
          <div className="rounded-md border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold">Product identity</h2>
              {!editingProduct && (
                <button
                  className="text-xs font-bold text-slate-700 hover:underline"
                  onClick={() => {
                    setPName(d.product_name);
                    setPBrand(d.brand_name);
                    setPCat(d.category);
                    setEditingProduct(true);
                  }}
                >
                  Edit
                </button>
              )}
            </div>
            {!editingProduct ? (
              <dl className="mt-2 grid grid-cols-[110px_1fr] gap-x-2 gap-y-1 text-[13px]">
                <dt className="text-slate-500">Product</dt>
                <dd className="font-semibold">{d.product_name || <span className="font-normal text-slate-400">—</span>}</dd>
                <dt className="text-slate-500">Brand</dt>
                <dd className="font-semibold">{d.brand_name || <span className="font-normal text-slate-400">—</span>}</dd>
                <dt className="text-slate-500">Category</dt>
                <dd className="font-semibold">{d.category || <span className="font-normal text-slate-400">—</span>}</dd>
              </dl>
            ) : (
              <div className="mt-2 flex flex-col gap-2">
                <input aria-label="Product name" value={pName} onChange={(e) => setPName(e.target.value)} placeholder="Product name"
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
                <input aria-label="Brand" value={pBrand} onChange={(e) => setPBrand(e.target.value)} placeholder="Brand / maker"
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
                <input aria-label="Category" value={pCat} onChange={(e) => setPCat(e.target.value)} placeholder="Category (e.g. Snacks)"
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
                <div className="flex gap-2">
                  <Button size="sm" disabled={busy !== null} onClick={saveProduct}>
                    {busy === "review" ? "Saving…" : "Save"}
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => setEditingProduct(false)}>Cancel</Button>
                </div>
              </div>
            )}
            <p className="mt-2 text-[11px] text-slate-500">Auto-filled from the label at scan time; officers can correct it here.</p>
          </div>
          <div className="rounded-md border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-bold">OCR reading</h2>
            <dl className="mt-2 grid grid-cols-[110px_1fr] gap-x-2 gap-y-1 text-[13px]">
              <dt className="text-slate-500">Engine</dt>
              <dd className="font-semibold"><code className="text-xs">{d.ocr_engine}</code></dd>
              <dt className="text-slate-500">Confidence</dt>
              <dd className="font-semibold">{d.ocr_confidence}%</dd>
              <dt className="text-slate-500">Type height</dt>
              <dd className="font-semibold">{d.font_height_mm ?? "—"} {d.font_height_mm != null ? "mm" : ""}</dd>
              <dt className="text-slate-500">PPM scale</dt>
              <dd className="font-semibold">
                {d.ppm_used != null ? `${d.ppm_used} px/mm` : "—"}
              </dd>
            </dl>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200">
              <div className="h-full rounded-full bg-slate-900" style={{ width: `${Math.min(100, d.ocr_confidence)}%` }} />
            </div>
            {lowConf && (
              <p className="mt-2 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                Below 60% — verify against the physical package.
              </p>
            )}
            {d.warnings.map((w, i) => (
              <p key={i} className="mt-2 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">{w}</p>
            ))}
            <Button variant="outline" size="sm" className="mt-2" onClick={() => setShowOcr((v) => !v)}>
              {showOcr ? "Hide OCR text" : "Show OCR text"}
            </Button>
            {showOcr && <p className="mt-2 whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs text-slate-600">{d.ocr_text || "(no text extracted)"}</p>}
          </div>

          <div className="rounded-md border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-bold">Officer review</h2>
            <p className="mb-2 text-xs text-slate-500">
              {d.status === "final" ? `Finalized${d.reviewed_by ? ` by ${d.reviewed_by}` : ""}.` : "Pending review — reports unlock after finalizing."}
            </p>
            {d.status !== "final" ? (
              <>
                <label className="mb-1 block text-xs font-semibold text-slate-600" htmlFor="notes">Review notes (required to override)</label>
                <textarea id="notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)}
                  placeholder="Findings verified against the physical label…"
                  className="mb-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
                <div className="flex flex-wrap gap-2">
                  <Button variant="success" size="sm" disabled={busy !== null} onClick={() => doReview("confirm")}>
                    {busy === "review" ? "Working…" : "Confirm and finalize"}
                  </Button>
                  <Button variant="destructive" size="sm" disabled={busy !== null} onClick={() => doReview("override")}>
                    Override (admin)
                  </Button>
                </div>
              </>
            ) : (
              <p className="rounded border border-green-300 bg-green-50 px-3 py-2 text-xs text-green-900">
                Finalized{reviewedNote(d)}. The report below is the exportable record.
              </p>
            )}
          </div>

          <div className="rounded-md border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-bold">Report and explanation</h2>
            <p className="mb-2 text-xs text-slate-500">
              {d.status === "final"
                ? "Printable PDF with Rule 7 tables, findings and audit trail."
                : "PDF unlocks after review; explanation needs a server-side key."}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" disabled={busy !== null} onClick={downloadPdf}>
                {busy === "pdf" ? "Working…" : "Download PDF"}
              </Button>
              <Button variant="outline" size="sm" disabled={busy !== null} onClick={doExplain}>
                {busy === "explain" ? "Working…" : "AI explanation"}
              </Button>
            </div>
            {explanation && <p className="mt-2 whitespace-pre-wrap rounded border border-sky-300 bg-sky-50 px-3 py-2 text-xs text-sky-900">{explanation}</p>}
          </div>

          <div className="rounded-md border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-bold">Rule findings ({d.results.length})</h2>
            <p className="mb-3 text-xs text-slate-500">Amber cards need measurement — never passes. “Verified” means checked vs gazette PDF.</p>
            <div className="flex flex-col gap-2.5">
              {d.results.map((r) => (
                <RuleCard key={r.rule_id} check={r} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
