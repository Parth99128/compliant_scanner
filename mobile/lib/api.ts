import Constants from "expo-constants";
import * as SecureStore from "expo-secure-store";

export const API_URL: string =
  (Constants.expoConfig?.extra as { apiUrl?: string } | undefined)?.apiUrl ??
  "http://10.0.2.2:8001";
// NOTE: Android emulator reaches the dev PC via 10.0.2.2. On a physical
// device on the same Wi-Fi, set extra.apiUrl in app.json to the PC's LAN IP.

const TOKEN_KEY = "lmpc_token";
const USER_KEY = "lmpc_user";

export interface Session {
  token: string;
  username: string;
}

export interface RuleResult {
  rule_id: string;
  status: string;
  message: string;
  citation: string;
  citation_verified: boolean;
  observed: string | null;
  expected: string | null;
  remedy: string | null;
}

export interface ScanResult {
  id: string;
  verdict: string;
  ocr_engine: string;
  ocr_confidence: number;
  results: RuleResult[];
  warnings: string[];
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function jsonCall(path: string, body: unknown, token?: string): Promise<unknown> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Cannot reach the API server. Check the endpoint in app settings.");
  }
  if (!res.ok) throw new ApiError(res.status, (await res.text()).slice(0, 300));
  return res.json() as Promise<unknown>;
}

function asToken(json: unknown): string {
  const rec = json as { access_token?: unknown };
  if (typeof rec.access_token !== "string") throw new ApiError(500, "Bad auth response.");
  return rec.access_token;
}

export async function login(username: string, password: string): Promise<Session> {
  const token = asToken(await jsonCall("/auth/login", { username, password }));
  await SecureStore.setItemAsync(TOKEN_KEY, token);
  await SecureStore.setItemAsync(USER_KEY, username);
  return { token, username };
}

export async function register(username: string, password: string): Promise<Session> {
  const token = asToken(await jsonCall("/auth/register", { username, password }));
  await SecureStore.setItemAsync(TOKEN_KEY, token);
  await SecureStore.setItemAsync(USER_KEY, username);
  return { token, username };
}

export async function logout(): Promise<void> {
  await SecureStore.deleteItemAsync(TOKEN_KEY);
  await SecureStore.deleteItemAsync(USER_KEY);
}

export async function loadSession(): Promise<Session | null> {
  const token = await SecureStore.getItemAsync(TOKEN_KEY);
  const username = await SecureStore.getItemAsync(USER_KEY);
  return token && username ? { token, username } : null;
}

export async function uploadMerge(uris: string[], token: string): Promise<ScanResult> {
  const form = new FormData();
  uris.forEach((uri, i) => {
    form.append("files", { uri, name: `angle${i + 1}.jpg`, type: "image/jpeg" } as unknown as Blob);
  });
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1/scans/merge`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });
  } catch {
    throw new ApiError(0, "Upload failed — is the backend reachable?");
  }
  if (!res.ok) throw new ApiError(res.status, (await res.text()).slice(0, 300));
  const json = (await res.json()) as ScanResult;
  if (typeof json.verdict !== "string" || !Array.isArray(json.results)) {
    throw new ApiError(500, "Unexpected scan response.");
  }
  return json;
}
