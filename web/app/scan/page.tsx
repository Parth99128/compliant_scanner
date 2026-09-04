"use client";

import { useRouter } from "next/navigation";
import * as React from "react";

import { useAuth, useMounted } from "@/components/auth-context";
import { AlertDestructive, AlertInfo } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toaster";
import { ApiError, uploadScan } from "@/lib/api";
import { cn } from "@/lib/utils";

const STAGES = [
  "Uploading captures",
  "Enhancing + running OCR",
  "Extracting declarations",
  "Evaluating rules and verdict",
];

function StageRail({ active, done }: { active: number; done: boolean }): React.JSX.Element {
  return (
    <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-4" aria-live="polite">
      <div className="mb-3 h-1.5 overflow-hidden rounded-full bg-slate-200">
        <div
          className="h-full rounded-full bg-slate-900 transition-all duration-700 ease-out"
          style={{ width: done ? "100%" : `${8 + (active / STAGES.length) * 84}%` }}
        />
      </div>
      <ol className="flex flex-col gap-2">
        {STAGES.map((label, i) => {
          const state = done || i < active ? "done" : i === active ? "active" : "todo";
          return (
            <li key={label} className="flex items-center gap-2.5 text-[13px]">
              <span
                className={cn(
                  "grid h-5 w-5 flex-none place-items-center rounded-full text-[11px] font-bold",
                  state === "done" && "bg-green-700 text-white",
                  state === "active" && "bg-slate-900 text-white",
                  state === "todo" && "bg-slate-200 text-slate-500"
                )}
              >
                {state === "done" ? "✓" : state === "active" ? <span className="spinner" /> : i + 1}
              </span>
              <span className={state === "todo" ? "text-slate-400" : "font-semibold text-slate-800"}>
                {label}
                {state === "active" && <span className="dots" />}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export default function ScanPage(): React.JSX.Element {
  const router = useRouter();
  const { session, ready } = useAuth();
  const mounted = useMounted();
  const { notifyError } = useToast();
  const [files, setFiles] = React.useState<File[]>([]);
  const [dragOver, setDragOver] = React.useState(false);
  const [ppm, setPpm] = React.useState("");
  const [fontPx, setFontPx] = React.useState("");
  const [panelArea, setPanelArea] = React.useState("");
  const [embossed, setEmbossed] = React.useState(false);
  const [error, setError] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [stage, setStage] = React.useState(0);
  const [finished, setFinished] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const previews = React.useMemo(() => files.map((f) => URL.createObjectURL(f)), [files]);
  React.useEffect(() => () => previews.forEach((u) => URL.revokeObjectURL(u)), [previews]);

  React.useEffect(() => {
    if (ready && !session) router.replace("/login");
  }, [ready, session, router]);

  // Advance the stage rail while the server works; cleared on settle.
  React.useEffect(() => {
    if (!busy) return;
    const t = window.setInterval(() => setStage((s) => Math.min(s + 1, STAGES.length - 1)), 5000);
    return () => window.clearInterval(t);
  }, [busy]);

  if (!mounted || !ready || !session) return <p className="text-sm text-slate-500">Loading…</p>;

  function add(list: FileList | File[] | null): void {
    if (!list) return;
    setError("");
    setFiles((prev) => {
      const seen = new Set(prev.map((f) => `${f.name}:${f.size}`));
      const fresh = [...list].filter((f) => f.type.startsWith("image/") && !seen.has(`${f.name}:${f.size}`));
      return [...prev, ...fresh].slice(0, 5);
    });
  }

  function removeAt(index: number): void {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  async function submit(): Promise<void> {
    if (!session || files.length === 0 || busy) return;
    setError("");
    setFinished(false);
    setStage(0);
    setBusy(true);
    try {
      const created = await uploadScan(files, { ppm, fontPx, panelArea, embossed }, session.token);
      setFinished(true);
      window.setTimeout(() => router.push(`/scans/${created.id}`), 650);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Upload failed.";
      setError(msg);
      notifyError(e, msg);
      setBusy(false);
    }
  }

  return (
    <div className="animate-rise">
      <p className="text-xs text-slate-500">Inspect / New scan</p>
      <h1 className="text-xl font-bold">New label scan</h1>
      <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
        <div className="rounded-md border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-baseline justify-between gap-2">
            <h2 className="text-sm font-bold">Label photos</h2>
            <span className={cn("text-xs font-bold", files.length > 1 ? "text-green-800" : "text-slate-400")}>
              {files.length}/5{files.length > 1 ? " · merge mode" : ""}
            </span>
          </div>
          <p className="mb-3 text-xs text-slate-500">
            One close-up of the declaration panel — or several angles to merge into a single verdict.
          </p>
          <div
            role="button"
            tabIndex={0}
            aria-label="Add label photos"
            onClick={() => inputRef.current?.click()}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") inputRef.current?.click(); }}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); add(e.dataTransfer.files); }}
            className={cn(
              "cursor-pointer rounded-md border-2 border-dashed p-5 text-center transition-colors",
              dragOver ? "border-slate-900 bg-slate-100" : "border-slate-300 bg-slate-50 hover:border-slate-500"
            )}
          >
            <p className="text-sm font-bold text-slate-800">
              {files.length === 0 ? "Drop photos here or click to browse" : "Add more angles or drag them in"}
            </p>
            <p className="mt-0.5 text-xs text-slate-500">JPG / PNG / WebP · each click adds, nothing is replaced</p>
            <input
              ref={inputRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={(e) => { add(e.target.files); e.target.value = ""; }}
            />
          </div>
          {previews.length > 0 && (
            <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-5">
              {previews.map((u, i) => (
                <div key={`${files[i]?.name}:${i}`} className="animate-pop group relative">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={u} alt={`Capture ${i + 1}`} className="h-24 w-full rounded-md border border-slate-200 object-cover" />
                  <span className="absolute left-1 top-1 rounded bg-slate-900/85 px-1.5 py-0.5 text-[10px] font-bold text-white">
                    {i === 0 ? "Base" : `Angle ${i + 1}`}
                  </span>
                  <button
                    type="button"
                    aria-label={`Remove capture ${i + 1}`}
                    onClick={() => removeAt(i)}
                    className="absolute right-1 top-1 grid h-5 w-5 place-items-center rounded-full bg-white/95 text-xs font-bold text-red-700 opacity-0 shadow transition-opacity group-hover:opacity-100 focus:opacity-100"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
          {files.length > 1 && (
            <AlertInfo className="mt-3">
              {files.length} angles selected — text will be unioned by confidence into one verdict.
            </AlertInfo>
          )}
        </div>
        <div className="rounded-md border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-bold">Spatial calibration (Rule 7)</h2>
          <p className="mb-3 text-xs text-slate-500">
            Font height in mm = pixels ÷ PPM. Without calibration, font rules return “not assessable” — never a pass.
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-600" htmlFor="ppm">PPM (px/mm)</label>
              <input id="ppm" value={ppm} onChange={(e) => setPpm(e.target.value)} placeholder="Auto-detect"
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-600" htmlFor="fpx">Glyph height (px)</label>
              <input id="fpx" value={fontPx} onChange={(e) => setFontPx(e.target.value)} placeholder="Median"
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-600" htmlFor="area">Panel area (cm²)</label>
              <input id="area" value={panelArea} onChange={(e) => setPanelArea(e.target.value)} placeholder="Table-II"
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
            </div>
          </div>
          <label className="mt-3 flex cursor-pointer items-center gap-2 text-[13px] font-medium text-slate-700">
            <input type="checkbox" checked={embossed} onChange={(e) => setEmbossed(e.target.checked)} className="accent-slate-900" />
            Blown / moulded / embossed (higher minima apply)
          </label>
          {error && <AlertDestructive className="mt-3">{error}</AlertDestructive>}
          <Button disabled={busy || files.length === 0} onClick={submit} className="mt-4">
            {busy ? "Analyzing…" : files.length > 1 ? `Merge ${files.length} angles and scan` : "Run compliance scan"}
          </Button>
          {busy && <StageRail active={stage} done={finished} />}
        </div>
      </div>
    </div>
  );
}
