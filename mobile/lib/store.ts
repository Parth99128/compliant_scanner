import * as SecureStore from "expo-secure-store";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { DEFAULT_API_URL, normalizeBaseUrl, type Session } from "./api";

const TOKEN_KEY = "lmpc_token_v1";
const USER_KEY = "lmpc_user_v1";
const API_URL_KEY = "lmpc_api_url_v1";

/** SecureStore throws on devices without a lock screen / keystore — fall back, never crash. */
async function secureGet(key: string): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(key);
  } catch {
    try {
      return await AsyncStorage.getItem(key);
    } catch {
      return null;
    }
  }
}

async function secureSet(key: string, value: string): Promise<void> {
  try {
    await SecureStore.setItemAsync(key, value);
    return;
  } catch {
    await AsyncStorage.setItem(key, value);
  }
}

async function secureDel(key: string): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(key);
  } catch {
    /* ignore */
  }
  try {
    await AsyncStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

export async function loadSession(): Promise<Session | null> {
  const [token, username] = await Promise.all([secureGet(TOKEN_KEY), secureGet(USER_KEY)]);
  if (token && username) return { token, username };
  return null;
}

export async function saveSession(token: string, username: string): Promise<void> {
  await Promise.all([secureSet(TOKEN_KEY, token), secureSet(USER_KEY, username)]);
}

export async function clearSession(): Promise<void> {
  await Promise.all([secureDel(TOKEN_KEY), secureDel(USER_KEY)]);
}

export async function loadApiUrl(): Promise<string> {
  try {
    const raw = await AsyncStorage.getItem(API_URL_KEY);
    if (raw && raw.trim()) return normalizeBaseUrl(raw);
  } catch {
    /* fall through to default */
  }
  return DEFAULT_API_URL;
}

export async function saveApiUrl(raw: string): Promise<string> {
  const clean = normalizeBaseUrl(raw);
  try {
    await AsyncStorage.setItem(API_URL_KEY, clean);
  } catch {
    /* storage failure must not block scanning */
  }
  return clean;
}
