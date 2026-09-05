"use client";

import * as React from "react";

import { AlertInfo } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toaster";
import { ApiError, previewScan, type ScanOptions, type ScanPreview } from "@/lib/api";
import { cn } from "@/lib/utils";

const FIELD_LABELS: Array<[string, string]> = [
  ["generic", "Product name"],
  ["manufacturer", "Maker + address"],
  ["net_qty", "Net quantity"],
  ["mrp", "MRP"],
  ["mfg_date", "Mfg date"],
  ["care", "Care contact"],
];

interface LiveScannerProps {
  token: string;
  opts: ScanOptions;
  onCapture: (file: File) => void;
}

export function LiveScanner({ token, opts, onCapture }: LiveScannerProps): React.JSX.Element {
  const { notifyError } = useToast();
  const videoRef = React.useRef<HTMLVideoElement>(null);
  const streamRef = React.useRef<MediaStream | null>(null);
  const busyRef = React.useRef(false);
  const stableRef = React.useRef(0);
  const lastTextRef = React.useRef("");
  const [camOn, setCamOn] = React.useState(false);
  const [camError, setCamError] = React.useState("");
  const [live, setLive] = React.useState(true);
  const [auto, setAuto] = React.useState(true);
  const [preview, setPreview] = React.useState<ScanPreview | null>(null);
  const [countdown, setCountdown] = React.useState(0);
  const optsRef = React.useRef(opts);
  React.useEffect(() => {
    optsRef.current = opts;
  }, [opts]);

  const insecure = typeof window !== "undefined" && window.isSecureContext === false;
  const cameraSupported =
    typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia;

  function stop(): void {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setCamOn(false);
    setLive(false);
  }

  React.useEffect(() => stop, []);

  async function start(): Promise<void> {
    setCamError("");
    if (!cameraSupported) {
      setCamError("This browser cannot open the camera here. Use Upload instead.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCamOn(true);
      setLive(true);
    } catch {
      setCamError(
        insecure
          ? "Camera is blocked on plain-HTTP. Open via localhost/HTTPS or use Upload."
          : "Camera unavailable — check permission, or use Upload instead."
      );
    }
  }

  function grabFrameBlob(maxW = 640): Promise<Blob | null> {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return Promise.resolve(null);
    const scale = Math.min(1, maxW / video.videoWidth);
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);
    return new Promise((resolve) => canvas.toBlob((b) => resolve(b), "image/jpeg", 0.7));
  }

  function grabFullRes(): void {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0);
    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        onCapture(new File([blob], `live-capture-${Date.now()}.jpg`, { type: "image/jpeg" }));
      },
      "image/jpeg",
      0.92
    );
  }

  // Live loop: sample a small viewfinder frame every ~2s for text + size calc.
  React.useEffect(() => {
    if (!camOn || !live) return;
    let cancelled = false;
    const timer = window.setInterval(async () => {
      if (busyRef.current || cancelled) return;
      const frame = await grabFrameBlob();
      if (!frame || cancelled) return;
      busyRef.current = true;
      try {
        const p = await previewScan(frame, optsRef.current, token);
        if (cancelled) return;
        setPreview(p);
        // Stability: same word-count + same leading text as last frame.
        const key = `${p.word_count}:${p.ocr_text.slice(0, 120)}`;
        stableRef.current = key === lastTextRef.current ? stableRef.current + 1 : 0;
        lastTextRef.current = key;
        // Auto-capture: all text detected + measured + stable twice in a row.
        if (auto && p.ready && stableRef.current >= 1) {
          setCountdown(2);
          setLive(false);
          let n = 2;
          const cd = window.setInterval(() => {
            n -= 1;
            setCountdown(n);
            if (n <= 0) {
              window.clearInterval(cd);
              grabFullRes();
            }
          }, 500);
        }
      } catch (e) {
        if (e instanceof ApiError && e.status === 429) {
          setLive(false);
          notifyError(e, "Live preview rate-limited — paused. Resume to continue.");
        }
        // Transient frame errors stay silent; the next tick retries.
      } finally {
        busyRef.current = false;
      }
    }, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [camOn, live, auto, token]);

  const fields = preview?.fields_found ?? {};
  const sizeText =
    preview == null
      ? "Point at the label…"
      : preview.font_height_mm != null
        ? `${preview.font_height_mm} mm${preview.ppm_used != null ? ` @ ${preview.ppm_used.toFixed(1)} px/mm` : ""}`
        : "Size unmeasured — include the card in frame";

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-950 p-3">
      <div className="relative overflow-hidden rounded-lg bg-black">
        {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
        <video ref={videoRef} playsInline muted className="block aspect-[4/3] w-full object-cover" />
        {preview && preview.boxes.length > 0 && preview.coord_w && preview.coord_h && (
          <svg
            className="pointer-events-none absolute inset-0 h-full w-full"
            viewBox={`0 0 ${preview.coord_w} ${preview.coord_h}`}
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            {preview.boxes.slice(0, 100).map((b, i) => (
              <rect
                key={i}
                x={b.x}
                y={b.y}
                width={b.w}
                height={b.h}
                fill="none"
                stroke={b.confidence >= 60 ? "#4ade80" : "#f87171"}
                strokeWidth={Math.max(preview.coord_w ?? 640, preview.coord_h ?? 480) / 400}
              />
            ))}
          </svg>
        )}
        {!camOn && (
          <div className="absolute inset-0 grid place-items-center bg-slate-900/80 p-6 text-center">
            <div>
              <p className="text-sm font-bold text-white">Live detection</p>
              <p className="mx-auto mt-1 max-w-xs text-xs leading-relaxed text-slate-300">
                Streams viewfinder frames for text + size calc. Auto-captures at full
                resolution once every declaration reads clearly.
              </p>
            </div>
          </div>
        )}
      </div>

      {camError && <p className="mt-2 rounded bg-red-950 px-3 py-2 text-xs text-red-200">{camError}</p>}

      <div className="mt-2 flex gap-2">
        {!camOn ? (
          <Button type="button" onClick={start} className="flex-1">
            Start live detection
          </Button>
        ) : (
          <>
            <Button
              type="button"
              variant="outline"
              onClick={() => (live ? setLive(false) : setLive(true))}
              className="border-slate-600 bg-transparent text-slate-200"
            >
              {live ? "Pause" : "Resume"}
            </Button>
            <Button type="button" onClick={grabFullRes} className="flex-1">
              Capture now
            </Button>
            <Button type="button" variant="outline" onClick={stop} className="border-slate-600 bg-transparent text-slate-200">
              Close
            </Button>
          </>
        )}
      </div>

      <label className="mt-2 flex cursor-pointer items-center gap-2 text-xs font-semibold text-slate-300">
        <input
          type="checkbox"
          checked={auto}
          onChange={(e) => setAuto(e.target.checked)}
          className="accent-emerald-400"
        />
        Auto-capture when all text is detected
      </label>

      {camOn && (
        <div className="mt-2 rounded-lg bg-white p-3 text-slate-900">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="text-xs font-bold">
              {preview ? `${preview.fields_count}/${preview.fields_total} declarations` : "Detecting…"}
            </p>
            <p className="text-xs font-semibold text-slate-600">{sizeText}</p>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full rounded-full bg-emerald-600 transition-all"
              style={{ width: `${((preview?.fields_count ?? 0) / (preview?.fields_total ?? 6)) * 100}%` }}
            />
          </div>
          <ul className="mt-2 grid grid-cols-2 gap-1">
            {FIELD_LABELS.map(([key, label]) => (
              <li
                key={key}
                className={cn(
                  "flex items-center gap-1.5 rounded px-2 py-1 text-xs font-semibold",
                  fields[key] ? "bg-green-50 text-green-800" : "bg-slate-100 text-slate-500"
                )}
              >
                <span>{fields[key] ? "✓" : "○"}</span> {label}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-slate-500">
            {countdown > 0
              ? `All text detected — capturing in ${countdown}… hold steady!`
              : (preview?.ready_reason ?? "Move closer, flatten the pack, avoid glare.")}
          </p>
          {preview != null && (
            <p className="mt-1 text-[11px] tabular-nums text-slate-400">
              conf {preview.ocr_confidence}% · {preview.word_count} words
              {preview.sharpness != null ? ` · focus ${preview.sharpness}` : ""} · {preview.verdict}
            </p>
          )}
          {!live && countdown === 0 && (
            <AlertInfo className="mt-2">Paused — resume to keep detecting, or capture manually.</AlertInfo>
          )}
        </div>
      )}
    </div>
  );
}
