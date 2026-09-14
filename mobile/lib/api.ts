import Constants from "expo-constants";

/**
 * Robust backend client for the DrishtiLM LMPC scanner.
 *
 * Mirrors web/lib/api.ts semantics:
 * - base URL is explicit (persisted in store.ts, never a hidden global)
 * - every error carries HTTP status + backend `detail` + `request_id`
 * - 401 means "session expired" — callers clear the session and route to auth
 * - /scans and /scans/merge return 202 Job in production; this client polls
 *   GET /jobs/{id} then GET /scans/{id} so screens always get a ScanDetail
 * - all fetches have timeouts via AbortController (no hanging spinners)
 * - responses are runtime-validated (backend and app evolve independently)
 */

export const DEFAULT_API_URL = "http://10.0.2.2:8000";
export const API_PREFIX = "/api/v1";
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

export type ApiCode = "network" | "timeout" | "auth" | "validation" | "server";

export class ApiError extends Error {
  status: number;
  code: ApiCode;
  requestId: string;
  constructor(status: number, message: string, code: ApiCode = "server", requestId = "") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
  get isAuth(): boolean {
    return this.status === 401 || this.code === "auth";
  }
}

/** "http://192.168.1.5:8000/" -> "http://192.168.1.5:8000" (throws ApiError on garbage). */
export function normalizeBaseUrl(raw: string): string {
  const v = (raw ?? "").trim().replace(/\/+$/, "");
  if (!/^https?:\/\/[^/\s]+(:\d+)?$/.test(v)) {
    throw new ApiError(0, "API address must look like http://192.168.1.5:8000", "validation");
  }
  return v;
}

export function apiUrlFromConfig(): string {
  const extra = Constants.expoConfig?.extra as { apiUrl?: unknown } | undefined;
  const raw = typeof extra?.apiUrl === "string" && extra.apiUrl ? extra.apiUrl : DEFAULT_API_URL;
  try {
    return normalizeBaseUrl(raw);
  } catch {
    return DEFAULT_API_URL;
  }
}

export interface Session {
  token: string;
  username: string;
}

export interface RuleCheck {
  rule_id: string;
  status: string;
  message: string;
  field: string;
  citation: string;
  citation_verified: boolean;
  observed: string | null;
  expected: string | null;
  severity: string;
  remedy: string | null;
  cause: string;
  why: string;
  next_steps: string[];
}

export interface ScanDetail {
  id: string;
  status: string;
  ocr_engine: string;
  ocr_text: string;
  ocr_confidence: number;
  font_height_mm: number | null;
  verdict: string;
  compliant: boolean;
  results: RuleCheck[];
  warnings: string[];
  product_name: string;
  brand_name: string;
  category: string;
  has_image: boolean;
  request_id: string;
  job_id: string | null;
}

export interface ScanSummary {
  id: string;
  verdict: string;
  compliant: boolean;
  status: string;
  ocr_engine: string;
  created_at: string;
  preview: string;
  product_name: string;
  brand_name: string;
  category: string;
  has_image: boolean;
}

export interface ScanJob {
  job_id: string;
  status: string;
  kind: string;
  frames_total: number;
  scan_id: string | null;
  error: string;
  request_id: string;
}

export interface ScanPreview {
  ocr_engine: string;
  ocr_text: string;
  ocr_confidence: number;
  word_count: number;
  sharpness: number | null;
  fields_count: number;
  fields_total: number;
  ready: boolean;
  ready_reason: string;
}

function parseErrorBody(raw: string): { detail: string; requestId: string } {
  try {
    const p = JSON.parse(raw) as { detail?: unknown; request_id?: unknown };
    return {
      detail: typeof p.detail === "string" && p.detail ? p.detail : "",
      requestId: typeof p.request_id === "string" ? p.request_id : "",
    };
  } catch {
    return { detail: "", requestId: "" };
  }
}

