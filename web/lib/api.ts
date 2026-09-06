import { z } from "zod";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

const TokenSchema = z.object({ access_token: z.string(), token_type: z.string().default("bearer") });
export type Token = z.infer<typeof TokenSchema>;

const ScanSummarySchema = z.object({
  id: z.string(),
  verdict: z.string(),
  compliant: z.boolean(),
  status: z.string(),
  ocr_engine: z.string(),
  created_at: z.string(),
  preview: z.string().default(""),
  product_name: z.string().default(""),
  brand_name: z.string().default(""),
  category: z.string().default(""),
  has_image: z.boolean().default(false),
});
export type ScanSummary = z.infer<typeof ScanSummarySchema>;
const ScanListSchema = z.array(ScanSummarySchema);

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function friendlyError(status: number, raw: string): string {
  // Never flash raw JSON (e.g. {"detail":"Invalid token"}) at officers:
  // sessions simply expire after an hour of scanning.
  if (status === 401) return "Session expired — please sign in again.";
  if (status === 0) return "Cannot reach the API server. Is the backend running?";
  try {
    const parsed = JSON.parse(raw) as { detail?: unknown };
    if (typeof parsed.detail === "string" && parsed.detail) return parsed.detail.slice(0, 300);
  } catch {
    // Not JSON — fall through to raw text below.
  }
  return raw.slice(0, 300) || `Request failed (${status}).`;
}

