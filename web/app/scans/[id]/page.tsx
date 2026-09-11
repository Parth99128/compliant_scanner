"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import * as React from "react";

import { useAuth, useMounted } from "@/components/auth-context";
import { FindingRow, EDITABLE_RULES } from "@/components/finding-row";
import { AlertDestructive } from "@/components/ui/alert";
import { Badge, VerdictBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Hero, Panel, SourceBadge, sourceForRule } from "@/components/ui/ministry";
import { useToast } from "@/components/ui/toaster";
import { ApiError, explainScan, fetchBlob, getScan, reviewScan, updateFields, updateProduct, type Check, type FieldCorrections, type FrameInfo, type ScanDetail } from "@/lib/api";
import { cn } from "@/lib/utils";

function verdictTitle(v: string): string {
  if (v === "COMPLIANT") return "Compliant";
  if (v === "INCOMPLETE") return "Incomplete — needs verification";
  return "Non-compliant";
}

function RuleCard({
  check,
  declaration,
  measured,
}: {
  check: Check;
  declaration?: Record<string, unknown>;
  measured?: boolean;
}): React.JSX.Element {
  const tone =
    check.status === "PASS"
      ? "border-green-300 bg-green-50/50"
      : check.status === "NOT_ASSESSABLE"
        ? "border-amber-300 bg-amber-50/60"
        : "border-red-300 bg-red-50/50";
  return (
    <div className={cn("rounded-xl border bg-white p-4 shadow-sm", tone)}>
      <div className="flex flex-wrap items-center gap-1.5">
        <code className="rounded bg-navy-50 px-1.5 py-0.5 text-xs font-bold text-navy-900">{check.rule_id}</code>
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
        {check.cause === "possible_miss" && <Badge tone="amber">Needs verification — may be our miss</Badge>}
        {check.cause === "likely_genuine" && <Badge tone="red">Likely violation — verify</Badge>}
        {check.cause === "disputed" && <Badge tone="red">Disputed by officer</Badge>}
        {!check.manual && <SourceBadge source={sourceForRule(check.rule_id, declaration, !!measured)} />}
      </div>
      <p className="mt-0.5 text-xs text-slate-500">{check.citation}</p>
      <p className="mt-1.5 text-[13px]">{check.message}</p>
      {check.why && (
        <p className="mt-1.5 text-[13px] text-slate-700">
          <span className="font-semibold">Why:</span> {check.why}
        </p>
      )}
      {check.next_steps.length > 0 && (
        <ol className="mt-1.5 list-decimal space-y-0.5 pl-5 text-[13px] text-slate-700">
          {check.next_steps.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ol>
      )}
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

function GalleryCard({ scanId, token, d }: { scanId: string; token: string; d: ScanDetail }): React.JSX.Element {
  const [heatmap, setHeatmap] = React.useState(true);
  const [selected, setSelected] = React.useState<number | null>(null);
  const [playing, setPlaying] = React.useState(false);
  const [imgSize, setImgSize] = React.useState<{ id: string; w: number; h: number } | null>(null);

  const frames: FrameInfo[] = React.useMemo(() => {
    if (d.frames.length > 0) return d.frames;
    if (d.has_image) {
      // Pre-gallery rows: the single stored capture carries the detail boxes.
      return [
        {
          index: 0,
          is_best: true,
          measured: true,
          url: `/scans/${scanId}/image`,
          ocr_confidence: d.ocr_confidence,
          word_count: d.boxes.length,
          words_added: d.boxes.length,
          boxes: d.boxes,
          coord_w: d.coord_w,
          coord_h: d.coord_h,
        },
      ];
    }
    return [];
  }, [d, scanId]);

  const gallery = useQuery({
    queryKey: ["scan-frames", scanId],
    queryFn: async () => {
      const entries = await Promise.all(
        frames.map(async (f) => {
          const blob = await fetchBlob(f.url || `/scans/${scanId}/image`, token);
          return [f.index, URL.createObjectURL(blob)] as const;
        })
      );
      return new Map(entries);
    },
    enabled: frames.length > 0,
    staleTime: Infinity,
    retry: false,
  });

  React.useEffect(() => {
    const urls = gallery.data;
    return () => {
      urls?.forEach((u) => URL.revokeObjectURL(u));
    };
  }, [gallery.data]);

  const best = frames.find((f) => f.is_best) ?? frames[0];
  const current = frames.find((f) => f.index === selected) ?? best;
  const currentUrl = current ? gallery.data?.get(current.index) : undefined;

  React.useEffect(() => {
    if (!playing || frames.length < 2) return;
    const t = window.setInterval(() => {
      setSelected((prev) => {
        const order = frames.map((f) => f.index);
        const at = order.indexOf(prev ?? best?.index ?? order[0]);
        return order[(at + 1) % order.length];
      });
    }, 2500);
    return () => window.clearInterval(t);
  }, [playing, frames, best]);

  function step(dir: 1 | -1): void {
    if (!current || frames.length < 2) return;
    const order = frames.map((f) => f.index);
    const at = order.indexOf(current.index);
    setSelected(order[(at + dir + order.length) % order.length]);
  }

  return (
    <div className="rounded-md border border-slate-200 bg-white p-4 shadow-sm lg:sticky lg:top-6">
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <h2 className="text-sm font-bold">
          Label capture{frames.length > 1 ? `s (${frames.length} angles)` : ""}
        </h2>
        <span className="text-xs text-slate-500">{d.boxes.length} OCR words</span>
        <label className="ml-auto flex cursor-pointer items-center gap-1.5 text-xs font-semibold text-slate-600">
          <input type="checkbox" checked={heatmap} onChange={(e) => setHeatmap(e.target.checked)} className="accent-slate-900" />
          Confidence heatmap
        </label>
      </div>

      {frames.length === 0 || !current ? (
        <div className="grid h-56 place-items-center rounded border border-dashed border-slate-300 bg-slate-50 text-sm text-slate-500">
          No stored capture — this scan predates image storage. New scans include the photo.
        </div>
      ) : !currentUrl ? (
        <div className="grid h-56 place-items-center text-sm text-slate-500">
          {gallery.isPending ? "Loading captures…" : "Stored captures could not be loaded."}
        </div>
      ) : (
        <>
          <div className="relative overflow-hidden rounded border border-slate-200 bg-slate-950">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={currentUrl}
              alt={`Angle ${current.index + 1} of ${frames.length}`}
              className="mx-auto block max-h-[70vh] w-auto max-w-full object-contain"
              onLoad={(e) =>
                setImgSize({ id: `${scanId}:${current.index}`, w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })
              }
            />
                {current.boxes.length > 0 && imgSize && imgSize.id === `${scanId}:${current.index}` && (
                <svg
                  className="pointer-events-none absolute inset-0 h-full w-full"
                  viewBox={`0 0 ${current.coord_w ?? imgSize.w} ${current.coord_h ?? imgSize.h}`}
                  preserveAspectRatio="xMidYMid meet"
                  role="img"
                  aria-label={`${current.boxes.length} OCR word boxes for angle ${current.index + 1}`}
                >
                  {current.boxes.slice(0, 500).map((b, i) => (
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

          <div className="mt-2 flex items-center gap-2">
            <Button variant="outline" size="sm" disabled={frames.length < 2} onClick={() => step(-1)} aria-label="Previous angle">
              ‹
            </Button>
            <Button variant="outline" size="sm" disabled={frames.length < 2} onClick={() => step(1)} aria-label="Next angle">
              ›
            </Button>
            <span className="text-xs font-semibold text-slate-600">
              Angle {current.index + 1} of {frames.length}
              {current.is_best ? " · Best (measured)" : ""}
            </span>
            {frames.length > 1 && (
              <button
                type="button"
                onClick={() => setPlaying((v) => !v)}
                className="ml-auto text-xs font-bold text-slate-700 hover:underline"
              >
                {playing ? "❚❚ Pause slideshow" : "▶ Slideshow"}
              </button>
            )}
          </div>

          <div className="mt-2 flex gap-2 overflow-x-auto pb-1">
            {frames.map((f) => {
              const url = gallery.data?.get(f.index);
              const active = current.index === f.index;
              return (
                <button
                  key={f.index}
                  type="button"
                  onClick={() => {
                    setSelected(f.index);
                    setPlaying(false);
                  }}
                  className={cn(
                    "relative w-20 flex-none rounded-md border bg-slate-950",
                    active ? "border-slate-900 ring-2 ring-slate-900" : "border-slate-200"
                  )}
                  aria-label={`Show angle ${f.index + 1}${f.is_best ? " (best)" : ""}`}
                >
                  {url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={url} alt="" className="h-16 w-full rounded-md object-cover" loading="lazy" />
                  ) : (
                    <span className="grid h-16 w-full place-items-center text-[10px] text-slate-400">…</span>
                  )}
                  <span className="absolute left-1 top-1 rounded bg-slate-900/85 px-1 py-px text-[10px] font-bold text-white">
                    {f.index + 1}
                  </span>
                  {f.is_best && (
                    <span className="absolute right-1 top-1 rounded bg-green-700 px-1 py-px text-[10px] font-bold text-white">
                      Best
                    </span>
                  )}
                  {f.measured && !f.is_best && (
                    <span className="absolute bottom-1 right-1 rounded bg-sky-700 px-1 py-px text-[10px] font-bold text-white">
                      Measured
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          <p className="mt-1 text-xs tabular-nums text-slate-600">
            Angle {current.index + 1} read at {Math.round(current.ocr_confidence)}% · {current.word_count} words
            {current.words_added > 0 && frames.length > 1 ? ` · +${current.words_added} lines found only here` : ""}
          </p>
          {frames.length > 1 && (
            <p className="mt-1 text-[11px] text-slate-500">
              Final verdict merges all {frames.length} angles; type size is measured on angle{" "}
              {(d.measured_index ?? best?.index ?? 0) + 1}
              {best && d.measured_index != null && d.measured_index !== best.index
                ? ` (text led by angle ${best.index + 1})`
                : ""}
              .
            </p>
          )}
        </>
      )}

      <div className="mt-2 flex gap-4 text-[11px] text-slate-500">
        <span><i className="mr-1 inline-block h-0 w-4 border-t-2 border-green-400 align-middle" />High confidence (≥60%)</span>
        <span><i className="mr-1 inline-block h-0 w-4 border-t-2 border-red-400 align-middle" />Low confidence — verify on pack</span>
      </div>
    </div>
  );
}

export default function ScanDetailPage(): React.JSX.Element {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const router = useRouter();
  const { session, ready } = useAuth();
  const mounted = useMounted();
  const { notifyError } = useToast();
  const queryClient = useQueryClient();
  const [notes, setNotes] = React.useState("");
  const [actionError, setActionError] = React.useState("");
  const [busy, setBusy] = React.useState<"review" | "pdf" | "explain" | "fields" | null>(null);
  const [explanation, setExplanation] = React.useState("");
  const [showOcr, setShowOcr] = React.useState(false);
  const [editingProduct, setEditingProduct] = React.useState(false);
  const [pName, setPName] = React.useState("");
  const [pBrand, setPBrand] = React.useState("");
  const [pCat, setPCat] = React.useState("");
  const [editingFields, setEditingFields] = React.useState(false);
  const [fVals, setFVals] = React.useState<Record<string, string>>({});
  const [fBools, setFBools] = React.useState<Record<string, boolean>>({});

  React.useEffect(() => {
    if (ready && !session) router.replace("/login");
  }, [ready, session, router]);

  const detail = useQuery({
    queryKey: ["scan", id],
    queryFn: () => getScan(id, session?.token ?? ""),
    enabled: ready && !!session,
  });

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

  function declStr(key: string): string {
    const v = d.declaration[key];
    return v == null ? "" : String(v);
  }

  function openFieldEditor(): void {
    const vals: Record<string, string> = {};
    for (const k of [
      "manufacturer_name", "manufacturer_address", "generic_name",
      "net_quantity_value", "net_quantity_unit", "mrp", "mfg_date",
      "expiry_date", "consumer_care", "country_of_origin", "panel_area_cm2",
    ]) {
      vals[k] = declStr(k);
    }
    setFVals(vals);
    setFBools({
      mrp_includes_taxes: d.declaration["mrp_includes_taxes"] === true,
      is_imported: d.declaration["is_imported"] === true,
    });
    setEditingFields(true);
  }

  async function saveFields(): Promise<void> {
    if (!session) return;
    setActionError("");
    setBusy("fields");
    try {
      const body: FieldCorrections = {};
      const putText = (
        k:
          | "manufacturer_name"
          | "manufacturer_address"
          | "generic_name"
          | "net_quantity_unit"
          | "consumer_care"
          | "country_of_origin"
      ) => {
        body[k] = fVals[k] ?? "";
      };
      putText("manufacturer_name");
      putText("manufacturer_address");
      putText("generic_name");
      putText("net_quantity_unit");
      putText("consumer_care");
      putText("country_of_origin");
      const putNum = (k: "net_quantity_value" | "mrp" | "panel_area_cm2") => {
        const raw = (fVals[k] ?? "").trim();
        if (raw !== "" && !Number.isNaN(Number(raw))) body[k] = Number(raw);
      };
      putNum("net_quantity_value");
      putNum("mrp");
      putNum("panel_area_cm2");
      if ((fVals["mfg_date"] ?? "").trim() !== "") body.mfg_date = fVals["mfg_date"].trim();
      if ((fVals["expiry_date"] ?? "").trim() !== "") body.expiry_date = fVals["expiry_date"].trim();
      body.mrp_includes_taxes = !!fBools["mrp_includes_taxes"];
      body.is_imported = !!fBools["is_imported"];
      await updateFields(id, session.token, body);
      setEditingFields(false);
      await queryClient.invalidateQueries({ queryKey: ["scan", id] });
      await queryClient.invalidateQueries({ queryKey: ["scans"] });
      await queryClient.invalidateQueries({ queryKey: ["stats"] });
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Saving corrections failed.";
      setActionError(msg);
      notifyError(e, msg);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="animate-rise flex flex-col gap-4">
      <p className="text-xs text-slate-500">
        <Link href="/scans" className="font-semibold text-navy-800 hover:underline">Scan history</Link>
        <span className="mx-1.5 text-slate-300">/</span>
        <code className="rounded bg-navy-50 px-1.5 py-0.5 font-mono text-[11px] text-navy-900">{d.id}</code>
      </p>
      <Hero
        kicker={d.status === "final" ? "Final record" : "Pending review"}
        kickerHi="निरीक्षण विवरण"
        title={d.product_name || "Scan detail"}
        description={`${d.brand_name ? `${d.brand_name} · ` : ""}${d.category || "Uncategorised"} · Scan ${d.id.slice(0, 8)}`}
        tone={d.verdict === "COMPLIANT" ? "green" : d.verdict === "NON_COMPLIANT" ? "red" : "amber"}
        actions={<VerdictBadge verdict={d.verdict} />}
        meta={
          <Badge tone={d.status === "final" ? "blue" : "slate"}>{d.status === "final" ? "Final" : "Pending review"}</Badge>
        }
      />

      <div className="rounded-xl border-l-4 border-navy-800 bg-white px-5 py-4 shadow-sm">
        <p className="font-display text-base font-black text-navy-950">{verdictTitle(d.verdict)}</p>
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

      {d.corrected_by && (
        <p className="mt-3 rounded-md border border-sky-300 bg-sky-50 px-4 py-3 text-[13px] text-sky-900">
          Officer-corrected by <strong>{d.corrected_by}</strong>
          {d.corrected_at ? ` at ${d.corrected_at.slice(0, 16).replace("T", " ")}` : ""} — Rule 6
          values below are officer-verified; machine measurements unchanged.
        </p>
      )}

      {actionError && <AlertDestructive className="mt-3">{actionError}</AlertDestructive>}

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-5">
        <div className="xl:col-span-3">
          <GalleryCard scanId={id} token={session.token} d={d} />
        </div>

        <div className="flex flex-col gap-4 xl:col-span-2">
          <Panel
            title="Product identity"
            description="Auto-filled from the label at scan time; officers can correct it here."
            actions={!editingProduct ? (
              <button
                className="text-xs font-bold text-navy-800 hover:underline"
                onClick={() => {
                  setPName(d.product_name);
                  setPBrand(d.brand_name);
                  setPCat(d.category);
                  setEditingProduct(true);
                }}
              >
                Edit
              </button>
            ) : undefined}
          >
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
          </Panel>
          <Panel title="OCR reading">
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
              <dt className="text-slate-500">Location</dt>
              <dd className="font-semibold">
                {d.scan_lat != null && d.scan_lon != null
                  ? `${d.scan_lat.toFixed(5)}, ${d.scan_lon.toFixed(5)}`
                  : <span className="font-normal text-slate-400">Not attached</span>}
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
            {showOcr && <p className="mt-2 whitespace-pre-wrap rounded-lg border border-slate-100 bg-navy-50/60 p-3 text-xs text-slate-600">{d.ocr_text || "(no text extracted)"}</p>}
          </Panel>

          <Panel title="Officer review">
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
              <p className="rounded-lg border border-green-300 bg-green-50 px-3 py-2 text-xs font-semibold text-green-900">
                Finalized{reviewedNote(d)}. The report below is the exportable record.
              </p>
            )}
          </Panel>

          <Panel
            title="Report and explanation"
            description={d.status === "final"
              ? "Printable PDF with Rule 7 tables, findings and audit trail."
              : "PDF unlocks after review; explanation needs a server-side key."}
          >
            <div className="flex flex-wrap gap-2">
              <Button size="sm" disabled={busy !== null} onClick={downloadPdf}>
                {busy === "pdf" ? "Working…" : "Download PDF"}
              </Button>
              <Button variant="outline" size="sm" disabled={busy !== null} onClick={doExplain}>
                {busy === "explain" ? "Working…" : "AI explanation"}
              </Button>
            </div>
            {explanation && <p className="mt-2 whitespace-pre-wrap rounded-lg border border-sky-300 bg-sky-50 px-3 py-2 text-xs text-sky-900">{explanation}</p>}
          </Panel>

          <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-5 pb-3 pt-4">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-slate-400">Rule 6 · Mandatory declarations</p>
                <h2 className="font-display text-[17px] font-black tracking-tight text-navy-950">Extracted declarations</h2>
              </div>
              {!editingFields && (
                <button
                  className="flex-none rounded-lg border border-navy-100 bg-navy-50 px-3 py-1.5 text-xs font-bold text-navy-900 hover:bg-navy-100"
                  onClick={openFieldEditor}
                >
                  Correct values
                </button>
              )}
            </div>
            <div className="px-5 pb-4">
            <p className="mb-3 text-xs text-slate-500">Correct a mis-read value or mark a declaration present. Amber cards need measurement — never passes.</p>
            <p className="mb-3 text-[11px] leading-relaxed text-slate-400">
              Source badges — <strong>Read</strong>: taken straight off the label text ·
              <strong> Inferred</strong>: model or directory filled a gap, verify ·
              <strong> AI assist</strong>: second-opinion model supplied it ·
              <strong> Uncertain</strong>: weak read, verify.
            </p>
            {editingFields ? (
              <div className="mb-3 rounded-md border border-sky-300 bg-sky-50/50 p-3">
                <p className="mb-2 text-xs font-semibold text-sky-900">
                  Fix OCR-mangled Rule 6 values. Machine-measured sizes cannot be edited. Saving re-runs the rules.
                </p>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {[
                    ["manufacturer_name", "Maker name"],
                    ["manufacturer_address", "Maker address"],
                    ["generic_name", "Generic name"],
                    ["net_quantity_value", "Net qty value"],
                    ["net_quantity_unit", "Net qty unit"],
                    ["mrp", "MRP amount"],
                    ["consumer_care", "Care contact"],
                    ["country_of_origin", "Origin country"],
                    ["panel_area_cm2", "Panel area (cm²)"],
                  ].map(([k, label]) => (
                    <label key={k} className="block text-xs font-semibold text-slate-600">
                      {label}
                      <input
                        value={fVals[k] ?? ""}
                        onChange={(e) => setFVals((p) => ({ ...p, [k]: e.target.value }))}
                        className="mt-0.5 w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-[13px] font-normal"
                      />
                    </label>
                  ))}
                  <label className="block text-xs font-semibold text-slate-600">
                    Mfg date
                    <input
                      type="date"
                      aria-label="Manufacture date"
                      value={(fVals["mfg_date"] ?? "").slice(0, 10)}
                      onChange={(e) => setFVals((p) => ({ ...p, mfg_date: e.target.value }))}
                      className="mt-0.5 w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-[13px] font-normal"
                    />
                  </label>
                  <label className="block text-xs font-semibold text-slate-600">
                    Expiry date
                    <input
                      type="date"
                      aria-label="Expiry date"
                      value={(fVals["expiry_date"] ?? "").slice(0, 10)}
                      onChange={(e) => setFVals((p) => ({ ...p, expiry_date: e.target.value }))}
                      className="mt-0.5 w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-[13px] font-normal"
                    />
                  </label>
                </div>
                <div className="mt-2 flex flex-wrap gap-4 text-[13px] font-medium text-slate-700">
                  <label className="flex cursor-pointer items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={!!fBools["mrp_includes_taxes"]}
                      onChange={(e) => setFBools((p) => ({ ...p, mrp_includes_taxes: e.target.checked }))}
                      className="accent-slate-900"
                    />
                    MRP includes all taxes
                  </label>
                  <label className="flex cursor-pointer items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={!!fBools["is_imported"]}
                      onChange={(e) => setFBools((p) => ({ ...p, is_imported: e.target.checked }))}
                      className="accent-slate-900"
                    />
                    Imported pack
                  </label>
                </div>
                <div className="mt-3 flex gap-2">
                  <Button size="sm" disabled={busy !== null} onClick={saveFields}>
                    {busy === "fields" ? "Saving…" : "Save corrections"}
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => setEditingFields(false)}>Cancel</Button>
                </div>
              </div>
            ) : (
            <div className="flex flex-col gap-2.5">
              {d.results
                .filter((r) => EDITABLE_RULES.has(r.rule_id))
                .map((r) => (
                  <FindingRow
                    key={r.rule_id}
                    scanId={id}
                    token={session.token}
                    check={r}
                    declaration={d.declaration}
                    measured={d.font_height_mm != null}
                    onChanged={() => {
                      void queryClient.invalidateQueries({ queryKey: ["scan", id] });
                      void queryClient.invalidateQueries({ queryKey: ["scans"] });
                      void queryClient.invalidateQueries({ queryKey: ["stats"] });
                    }}
                    onError={(e, msg) => {
                      setActionError(msg);
                      notifyError(e, msg);
                    }}
                  />
                ))}
              {d.results
                .filter((r) => !EDITABLE_RULES.has(r.rule_id))
                .map((r, i) => (
                  <RuleCard
                    key={`${r.rule_id}-${i}`}
                    check={r}
                    declaration={d.declaration}
                    measured={d.font_height_mm != null}
                  />
                ))}
            </div>
            )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
