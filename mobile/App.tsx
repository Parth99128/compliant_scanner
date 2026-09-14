import { Component, useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import {
  ActivityIndicator,
  Button,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  useWindowDimensions,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import Constants from "expo-constants";
import { DeviceMotion } from "expo-sensors";
import Svg, { G, Path, Rect, Text as SvgText } from "react-native-svg";
import { Camera, useCameraDevice, useCameraPermission, usePhotoOutput } from "react-native-vision-camera";

import {
  ApiError,
  apiUrlFromConfig,
  getScan,
  healthCheck,
  listScans,
  login,
  normalizeBaseUrl,
  register,
  uploadScans,
  type ScanDetail,
  type ScanSummary,
  type Session,
} from "./lib/api";
import { clearSession, loadApiUrl, loadSession, saveApiUrl, saveSession } from "./lib/store";
import { prepareImage } from "./lib/images";

const NAVY = "#0f2544";
const TILT_LIMIT_DEG = 10;
const MIN_SHOTS = 2;
const MAX_SHOTS = 5;
const APP_VERSION = Constants.expoConfig?.version ?? "1.0.0";

/* ---------------------------------- errors --------------------------------- */

interface ErrInfo {
  message: string;
  requestId: string;
}

function toErr(e: unknown): ErrInfo {
  if (e instanceof ApiError) return { message: e.message, requestId: e.requestId };
  return { message: e instanceof Error ? e.message : "Something went wrong.", requestId: "" };
}

class ErrorBoundary extends Component<{ children: ReactNode }, { crashed: string | null }> {
  state = { crashed: null as string | null };
  static getDerivedStateFromError(e: unknown): { crashed: string } {
    return { crashed: e instanceof Error ? e.message : "App crashed." };
  }
  render(): ReactNode {
    if (this.state.crashed) {
      return (
        <View style={styles.center}>
          <Text style={styles.title}>Something broke</Text>
          <Text style={styles.hint}>{this.state.crashed}</Text>
          <Button title="Restart" color={NAVY} onPress={() => this.setState({ crashed: null })} />
        </View>
      );
    }
    return this.props.children;
  }
}

/* ----------------------------------- tilt ---------------------------------- */

function tiltFromGravity(g: { x: number | null; y: number | null; z: number | null }): number | null {
  if (g.x == null || g.y == null || g.z == null) return null;
  const horiz = Math.sqrt(g.x * g.x + g.y * g.y);
  return (Math.atan2(horiz, Math.abs(g.z)) * 180) / Math.PI;
}

function useTilt(active: boolean): { tiltDeg: number | null; level: boolean } {
  const [tiltDeg, setTiltDeg] = useState<number | null>(null);
  useEffect(() => {
    if (!active) return;
    let sub: { remove: () => void } | null = null;
    let mounted = true;
    (async () => {
      try {
        const dm = DeviceMotion as unknown as {
          setUpdateIntervalAsync?: (ms: number) => Promise<void>;
          setUpdateInterval?: (ms: number) => void;
        };
        if (typeof dm.setUpdateIntervalAsync === "function") await dm.setUpdateIntervalAsync(300);
        else dm.setUpdateInterval?.(300);
      } catch {
        /* sensor unavailable — capture stays enabled */
      }
      try {
        sub = DeviceMotion.addListener((m) => {
          const g = m.accelerationIncludingGravity;
          if (g && mounted) setTiltDeg(tiltFromGravity({ x: g.x, y: g.y, z: g.z }));
        });
      } catch {
        /* no sensor */
      }
    })();
    return () => {
      mounted = false;
      try {
        sub?.remove();
      } catch {
        /* ignore */
      }
    };
  }, [active]);
  return { tiltDeg, level: tiltDeg == null || tiltDeg <= TILT_LIMIT_DEG };
}

/* --------------------------------- overlays -------------------------------- */

function CalibrationOverlay(): React.JSX.Element {
  const { width, height } = useWindowDimensions();
  const cardW = 172;
  const cardH = (cardW * 54) / 86;
  return (
    <Svg width={width} height={height} style={StyleSheet.absoluteFill} pointerEvents="none">
      <Rect x={20} y={height - cardH - 140} width={cardW} height={cardH} fill="none" stroke="#38bdf8" strokeWidth={2} strokeDasharray="8 5" />
      <SvgText x={20} y={height - cardH - 148} fill="#38bdf8" fontSize={12}>Align card here (scale ref)</SvgText>
      <Rect x={width / 2 - 130} y={height / 2 - 190} width={260} height={200} fill="none" stroke="#4ade80" strokeWidth={2} />
      <SvgText x={width / 2 - 130} y={height / 2 - 198} fill="#4ade80" fontSize={12}>Full pack in frame</SvgText>
    </Svg>
  );
}

function MacroOverlay(): React.JSX.Element {
  const { width, height } = useWindowDimensions();
  const fw = width - 48;
  const fh = 300;
  const x = 24;
  const y = height / 2 - fh / 2;
  const L = 28;
  const corners = [
    `M ${x} ${y + L} L ${x} ${y} L ${x + L} ${y}`,
    `M ${x + fw - L} ${y} L ${x + fw} ${y} L ${x + fw} ${y + L}`,
    `M ${x + fw} ${y + fh - L} L ${x + fw} ${y + fh} L ${x + fw - L} ${y + fh}`,
    `M ${x + L} ${y + fh} L ${x} ${y + fh} L ${x} ${y + fh - L}`,
  ];
  return (
    <Svg width={width} height={height} style={StyleSheet.absoluteFill} pointerEvents="none">
      <G>
        <Path
          d={`M0 0H${width}V${height}H0Z M${x} ${y}H${x + fw}V${y + fh}H${x}Z`}
          fill="#000"
          fillOpacity={0.55}
          fillRule="evenodd"
        />
        {corners.map((d, i) => (
          <Path key={i} d={d} fill="none" stroke="#4ade80" strokeWidth={3} />
        ))}
      </G>
      <SvgText x={x} y={y - 10} fill="#4ade80" fontSize={12}>Fill the window with declaration text</SvgText>
    </Svg>
  );
}

/* ----------------------------------- auth ---------------------------------- */

function AuthScreen({
  apiUrl,
  onApiUrl,
  onDone,
}: {
  apiUrl: string;
  onApiUrl: (u: string) => void;
  onDone: (s: Session) => void;
}): React.JSX.Element {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [url, setUrl] = useState(apiUrl);
  const [err, setErr] = useState<ErrInfo | null>(null);
  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);
  const [health, setHealth] = useState("");
  const valid = username.trim().length >= 3 && password.length >= 6;

  useEffect(() => setUrl(apiUrl), [apiUrl]);

  async function applyUrl(): Promise<string | null> {
    try {
      const clean = normalizeBaseUrl(url);
      await saveApiUrl(clean);
      onApiUrl(clean);
      return clean;
    } catch (e) {
      setErr(toErr(e));
      return null;
    }
  }

  async function go(): Promise<void> {
    if (!valid) {
      setErr({ message: "Username needs 3+ characters and password 6+ characters.", requestId: "" });
      return;
    }
    setErr(null);
    setBusy(true);
    try {
      const base = (await applyUrl()) ?? apiUrl;
      const name = username.trim();
      const token = mode === "login" ? await login(base, name, password) : await register(base, name, password);
      await saveSession(token, name);
      onDone({ token, username: name });
    } catch (e) {
      setErr(toErr(e));
    } finally {
      setBusy(false);
    }
  }

  async function test(): Promise<void> {
    setTesting(true);
    setHealth("");
    try {
      const base = normalizeBaseUrl(url);
      await healthCheck(base);
      setHealth("Backend reachable.");
    } catch (e) {
      setHealth(toErr(e).message);
    } finally {
      setTesting(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.form} keyboardShouldPersistTaps="handled">
      <Text style={styles.kicker}>Legal Metrology · Packaged Commodities</Text>
      <Text style={styles.title}>DrishtiLM Scanner</Text>
      <View style={styles.tabs} accessibilityRole="tablist">
        {(["login", "register"] as const).map((m) => (
          <Pressable key={m} onPress={() => setMode(m)} accessibilityRole="tab" accessibilityLabel={m}>
            <Text style={[styles.tab, mode === m && styles.tabActive]}>{m === "login" ? "Sign in" : "Register"}</Text>
          </Pressable>
        ))}
      </View>
      <Text style={styles.label}>Username</Text>
      <TextInput
        style={styles.input}
        autoCapitalize="none"
        autoCorrect={false}
        value={username}
        onChangeText={setUsername}
        placeholder="inspector.mumbai"
        testID="username"
      />
      <Text style={styles.label}>Password</Text>
      <TextInput
        style={styles.input}
        secureTextEntry={!showPw}
        value={password}
        onChangeText={setPassword}
        placeholder="Minimum 6 characters"
        testID="password"
      />
      <Pressable onPress={() => setShowPw((v) => !v)} accessibilityLabel="toggle password visibility">
        <Text style={styles.link}>{showPw ? "Hide password" : "Show password"}</Text>
      </Pressable>
      <Text style={styles.label}>API address</Text>
      <TextInput
        style={styles.input}
        autoCapitalize="none"
        autoCorrect={false}
        value={url}
        onChangeText={setUrl}
        placeholder="http://192.168.1.5:8000"
        testID="api-url"
      />
      {testing ? <ActivityIndicator /> : <Text style={styles.hint}>{health}</Text>}
      <View style={styles.row}>
        <Button title="Test connection" onPress={() => void test()} color="#3d4759" />
      </View>
      {err ? (
        <Text style={styles.error} testID="auth-error">
          {err.message}
          {err.requestId ? `\nRef: ${err.requestId}` : ""}
        </Text>
      ) : null}
      {busy ? (
        <ActivityIndicator testID="auth-busy" />
      ) : (
        <Button
          title={mode === "login" ? "Sign in" : "Create account"}
          onPress={() => void go()}
          color={NAVY}
          accessibilityLabel={mode === "login" ? "Sign in" : "Create account"}
        />
      )}
      <Text style={styles.hint}>On-device emulator: http://10.0.2.2:8000. Physical phone: your PC&apos;s LAN IP + :8000.</Text>
    </ScrollView>
  );
}

/* ---------------------------------- camera --------------------------------- */

function CameraScreen({
  wide,
  flashOn,
  onFlash,
  onCapture,
  onClose,
}: {
  wide: boolean;
  flashOn: boolean;
  onFlash: () => void;
  onCapture: (uri: string) => void;
  onClose: () => void;
}): React.JSX.Element {
  const device = useCameraDevice("back");
  const { hasPermission, requestPermission } = useCameraPermission();
  const photoOutput = usePhotoOutput({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const { tiltDeg, level } = useTilt(true);

  useEffect(() => {
    if (!hasPermission) void requestPermission();
  }, [hasPermission, requestPermission]);

  const shoot = useCallback(async () => {
    if (!level || busy) return;
    setBusy(true);
    setErr("");
    try {
      // v5 API: capturePhoto(settings, callbacks). Prefer direct-to-file
      // (PhotoFile.filePath), fall back to in-memory Photo + save.
      const out = photoOutput as unknown as {
        capturePhotoToFile?: (s: unknown, c: unknown) => Promise<{ filePath: string }>;
        capturePhoto?: (s: unknown, c: unknown) => Promise<{
          saveToTemporaryFileAsync?: () => Promise<string>;
          dispose?: () => void;
        }>;
      };
      let raw = "";
      if (typeof out.capturePhotoToFile === "function") {
        const f = await out.capturePhotoToFile({ flashMode: flashOn ? "on" : "off" }, {});
        raw = f?.filePath ?? "";
      } else if (typeof out.capturePhoto === "function") {
        const photo = await out.capturePhoto({ flashMode: flashOn ? "on" : "off" }, {});
        try {
          raw = (await photo?.saveToTemporaryFileAsync?.()) ?? "";
        } finally {
          try {
            photo?.dispose?.();
          } catch {
            /* ignore */
          }
        }
      } else {
        throw new Error("Camera output not ready.");
      }
      if (!raw) throw new Error("Camera returned no photo.");
      onCapture(raw.startsWith("file://") ? raw : `file://${raw}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Capture failed — retry.");
    } finally {
      setBusy(false);
    }
  }, [busy, flashOn, level, onCapture, photoOutput]);

  if (!hasPermission) {
    return (
      <View style={styles.center}>
        <Text style={styles.hint}>Camera permission is required to photograph labels.</Text>
        <Button title="Grant permission" onPress={() => void requestPermission()} color={NAVY} />
        <View style={styles.gap} />
        <Button title="Back" onPress={onClose} color="#6b7689" />
      </View>
    );
  }
  if (!device) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
        <Text style={styles.hint}>Starting camera…</Text>
      </View>
    );
  }
  return (
    <View style={styles.flex}>
      <Camera style={styles.flex} device={device} isActive outputs={[photoOutput]} />
      {wide ? <CalibrationOverlay /> : <MacroOverlay />}
      <View style={styles.captureBar}>
        <Text style={styles.captureTitle}>{wide ? "Shot 1: whole pack + card" : "Close-up: declaration text"}</Text>
        {tiltDeg != null && !level ? (
          <Text style={styles.tiltWarn}>Hold level — {tiltDeg.toFixed(0)}° tilt (max {TILT_LIMIT_DEG}°)</Text>
        ) : null}
        {err ? <Text style={styles.tiltWarn}>{err}</Text> : null}
        <View style={styles.row}>
          <Button title={flashOn ? "Flash on" : "Flash off"} onPress={onFlash} color="#3d4759" />
          <Button title="Cancel" onPress={onClose} color="#6b7689" />
        </View>
        <Button
          title={busy ? "Capturing…" : level ? "Capture" : "Level the phone to capture"}
          onPress={() => void shoot()}
          disabled={!level || busy}
          color={NAVY}
          accessibilityLabel="Capture photo"
        />
      </View>
    </View>
  );
}

/* --------------------------------- result ---------------------------------- */

function verdictColor(v: string): string {
  if (v === "COMPLIANT") return "#1c6b3a";
  if (v === "INCOMPLETE") return "#8a5a00";
  return "#a4262c";
}

function ResultCard({ scan }: { scan: ScanDetail }): React.JSX.Element {
  const bad = scan.results.filter((r) => r.status !== "PASS");
  return (
    <View style={styles.card}>
      <Text style={[styles.verdict, { color: verdictColor(scan.verdict) }]} testID="verdict">
        {scan.verdict}
      </Text>
      <Text style={styles.hint}>
        {scan.ocr_engine} · {Math.round(scan.ocr_confidence)}% confidence
        {scan.font_height_mm != null ? ` · type ${scan.font_height_mm} mm` : ""}
      </Text>
      {scan.product_name ? <Text style={styles.rule}>Product: {scan.product_name}</Text> : null}
      {bad.length === 0 ? <Text style={styles.rule}>All declarations present.</Text> : null}
      {bad.slice(0, 10).map((r) => (
        <View key={r.rule_id} style={styles.finding}>
          <Text style={styles.ruleBold}>
            {r.rule_id} [{r.status}]
          </Text>
          <Text style={styles.rule}>{r.message}</Text>
          {r.remedy ? <Text style={styles.hint}>Fix: {r.remedy}</Text> : null}
        </View>
      ))}
      {scan.warnings.slice(0, 4).map((w, i) => (
        <Text key={i} style={styles.hint}>• {w}</Text>
      ))}
    </View>
  );
}

/* ----------------------------------- app ----------------------------------- */

type Tab = "scan" | "history" | "settings";
type ShotRoute = { name: "shots" } | { name: "camera"; wide: boolean } | { name: "preview"; uri: string; wide: boolean };

function InnerApp(): React.JSX.Element {
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  const [apiUrl, setApiUrl] = useState(apiUrlFromConfig());
  const [tab, setTab] = useState<Tab>("scan");
  const [route, setRoute] = useState<ShotRoute>({ name: "shots" });

  const [shots, setShots] = useState<string[]>([]);
  const [flashOn, setFlashOn] = useState(false);
  const [productName, setProductName] = useState("");
  const [brandName, setBrandName] = useState("");
  const [category, setCategory] = useState("");

  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [result, setResult] = useState<ScanDetail | null>(null);
  const [err, setErr] = useState<ErrInfo | null>(null);
  const cancelRef = useRef(false);

  const [history, setHistory] = useState<ScanSummary[]>([]);
  const [hq, setHq] = useState("");
  const [hverdict, setHverdict] = useState("all");
  const [hbusy, setHbusy] = useState(false);
  const [herr, setHerr] = useState<ErrInfo | null>(null);
  const [detail, setDetail] = useState<ScanDetail | null>(null);
  const [dbusy, setDbusy] = useState(false);

  useEffect(() => {
    (async () => {
      const [s, u] = await Promise.all([loadSession(), loadApiUrl()]);
      if (s) setSession(s);
      setApiUrl(u);
      setReady(true);
    })();
  }, []);

  async function signOut(): Promise<void> {
    await clearSession();
    setSession(null);
    setShots([]);
    setResult(null);
    setTab("scan");
    setRoute({ name: "shots" });
  }

  async function requireSession(): Promise<Session> {
    if (!session) throw new ApiError(401, "Session expired — please sign in again.", "auth");
    return session;
  }

  const loadHistory = useCallback(async () => {
    setHbusy(true);
    setHerr(null);
    try {
      const s = await requireSession();
      setHistory(await listScans(apiUrl, s.token, { q: hq, verdict: hverdict }));
    } catch (e) {
      const info = toErr(e);
      setHerr(info);
      if (e instanceof ApiError && e.isAuth) void signOut();
    } finally {
      setHbusy(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiUrl, hq, hverdict, session]);

  useEffect(() => {
    if (session && tab === "history") void loadHistory();
  }, [session, tab, loadHistory]);

  async function openDetail(id: string): Promise<void> {
    setDbusy(true);
    try {
      const s = await requireSession();
      setDetail(await getScan(apiUrl, s.token, id));
    } catch (e) {
      setHerr(toErr(e));
      if (e instanceof ApiError && e.isAuth) void signOut();
    } finally {
      setDbusy(false);
    }
  }

  async function analyze(): Promise<void> {
    setErr(null);
    setResult(null);
    if (shots.length < MIN_SHOTS) {
      setErr({ message: `Take at least ${MIN_SHOTS} photos (whole pack + close-up).`, requestId: "" });
      return;
    }
    setBusy(true);
    cancelRef.current = false;
    setStage("preparing photos");
    try {
      const s = await requireSession();
      const prepared = await Promise.all(shots.slice(0, MAX_SHOTS).map((u) => prepareImage(u)));
      const uris = prepared.map((p) => p.uri);
      const scan = await uploadScans(apiUrl, s.token, uris, {
        productName,
        brandName,
        category,
        onStage: (st) => setStage(st),
        onJobTick: (_st, e) => setElapsed(e),
        shouldCancel: () => cancelRef.current,
      });
      setResult(scan);
    } catch (e) {
      if (e instanceof ApiError && e.isAuth) {
        await signOut();
        return;
      }
      setErr(toErr(e));
    } finally {
      setBusy(false);
      setStage("");
    }
  }

  if (!ready) {
    return (
      <View style={styles.center}>
        <ActivityIndicator testID="boot" />
      </View>
    );
  }
  if (!session) {
    return (
      <View style={styles.root}>
        <StatusBar style="auto" />
        <AuthScreen apiUrl={apiUrl} onApiUrl={setApiUrl} onDone={(s) => setSession(s)} />
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <StatusBar style="auto" />
      {tab === "scan" && route.name === "camera" && (
        <CameraScreen
          wide={route.wide}
          flashOn={flashOn}
          onFlash={() => setFlashOn((v) => !v)}
          onClose={() => setRoute({ name: "shots" })}
          onCapture={(uri) => setRoute({ name: "preview", uri, wide: route.wide })}
        />
      )}
      {tab === "scan" && route.name === "preview" && (
        <View style={styles.flex}>
          <Image source={{ uri: route.uri }} style={styles.flex} resizeMode="contain" />
          <View style={styles.captureBar}>
            <Button title="Retake" onPress={() => setRoute({ name: "camera", wide: route.wide })} color="#6b7689" />
            <Button
              title="Use this shot"
              color={NAVY}
              onPress={() => {
                setShots((prev) => [...prev, route.uri].slice(-MAX_SHOTS));
                setRoute({ name: "shots" });
              }}
            />
          </View>
        </View>
      )}
      {tab === "scan" && route.name === "shots" && (
        <ScrollView contentContainerStyle={styles.form}>
          <Text style={styles.title}>New inspection</Text>
          <Text style={styles.hint}>
            {MIN_SHOTS}–{MAX_SHOTS} photos: shot 1 = whole pack + card for scale, rest = macro close-ups of the
            declaration panel (MRP, net qty, dates, care).
          </Text>
          <View style={styles.thumbs}>
            {shots.map((u, i) => (
              <View key={`${u}-${i}`}>
                <Image source={{ uri: u }} style={styles.thumb} />
                <Text style={styles.hint}>Angle {i + 1}{i === 0 ? " · scale" : " · macro"}</Text>
                <Button title="Remove" color="#a4262c" onPress={() => setShots((p) => p.filter((_, j) => j !== i))} />
              </View>
            ))}
          </View>
          <View style={styles.row}>
            <Button
              title={shots.length === 0 ? "Take shot 1 (wide)" : `Add close-up (${shots.length}/${MAX_SHOTS})`}
              color={NAVY}
              disabled={shots.length >= MAX_SHOTS}
              onPress={() => setRoute({ name: "camera", wide: shots.length === 0 })}
            />
          </View>
          <Text style={styles.label}>Product (optional)</Text>
          <TextInput style={styles.input} value={productName} onChangeText={setProductName} placeholder="Product name" />
          <TextInput style={styles.input} value={brandName} onChangeText={setBrandName} placeholder="Brand" />
          <TextInput style={styles.input} value={category} onChangeText={setCategory} placeholder="Category" />
          {err ? (
            <Text style={styles.error} testID="scan-error">
              {err.message}
              {err.requestId ? `\nRef: ${err.requestId}` : ""}
            </Text>
          ) : null}
          {busy ? (
            <View>
              <ActivityIndicator testID="scan-busy" />
              <Text style={styles.hint}>
                {stage || "working"}… {elapsed > 0 ? `${elapsed}s` : ""}
              </Text>
              <Button title="Cancel" color="#a4262c" onPress={() => { cancelRef.current = true; }} />
            </View>
          ) : (
            <Button
              title={`Analyze ${Math.max(shots.length, MIN_SHOTS)} shots`}
              color={NAVY}
              disabled={shots.length < MIN_SHOTS}
              onPress={() => void analyze()}
              accessibilityLabel="Analyze shots"
            />
          )}
          {result ? <ResultCard scan={result} /> : null}
          <View style={styles.gap} />
          <Button
            title="Clear shots"
            color="#6b7689"
            onPress={() => {
              setShots([]);
              setResult(null);
              setErr(null);
            }}
          />
        </ScrollView>
      )}
      {tab === "history" && (
        <ScrollView contentContainerStyle={styles.form}>
          <Text style={styles.title}>History</Text>
          <TextInput style={styles.input} value={hq} onChangeText={setHq} placeholder="Search product / OCR text" />
          <View style={styles.row}>
            {(["all", "COMPLIANT", "NON_COMPLIANT", "INCOMPLETE"] as const).map((v) => (
              <Pressable key={v} onPress={() => setHverdict(v)}>
                <Text style={[styles.chip, hverdict === v && styles.chipActive]}>{v === "all" ? "All" : v.slice(0, 4)}</Text>
              </Pressable>
            ))}
          </View>
          <View style={styles.row}>
            <Button title="Refresh" color={NAVY} onPress={() => void loadHistory()} />
          </View>
          {hbusy ? <ActivityIndicator /> : null}
          {herr ? <Text style={styles.error}>{herr.message}</Text> : null}
          {dbusy ? <ActivityIndicator /> : null}
          {detail ? <ResultCard scan={detail} /> : null}
          {history.map((h) => (
            <Pressable key={h.id} onPress={() => void openDetail(h.id)}>
              <View style={styles.card}>
                <Text style={[styles.ruleBold, { color: verdictColor(h.verdict) }]}>{h.verdict}</Text>
                <Text style={styles.rule}>{h.product_name || h.preview || h.id.slice(0, 8)}</Text>
                <Text style={styles.hint}>{h.created_at} · {h.ocr_engine}</Text>
              </View>
            </Pressable>
          ))}
          {history.length === 0 && !hbusy ? <Text style={styles.hint}>No scans yet.</Text> : null}
        </ScrollView>
      )}
      {tab === "settings" && (
        <SettingsScreen apiUrl={apiUrl} session={session} onApiUrl={setApiUrl} onSignOut={() => void signOut()} />
      )}
      <View style={styles.tabbar}>
        {(["scan", "history", "settings"] as const).map((t) => (
          <Pressable key={t} onPress={() => { setTab(t); setDetail(null); }} accessibilityRole="tab" accessibilityLabel={t}>
            <Text style={[styles.tabbarItem, tab === t && styles.tabbarActive]}>{t.toUpperCase()}</Text>
          </Pressable>
        ))}
      </View>
      <View style={styles.signout}>
        <Text style={styles.hint}>Signed in as {session.username} · v{APP_VERSION}</Text>
      </View>
    </View>
  );
}

function SettingsScreen({
  apiUrl,
  session,
  onApiUrl,
  onSignOut,
}: {
  apiUrl: string;
  session: Session;
  onApiUrl: (u: string) => void;
  onSignOut: () => void;
}): React.JSX.Element {
  const [url, setUrl] = useState(apiUrl);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => setUrl(apiUrl), [apiUrl]);

  async function save(): Promise<void> {
    setBusy(true);
    setMsg("");
    try {
      const clean = await saveApiUrl(url);
      onApiUrl(clean);
      await healthCheck(clean);
      setMsg("Saved — backend reachable.");
    } catch (e) {
      setMsg(toErr(e).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.form}>
      <Text style={styles.title}>Settings</Text>
      <Text style={styles.label}>API address</Text>
      <TextInput style={styles.input} autoCapitalize="none" autoCorrect={false} value={url} onChangeText={setUrl} />
      {busy ? <ActivityIndicator /> : <Button title="Save & test" color={NAVY} onPress={() => void save()} />}
      {msg ? <Text style={styles.hint}>{msg}</Text> : null}
      <Text style={styles.hint}>User: {session.username}</Text>
      <Text style={styles.hint}>App v{APP_VERSION} · backend :8000 · uploads capped at 10 MB, auto-compressed.</Text>
      <View style={styles.gap} />
      <Button title="Sign out" color="#a4262c" onPress={onSignOut} />
    </ScrollView>
  );
}

export default function App(): React.JSX.Element {
  return (
    <ErrorBoundary>
      <InnerApp />
    </ErrorBoundary>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#f4f5f7", paddingTop: 40 },
  flex: { flex: 1 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24, gap: 12 },
  form: { padding: 20, gap: 8, paddingBottom: 40 },
  kicker: { fontSize: 11, fontWeight: "700", letterSpacing: 1.2, color: "#6b7689", textTransform: "uppercase" },
  title: { fontSize: 22, fontWeight: "800", color: "#1a2333", marginBottom: 8 },
  tabs: { flexDirection: "row", marginBottom: 12, gap: 8 },
  tab: { flex: 1, textAlign: "center", padding: 10, fontWeight: "700", color: "#6b7689", borderWidth: 1, borderColor: "#dfe3ea" },
  tabActive: { backgroundColor: NAVY, color: "#fff" },
  label: { fontSize: 13, fontWeight: "700", color: "#3d4759", marginTop: 10, marginBottom: 4 },
  input: { borderWidth: 1, borderColor: "#dfe3ea", borderRadius: 8, padding: 10, fontSize: 15, backgroundColor: "#fff", marginBottom: 6 },
  error: { color: "#a4262c", fontSize: 13, marginTop: 8 },
  hint: { color: "#6b7689", fontSize: 12, marginVertical: 6 },
  link: { color: NAVY, fontSize: 13, marginTop: 4 },
  row: { flexDirection: "row", gap: 12, alignItems: "center", marginVertical: 6, flexWrap: "wrap" },
  captureBar: { position: "absolute", left: 0, right: 0, bottom: 0, padding: 20, backgroundColor: "rgba(10,15,25,0.55)", gap: 8 },
  captureTitle: { color: "#fff", fontWeight: "700", fontSize: 14 },
  tiltWarn: { color: "#ffd166", fontWeight: "700" },
  thumbs: { flexDirection: "row", gap: 12, flexWrap: "wrap", marginVertical: 8 },
  thumb: { width: 150, height: 200, borderRadius: 8, backgroundColor: "#dfe3ea" },
  card: { borderWidth: 1, borderColor: "#dfe3ea", borderRadius: 8, padding: 14, backgroundColor: "#fff", gap: 4, marginVertical: 6 },
  verdict: { fontSize: 18, fontWeight: "800" },
  rule: { fontSize: 12, color: "#3d4759", marginTop: 2 },
  ruleBold: { fontSize: 13, fontWeight: "700", color: "#1a2333" },
  finding: { borderTopWidth: 1, borderTopColor: "#eef1f5", paddingTop: 6, marginTop: 6 },
  gap: { height: 12 },
  signout: { padding: 8, alignItems: "center" },
  tabbar: { flexDirection: "row", borderTopWidth: 1, borderTopColor: "#dfe3ea", backgroundColor: "#fff" },
  tabbarItem: { flex: 1, textAlign: "center", padding: 14, fontWeight: "700", color: "#6b7689" },
  tabbarActive: { color: NAVY },
  chip: { paddingVertical: 6, paddingHorizontal: 10, borderWidth: 1, borderColor: "#dfe3ea", borderRadius: 16, color: "#3d4759", fontSize: 12 },
  chipActive: { backgroundColor: NAVY, color: "#fff" },
});