export function friendlyMessage(status: number, raw: string): { message: string; requestId: string } {
  if (status === 401) return { message: "Session expired — please sign in again.", requestId: "" };
  if (status === 413) return { message: "Photos too large — retake closer but with lower resolution.", requestId: "" };
  if (status === 422) return { message: parseErrorBody(raw).detail || "Need 2–5 photos of the same label.", requestId: "" };
  if (status === 429)
    return { message: "Too many requests — wait a minute and retry.", requestId: parseErrorBody(raw).requestId };
  const { detail, requestId } = parseErrorBody(raw);
  if (detail) return { message: detail.slice(0, 300), requestId };
  if (raw && raw.length < 300) return { message: raw, requestId };
  if (status === 0) return { message: "Cannot reach the API server. Check the address in Settings.", requestId };
  return { message: `Request failed (${status}).`, requestId };
}

async function fetchTimeout(url: string, init: RequestInit, ms: number): Promise<Response> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetch(url, { ...init, signal: ctrl.signal });
  } catch (e) {
    if (e instanceof Error && e.name === "AbortError") {
      throw new ApiError(0, `Request timed out after ${Math.round(ms / 1000)}s — retry on stable Wi-Fi.`, "timeout");
    }
    throw new ApiError(0, "Cannot reach the API server. Check the address in Settings.", "network");
  } finally {
    clearTimeout(t);
  }
}

async function throwForStatus(res: Response): Promise<never> {
  let raw = "";
  try {
    raw = await res.text();
  } catch {
    raw = "";
  }
  const { message, requestId } = friendlyMessage(res.status, raw);
  throw new ApiError(res.status, message, res.status === 401 ? "auth" : "server", requestId);
}

function asRecord(v: unknown): Record<string, unknown> {
  return typeof v === "object" && v !== null ? (v as Record<string, unknown>) : {};
}

function str(v: unknown, fb = ""): string {
  return typeof v === "string" ? v : fb;
}

function num(v: unknown, fb = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fb;
}

function bool(v: unknown, fb = false): boolean {
  return typeof v === "boolean" ? v : fb;
}

function nullableStr(v: unknown): string | null {
  return typeof v === "string" ? v : null;
}

function parseCheck(v: unknown): RuleCheck {
  const r = asRecord(v);
  return {
    rule_id: str(r.rule_id, "unknown"),
    status: str(r.status, "NOT_ASSESSABLE"),
    message: str(r.message, ""),
    field: str(r.field),
    citation: str(r.citation),
    citation_verified: bool(r.citation_verified),
    observed: nullableStr(r.observed),
    expected: nullableStr(r.expected),
    severity: str(r.severity, "info"),
    remedy: nullableStr(r.remedy),
    cause: str(r.cause),
    why: str(r.why),
    next_steps: Array.isArray(r.next_steps) ? r.next_steps.filter((x): x is string => typeof x === "string") : [],
  };
}

function parseScanDetail(v: unknown): ScanDetail {
  const r = asRecord(v);
  if (typeof r.id !== "string" || typeof r.verdict !== "string" || !Array.isArray(r.results)) {
    throw new ApiError(500, "Unexpected scan response from server.", "validation");
  }
  return {
    id: r.id,
    status: str(r.status, "pending_review"),
    ocr_engine: str(r.ocr_engine, "unknown"),
    ocr_text: str(r.ocr_text),
    ocr_confidence: num(r.ocr_confidence),
    font_height_mm: typeof r.font_height_mm === "number" ? r.font_height_mm : null,
    verdict: r.verdict,
    compliant: bool(r.compliant),
    results: (r.results as unknown[]).map(parseCheck),
    warnings: Array.isArray(r.warnings) ? r.warnings.filter((x): x is string => typeof x === "string") : [],
    product_name: str(r.product_name),
    brand_name: str(r.brand_name),
    category: str(r.category),
    has_image: bool(r.has_image),
    request_id: str(r.request_id),
    job_id: typeof r.job_id === "string" ? r.job_id : null,
  };
}

function parseJob(v: unknown): ScanJob {
  const r = asRecord(v);
  if (typeof r.job_id !== "string") throw new ApiError(500, "Unexpected job response.", "validation");
  return {
    job_id: r.job_id,
    status: str(r.status, "queued"),
    kind: str(r.kind, "merge"),
    frames_total: num(r.frames_total, 1),
    scan_id: typeof r.scan_id === "string" ? r.scan_id : null,
    error: str(r.error),
    request_id: str(r.request_id),
  };
}