async function request<T>(path: string, schema: z.ZodType<T>, init: RequestInit = {}, token?: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(init.headers as Record<string, string> ?? {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/v1${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Cannot reach the API server. Is the backend running?");
  }
  if (!res.ok) {
    if (res.status === 401 && typeof window !== "undefined") {
      // Token expired/invalid: drop it and tell the app to send the user
      // back to sign-in (AuthProvider listens for this event).
      clearSession();
      window.dispatchEvent(new Event("lmpc:unauthorized"));
    }
    throw new ApiError(res.status, friendlyError(res.status, await res.text()));
  }
  return schema.parse(await res.json());
}

export const CredentialsSchema = z.object({
  username: z.string().trim().min(3, "Username needs at least 3 characters."),
  password: z.string().min(6, "Password needs at least 6 characters."),
  role: z.enum(["officer", "admin"]).default("officer"),
});
export type Credentials = z.infer<typeof CredentialsSchema>;

export function login(body: Credentials): Promise<Token> {
  return request("/auth/login", TokenSchema, { method: "POST", body: JSON.stringify(body) });
}

export function register(body: Credentials): Promise<Token> {
  return request("/auth/register", TokenSchema, { method: "POST", body: JSON.stringify(body) });
}

export function listScans(
  token: string,
  params: { q?: string; verdict?: string; status?: string } = {}
): Promise<ScanSummary[]> {
  const qs = new URLSearchParams();
  if (params.q) qs.set("q", params.q);
  if (params.verdict && params.verdict !== "all") qs.set("verdict", params.verdict);
  if (params.status && params.status !== "all") qs.set("status", params.status);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return request(`/scans${suffix}`, ScanListSchema, { method: "GET" }, token);
}

const CheckSchema = z.object({
  rule_id: z.string(),
  status: z.string(),
  passed: z.boolean(),
  message: z.string(),
  field: z.string().default(""),
  citation: z.string().default(""),
  citation_verified: z.boolean().default(false),
  source_ref: z.string().default(""),
  observed: z.string().nullable().default(null),
  expected: z.string().nullable().default(null),
  severity: z.string().default("info"),
  remedy: z.string().nullable().default(null),
});
export type Check = z.infer<typeof CheckSchema>;

const BoxSchema = z.object({
  text: z.string(),
  x: z.number(),
  y: z.number(),
  w: z.number(),
  h: z.number(),
  confidence: z.number(),
});
export type WordBox = z.infer<typeof BoxSchema>;

const FrameInfoSchema = z.object({
  index: z.number(),
  is_best: z.boolean().default(false),
  measured: z.boolean().default(false),
  url: z.string().default(""),
  ocr_confidence: z.number().default(0),
  word_count: z.number().default(0),
  words_added: z.number().default(0),
  boxes: z.array(BoxSchema).default([]),
  coord_w: z.number().nullable().default(null),
  coord_h: z.number().nullable().default(null),
});
export type FrameInfo = z.infer<typeof FrameInfoSchema>;
const FrameListSchema = z.array(FrameInfoSchema);

const ScanDetailSchema = z.object({
  id: z.string(),
  request_id: z.string(),
  status: z.string(),
  ocr_engine: z.string(),
  ocr_text: z.string(),
  ocr_confidence: z.number(),
  font_height_mm: z.number().nullable().default(null),
  verdict: z.string(),
  compliant: z.boolean(),
  results: z.array(CheckSchema),
  warnings: z.array(z.string()).default([]),
  boxes: z.array(BoxSchema).default([]),
  reviewed_by: z.string().nullable().default(null),
  reviewed_at: z.string().nullable().default(null),
  has_image: z.boolean().default(false),
  coord_w: z.number().nullable().default(null),
  coord_h: z.number().nullable().default(null),
  product_name: z.string().default(""),
  brand_name: z.string().default(""),
  category: z.string().default(""),
  ppm_used: z.number().nullable().default(null),
  frames: z.array(FrameInfoSchema).default([]),
  measured_index: z.number().nullable().default(null),
  scan_lat: z.number().nullable().default(null),
  scan_lon: z.number().nullable().default(null),
});
export type ScanDetail = z.infer<typeof ScanDetailSchema>;

const ExplainSchema = z.object({
  explanation: z.string(),
  provider: z.string().default(""),
  model: z.string().default(""),
  request_id: z.string(),
});

export function getScan(id: string, token: string): Promise<ScanDetail> {
  return request(`/scans/${id}`, ScanDetailSchema, { method: "GET" }, token);
}

export function listFrames(id: string, token: string): Promise<FrameInfo[]> {
  return request(`/scans/${id}/images`, FrameListSchema, { method: "GET" }, token);
}

export async function fetchBlob(path: string, token: string): Promise<Blob> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/v1${path}`, { headers: { Authorization: `Bearer ${token}` } });
  } catch {
    throw new ApiError(0, "Cannot reach the API server. Is the backend running?");
  }
  if (res.status === 409) throw new ApiError(409, "Report is not final — confirm the review first, then download.");
  if (res.status === 401 && typeof window !== "undefined") {
    clearSession();
    window.dispatchEvent(new Event("lmpc:unauthorized"));
  }
  if (!res.ok) throw new ApiError(res.status, friendlyError(res.status, await res.text()));
  return res.blob();
}

export function reviewScan(id: string, token: string, decision: "confirm" | "override", notes: string): Promise<ScanDetail> {
  return request(
    `/scans/${id}/review`,
    ScanDetailSchema,
    { method: "POST", body: JSON.stringify({ decision, notes }) },
    token
  );
}

export async function explainScan(id: string, token: string): Promise<string> {
  const r = await request(`/scans/${id}/explain`, ExplainSchema, { method: "POST", body: JSON.stringify({}) }, token);
  return r.explanation;
}

const StatsSchema = z.object({
  total: z.number(),
  by_verdict: z.record(z.string(), z.number()),
  top_failed_rules: z.array(z.tuple([z.string(), z.number()])),
  by_day: z.array(z.tuple([z.string(), z.number()])),
  recent: z.array(
    z.object({
      id: z.string(),
      verdict: z.string(),
      status: z.string(),
      product_name: z.string().default(""),
      preview: z.string().default(""),
      created_at: z.string(),
    })
  ),
});
export type StatsOverview = z.infer<typeof StatsSchema>;

export function statsOverview(token: string): Promise<StatsOverview> {
  return request("/stats/overview", StatsSchema, { method: "GET" }, token);
}

export function updateProduct(
  id: string,
  token: string,
  body: { product_name: string; brand_name: string; category: string }
): Promise<ScanDetail> {
  return request(`/scans/${id}/product`, ScanDetailSchema, { method: "PATCH", body: JSON.stringify(body) }, token);
}

export interface ScanOptions {
  ppm?: string;
  fontPx?: string;
  panelArea?: string;
  embossed?: boolean;
  lat?: number | null;
  lon?: number | null;
}

const ScanPreviewSchema = z.object({
  ocr_engine: z.string(),
  ocr_text: z.string().default(""),
  ocr_confidence: z.number().default(0),
  word_count: z.number().default(0),
  font_height_mm: z.number().nullable().default(null),
  ppm_used: z.number().nullable().default(null),
  sharpness: z.number().nullable().default(null),
  fields_found: z.record(z.string(), z.boolean()).default({}),
  fields_count: z.number().default(0),
  fields_total: z.number().default(6),
  verdict: z.string().default("INCOMPLETE"),
  compliant: z.boolean().default(false),
  ready: z.boolean().default(false),
  ready_reason: z.string().default(""),
  boxes: z.array(BoxSchema).default([]),
  coord_w: z.number().nullable().default(null),
  coord_h: z.number().nullable().default(null),
  request_id: z.string(),
});
export type ScanPreview = z.infer<typeof ScanPreviewSchema>;

export async function previewScan(frame: Blob, opts: ScanOptions, token: string): Promise<ScanPreview> {
  const fd = new FormData();
  fd.append("file", frame, "frame.jpg");
  if (opts.ppm) fd.append("ppm", opts.ppm);
  if (opts.panelArea) fd.append("panel_area_cm2", opts.panelArea);
  fd.append("is_embossed", opts.embossed ? "true" : "false");
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/v1/scans/preview`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: fd,
    });
  } catch {
    throw new ApiError(0, "Live preview failed — is the backend reachable?");
  }
  if (res.status === 401 && typeof window !== "undefined") {
    clearSession();
    window.dispatchEvent(new Event("lmpc:unauthorized"));
  }
  if (!res.ok) throw new ApiError(res.status, friendlyError(res.status, await res.text()));
  return ScanPreviewSchema.parse(await res.json());
}

