"use client";

import { useRouter } from "next/navigation";
import * as React from "react";

import { useAuth, useMounted } from "@/components/auth-context";
import { LiveScanner } from "@/components/live-scanner";
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
  const [rejected, setRejected] = React.useState<string[]>([]);
  const [dragOver, setDragOver] = React.useState(false);
  const [ppm, setPpm] = React.useState("");
  const [fontPx, setFontPx] = React.useState("");
  const [panelArea, setPanelArea] = React.useState("");
  const [embossed, setEmbossed] = React.useState(false);
  const [attachGps, setAttachGps] = React.useState(false);
  const [gpsNote, setGpsNote] = React.useState("");
  const [error, setError] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [stage, setStage] = React.useState(0);
  const [finished, setFinished] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [source, setSource] = React.useState<"camera" | "live" | "upload">("camera");
  const [camError, setCamError] = React.useState("");
  const [camOn, setCamOn] = React.useState(false);
  const [shotStep, setShotStep] = React.useState<1 | 2>(1);
  const videoRef = React.useRef<HTMLVideoElement>(null);
  const streamRef = React.useRef<MediaStream | null>(null);

  const cameraSupported =
    typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia;
  const insecure =
    typeof window !== "undefined" && window.isSecureContext === false;

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

  function stopCamera(): void {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setCamOn(false);
  }

  React.useEffect(() => stopCamera, []);

  async function startCamera(): Promise<void> {
    setCamError("");
    if (!cameraSupported) {
      setCamError("This browser cannot open the camera here. Use Upload instead.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCamOn(true);
    } catch {
      setCamError(
        insecure
          ? "Camera is blocked on plain-HTTP addresses. Open this page via localhost or HTTPS, enable camera access, or use Upload."
          : "Camera unavailable — check permission, or use Upload instead."
      );
    }
  }

  function captureShot(): void {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0);
    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        const name = shotStep === 1 ? "context-shot.jpg" : `macro-shot-${files.length + 1}.jpg`;
        add([new File([blob], name, { type: "image/jpeg", lastModified: Date.now() })]);
        if (shotStep === 1) setShotStep(2);
      },
      "image/jpeg",
      0.92
    );
  }

  if (!mounted || !ready || !session) return <p className="text-sm text-slate-500">Loading…</p>;

  function add(list: FileList | File[] | null): void {
    if (!list) return;
    setError("");
    const arr = Array.from(list as ArrayLike<File>);
    const seen = new Set(
      // read current names without stale closure issues: functional update below recomputes
      files.map((f) => `${f.name}:${f.size}`)
    );
    const fresh: File[] = [];
    const bad: string[] = [];
    for (const f of arr) {
      const name = f.name || "unnamed file";
      const lowerType = (f.type || "").toLowerCase();
      if (lowerType === "image/heic" || lowerType === "image/heif" || /\.hei[cf]$/i.test(name)) {
        bad.push(`${name} (HEIC — export as JPG/PNG first)`);
        continue;
      }
      const isImage = f.type
        ? f.type.startsWith("image/")
        : /\.(jpe?g|png|webp|bmp|tiff?)$/i.test(name);
      if (!isImage || seen.has(`${f.name}:${f.size}`)) {
        if (!isImage) bad.push(name);
        continue;
      }
      seen.add(`${f.name}:${f.size}`);
      fresh.push(f);
    }
    setRejected(bad);
    if (fresh.length > 0) {
      setFiles((prev) => {
        const seenNow = new Set(prev.map((f) => `${f.name}:${f.size}`));
        return [...prev, ...fresh.filter((f) => !seenNow.has(`${f.name}:${f.size}`))].slice(0, 5);
      });
    }
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
    // Optional inspection GPS for the legal trail (officer opt-in at submit).
    let lat: number | null = null;
    let lon: number | null = null;
    if (attachGps && typeof navigator !== "undefined" && navigator.geolocation) {
      try {
        const pos = await new Promise<GeolocationPosition>((resolve, reject) =>
          navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 8000 })
        );
        lat = pos.coords.latitude;
        lon = pos.coords.longitude;
      } catch {
        setGpsNote("Location unavailable — continuing without GPS.");
      }
    }
    try {
      const created = await uploadScan(files, { ppm, fontPx, panelArea, embossed, lat, lon }, session.token);
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
          <div className="mb-3 grid grid-cols-3 gap-1 rounded-md bg-slate-100 p-1 text-sm font-bold" role="tablist" aria-label="Photo source">
            <button
              type="button" role="tab" aria-selected={source === "camera"}
              onClick={() => { stopCamera(); setSource("camera"); }}
              className={cn("rounded py-2", source === "camera" ? "bg-slate-900 text-white shadow" : "text-slate-500")}
            >
              Camera
            </button>
            <button
              type="button" role="tab" aria-selected={source === "live"}
              onClick={() => { stopCamera(); setSource("live"); }}
              className={cn("rounded py-2", source === "live" ? "bg-slate-900 text-white shadow" : "text-slate-500")}
            >
              Live auto
            </button>
            <button
              type="button" role="tab" aria-selected={source === "upload"}
              onClick={() => { stopCamera(); setSource("upload"); }}
              className={cn("rounded py-2", source === "upload" ? "bg-slate-900 text-white shadow" : "text-slate-500")}
            >
              Upload
            </button>
          </div>
          {source === "live" && session && (
            <div className="mb-3">
              <LiveScanner
                token={session.token}
                opts={{ ppm, panelArea, embossed }}
                onCapture={(f) => add([f])}
              />
            </div>
          )}
          {source === "camera" && (
            <div className="mb-3 rounded-xl border border-slate-200 bg-slate-950 p-3">
              <ol className="mb-2 flex gap-2 text-[11px] font-bold">
                <li className={cn("flex-1 rounded px-2 py-1 text-center", shotStep === 1 ? "bg-white text-slate-900" : "text-slate-400")}>
                  1 · Pack + card
                </li>
                <li className={cn("flex-1 rounded px-2 py-1 text-center", shotStep === 2 ? "bg-white text-slate-900" : "text-slate-400")}>
                  2 · Label macro
                </li>
              </ol>
              <p className="mb-2 text-xs leading-relaxed text-slate-300">
                {shotStep === 1
                  ? "Lay the pack flat with a credit-card-size card beside the label — the card sets the mm scale."
                  : "Fill the frame with the declaration text, straight-on, no flash."}
              </p>
              <div className="relative overflow-hidden rounded-lg bg-black">
                {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
                <video ref={videoRef} playsInline muted className="block aspect-[4/3] w-full object-cover" />
                <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox="0 0 100 75" preserveAspectRatio="none" aria-hidden="true">
                  {shotStep === 1 ? (
                    <>
                      <rect x="6" y="52" width="22" height="14" fill="none" stroke="#38bdf8" strokeWidth="0.8" strokeDasharray="2 1.2" />
                      <rect x="20" y="12" width="60" height="40" fill="none" stroke="#4ade80" strokeWidth="0.8" />
                    </>
                  ) : (
                    <rect x="12" y="14" width="76" height="47" fill="none" stroke="#4ade80" strokeWidth="0.8" />
                  )}
                </svg>
              </div>
              {camError && <p className="mt-2 rounded bg-red-950 px-3 py-2 text-xs text-red-200">{camError}</p>}
              {insecure && !camOn && (
                <p className="mt-2 text-[11px] leading-relaxed text-slate-400">
                  On phones, the camera needs HTTPS or localhost. If blocked, open this page via a secure origin or use Upload.
                </p>
              )}
              <div className="mt-2 flex gap-2">
                {!camOn ? (
                  <Button type="button" onClick={startCamera} className="flex-1">
                    Open camera
                  </Button>
                ) : (
                  <>
                    <Button type="button" onClick={captureShot} className="flex-1">
                      {shotStep === 1 ? "Capture pack + card" : "Capture label text"}
                    </Button>
                    <Button type="button" variant="outline" onClick={stopCamera} className="border-slate-600 bg-transparent text-slate-200">
                      Close
                    </Button>
                  </>
                )}
              </div>
            </div>
          )}
          {source === "upload" && (
          <label
            htmlFor="scan-file-input"
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); add(e.dataTransfer.files); }}
            className={cn(
              "block cursor-pointer rounded-xl border-2 border-dashed p-6 text-center transition-all",
              dragOver ? "border-slate-900 bg-slate-100 shadow-inner" : "border-slate-300 bg-slate-50/50 hover:border-slate-400 hover:bg-white"
            )}
          >
            <div className="mx-auto flex max-w-sm flex-col items-center gap-3">
              <div className={cn("grid h-12 w-12 place-items-center rounded-full transition-colors", dragOver ? "bg-slate-900 text-white" : "bg-white text-slate-600 shadow-sm border border-slate-200")}>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-bold text-slate-900">
                  {files.length === 0 ? "Drop label photos here" : "Add more angles"}
                </p>
                <p className="mt-1 text-xs leading-relaxed text-slate-500">
                  Drag & drop or use the button below · JPG, PNG, WebP · up to 5 images
                </p>
              </div>
              <div className="flex flex-wrap items-center justify-center gap-2 pt-1">
                <span className="inline-flex items-center justify-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-semibold shadow-sm">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                    <line x1="12" y1="18" x2="12" y2="12" />
                    <line x1="9" y1="15" x2="12" y2="12" />
                    <line x1="15" y1="15" x2="12" y2="12" />
                  </svg>
                  Browse files
                </span>
                <span className="text-xs text-slate-400">or drop here</span>
              </div>
            </div>
            <input
              ref={inputRef}
              id="scan-file-input"
              type="file"
              accept="image/*"
              multiple
              className="sr-only"
              onChange={(e) => { add(e.target.files); e.currentTarget.value = ""; }}
            />
          </label>
          )}
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
          {rejected.length > 0 && (
            <AlertDestructive className="mt-3">
              Skipped {rejected.length === 1 ? "this file" : "these files"}:{" "}
              {rejected.join(", ")}.
            </AlertDestructive>
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
            Font height in mm = pixels ÷ PPM. Include the card in shot 1 and the app
            detects the scale itself — otherwise font rules return “not assessable”, never a pass.
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
          <label className="mt-2 flex cursor-pointer items-center gap-2 text-[13px] font-medium text-slate-700">
            <input type="checkbox" checked={attachGps} onChange={(e) => { setAttachGps(e.target.checked); setGpsNote(""); }} className="accent-slate-900" />
            Attach inspection location (GPS on the report)
          </label>
          {gpsNote && <p className="mt-1 text-xs text-amber-800">{gpsNote}</p>}
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