async function jsonCall(
  baseUrl: string,
  path: string,
  body: unknown,
  opts: { token?: string; timeoutMs?: number; method?: string } = {},
): Promise<unknown> {
  const res = await fetchTimeout(
    `${baseUrl}${API_PREFIX}${path}`,
    {
      method: opts.method ?? "POST",
      headers: {
        "Content-Type": "application/json",
        ...(opts.token ? { Authorization: `Bearer ${opts.token}` } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    },
    opts.timeoutMs ?? 30000,
  );
  if (!res.ok) await throwForStatus(res);
  try {
    return (await res.json()) as unknown;
  } catch {
    throw new ApiError(500, "Bad response from server.", "validation");
  }
}

async function getJson(baseUrl: string, path: string, token: string, timeoutMs = 15000): Promise<unknown> {
  const res = await fetchTimeout(
    `${baseUrl}${API_PREFIX}${path}`,
    { method: "GET", headers: { Authorization: `Bearer ${token}` } },
    timeoutMs,
  );
  if (!res.ok) await throwForStatus(res);
  try {
    return (await res.json()) as unknown;
  } catch {
    throw new ApiError(500, "Bad response from server.", "validation");
  }
}

function asToken(v: unknown): string {
  const r = asRecord(v);
  if (typeof r.access_token !== "string" || !r.access_token) {
    throw new ApiError(500, "Bad auth response from server.", "validation");
  }
  return r.access_token;
}

export async function login(baseUrl: string, username: string, password: string): Promise<string> {
  return asToken(await jsonCall(baseUrl, "/auth/login", { username: username.trim(), password }));
}

export async function register(baseUrl: string, username: string, password: string): Promise<string> {
  return asToken(await jsonCall(baseUrl, "/auth/register", { username: username.trim(), password }));
}

export async function healthCheck(baseUrl: string): Promise<string> {
  const res = await fetchTimeout(`${baseUrl}${API_PREFIX}/health`, { method: "GET" }, 10000);
  if (!res.ok) await throwForStatus(res);
  return "ok";
}

export async function getJob(baseUrl: string, token: string, jobId: string): Promise<ScanJob> {
  return parseJob(await getJson(baseUrl, `/jobs/${encodeURIComponent(jobId)}`, token));
}

export async function getScan(baseUrl: string, token: string, scanId: string): Promise<ScanDetail> {
  const v = await getJson(baseUrl, `/scans/${encodeURIComponent(scanId)}`, token, 20000);
  return parseScanDetail(v);
}

export async function listScans(
  baseUrl: string,
  token: string,
  params: { q?: string; verdict?: string } = {},
): Promise<ScanSummary[]> {
  const qs = new URLSearchParams();
  if (params.q?.trim()) qs.set("q", params.q.trim());
  if (params.verdict && params.verdict !== "all") qs.set("verdict", params.verdict);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  const v = await getJson(baseUrl, `/scans${suffix}`, token, 20000);
  if (!Array.isArray(v)) throw new ApiError(500, "Unexpected history response.", "validation");
  return v.map((item) => {
    const r = asRecord(item);
    return {
      id: str(r.id),
      verdict: str(r.verdict, "INCOMPLETE"),
      compliant: bool(r.compliant),
      status: str(r.status, "pending_review"),
      ocr_engine: str(r.ocr_engine),
      created_at: str(r.created_at),
      preview: str(r.preview),
      product_name: str(r.product_name),
      brand_name: str(r.brand_name),
      category: str(r.category),
      has_image: bool(r.has_image),
    } as ScanSummary;
  });
}

export interface PollOpts {
  onTick?: (status: string, elapsedS: number) => void;
  shouldCancel?: () => boolean;
  intervalMs?: number;
  maxWaitMs?: number;
}

/** Poll a 202 job until done -> scan_id. Throws ApiError(408) on timeout, ApiError(500) on job failure. */
export async function pollJob(baseUrl: string, token: string, jobId: string, opts: PollOpts = {}): Promise<string> {
  const interval = opts.intervalMs ?? 2000;
  const maxWait = opts.maxWaitMs ?? 6 * 60 * 1000;
  const t0 = Date.now();
  for (;;) {
    if (opts.shouldCancel?.()) throw new ApiError(0, "Cancelled.", "network");
    const job = await getJob(baseUrl, token, jobId);
    const elapsedS = Math.round((Date.now() - t0) / 1000);
    opts.onTick?.(job.status, elapsedS);
    if (job.status === "done" && job.scan_id) return job.scan_id;
    if (job.status === "failed") throw new ApiError(500, job.error || "Analysis failed on server.", "server", job.request_id);
    if (Date.now() - t0 > maxWait) {
      throw new ApiError(408, "Analysis is taking too long — check History later for the result.", "timeout", job.request_id);
    }
    await new Promise((r) => setTimeout(r, interval));
  }
}

export interface UploadOpts {
  productName?: string;
  brandName?: string;
  category?: string;
  lat?: number | null;
  lon?: number | null;
  onStage?: (stage: string) => void;
  onJobTick?: (status: string, elapsedS: number) => void;
  shouldCancel?: () => boolean;
}

export function mimeForUri(uri: string): string {
  const l = uri.toLowerCase().split("?")[0];
  if (l.endsWith(".png")) return "image/png";
  if (l.endsWith(".webp")) return "image/webp";
  return "image/jpeg";
}

/**
 * Upload 1–5 angles. Single file -> POST /scans, 2+ -> POST /scans/merge.
 * Handles both 200 ScanOut (TESTING=1) and 202 JobOut (production polling).
 */
export async function uploadScans(
  baseUrl: string,
  token: string,
  uris: string[],
  opts: UploadOpts = {},
): Promise<ScanDetail> {
  if (uris.length < 1 || uris.length > 5) {
    throw new ApiError(0, "Need 1–5 photos of the same label.", "validation");
  }
  opts.onStage?.("uploading");
  const form = new FormData();
  const multi = uris.length > 1;
  uris.forEach((uri, i) => {
    const type = mimeForUri(uri);
    const ext = type === "image/png" ? "png" : type === "image/webp" ? "webp" : "jpg";
    form.append(multi ? "files" : "file", { uri, name: `angle${i + 1}.${ext}`, type } as unknown as Blob);
  });
  if (opts.productName?.trim()) form.append("product_name", opts.productName.trim());
  if (opts.brandName?.trim()) form.append("brand_name", opts.brandName.trim());
  if (opts.category?.trim()) form.append("category", opts.category.trim());
  if (opts.lat != null && opts.lon != null && Number.isFinite(opts.lat) && Number.isFinite(opts.lon)) {
    form.append("scan_lat", String(opts.lat));
    form.append("scan_lon", String(opts.lon));
  }
  form.append("is_embossed", "false");

  const path = multi ? "/scans/merge" : "/scans";
  let res: Response;
  try {
    res = await fetchTimeout(
      `${baseUrl}${API_PREFIX}${path}`,
      { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form },
      120000,
    );
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError(0, "Upload failed — is the backend reachable?", "network");
  }
  if (res.status === 202) {
    let job: ScanJob;
    try {
      job = parseJob((await res.json()) as unknown);
    } catch {
      throw new ApiError(500, "Bad job response from server.", "validation");
    }
    opts.onStage?.("queued");
    const scanId = await pollJob(baseUrl, token, job.job_id, {
      onTick: (s, e) => {
        opts.onStage?.(s);
        opts.onJobTick?.(s, e);
      },
      shouldCancel: opts.shouldCancel,
    });
    opts.onStage?.("fetching result");
    return getScan(baseUrl, token, scanId);
  }
  if (res.status === 500) {
    throw new ApiError(500, "Server hiccup while analyzing — wait 15 seconds and retry.", "server");
  }
  if (!res.ok) await throwForStatus(res);
  try {
    return parseScanDetail((await res.json()) as unknown);
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError(500, "Unexpected scan response from server.", "validation");
  }
}