export async function uploadScan(files: File[], opts: ScanOptions, token: string): Promise<ScanDetail> {
  const fd = new FormData();
  if (files.length > 1) {
    files.slice(0, 5).forEach((f) => fd.append("files", f));
  } else {
    fd.append("file", files[0]);
  }
  if (opts.ppm) fd.append("ppm", opts.ppm);
  if (opts.fontPx) fd.append("font_px", opts.fontPx);
  if (opts.panelArea) fd.append("panel_area_cm2", opts.panelArea);
  if (opts.lat != null && opts.lon != null) {
    fd.append("scan_lat", String(opts.lat));
    fd.append("scan_lon", String(opts.lon));
  }
  fd.append("is_embossed", opts.embossed ? "true" : "false");
  const path = files.length > 1 ? "/scans/merge" : "/scans";
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/v1${path}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: fd,
    });
  } catch {
    throw new ApiError(0, "Upload failed — is the backend reachable?");
  }
  if (res.status === 401 && typeof window !== "undefined") {
    clearSession();
    window.dispatchEvent(new Event("lmpc:unauthorized"));
  }
  if (!res.ok) throw new ApiError(res.status, friendlyError(res.status, await res.text()));
  return ScanDetailSchema.parse(await res.json());
}

const TOKEN_KEY = "lmpc_token";
const USER_KEY = "lmpc_user";

export function loadSession(): { token: string; username: string } | null {
  if (typeof window === "undefined") return null;
  const token = window.localStorage.getItem(TOKEN_KEY);
  const username = window.localStorage.getItem(USER_KEY);
  return token && username ? { token, username } : null;
}

export function saveSession(token: string, username: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, username);
}

export function clearSession(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}
