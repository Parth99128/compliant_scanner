import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Button,
  Image,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  useWindowDimensions,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { DeviceMotion } from "expo-sensors";
import Svg, { G, Path, Rect, Text as SvgText } from "react-native-svg";
import { Camera, useCameraDevice, useCameraPermission, usePhotoOutput } from "react-native-vision-camera";

import {
  ApiError,
  loadSession,
  login,
  logout,
  register,
  uploadMerge,
  type ScanResult,
  type Session,
} from "./lib/api";

const NAVY = "#0f2544";
const TILT_LIMIT_DEG = 10;

type Screen =
  | { name: "auth" }
  | { name: "capture"; step: 1 | 2 }
  | { name: "preview"; step: 1 | 2; uri: string }
  | { name: "review" };

function tiltFromGravity(g: { x: number | null; y: number | null; z: number | null }): number | null {
  if (g.x == null || g.y == null || g.z == null) return null;
  const horiz = Math.sqrt(g.x * g.x + g.y * g.y);
  return (Math.atan2(horiz, Math.abs(g.z)) * 180) / Math.PI;
}

function useTilt(): { tiltDeg: number | null; level: boolean } {
  const [tiltDeg, setTiltDeg] = useState<number | null>(null);
  useEffect(() => {
    DeviceMotion.setUpdateInterval(300);
    const sub = DeviceMotion.addListener((m) => {
      const g = m.accelerationIncludingGravity;
      if (g) setTiltDeg(tiltFromGravity({ x: g.x, y: g.y, z: g.z }));
    });
    return () => sub.remove();
  }, []);
  return { tiltDeg, level: tiltDeg == null || tiltDeg <= TILT_LIMIT_DEG };
}

function AuthScreen({ onDone }: { onDone: (s: Session) => void }): React.JSX.Element {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const valid = username.trim().length >= 3 && password.length >= 6;

  async function go(): Promise<void> {
    if (!valid) {
      setError("Username needs 3+ characters and password 6+ characters.");
      return;
    }
    setError("");
    setBusy(true);
    try {
      onDone(mode === "login" ? await login(username.trim(), password) : await register(username.trim(), password));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.form}>
      <Text style={styles.kicker}>Legal Metrology · Packaged Commodities</Text>
      <Text style={styles.title}>LMPC Scanner</Text>
      <View style={styles.tabs}>
        {(["login", "register"] as const).map((m) => (
          <Text key={m} onPress={() => setMode(m)} style={[styles.tab, mode === m && styles.tabActive]}>
            {m === "login" ? "Sign in" : "Register"}
          </Text>
        ))}
      </View>
      <Text style={styles.label}>Username</Text>
      <TextInput style={styles.input} autoCapitalize="none" value={username} onChangeText={setUsername} placeholder="inspector.mumbai" />
      <Text style={styles.label}>Password</Text>
      <TextInput style={styles.input} secureTextEntry value={password} onChangeText={setPassword} placeholder="Minimum 6 characters" />
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {busy ? <ActivityIndicator /> : <Button title={mode === "login" ? "Sign in" : "Create account"} onPress={go} color={NAVY} />}
    </ScrollView>
  );
}

function CalibrationOverlay(): React.JSX.Element {
  const { width, height } = useWindowDimensions();
  const cardW = 172;
  const cardH = (cardW * 54) / 86;
  return (
    <Svg width={width} height={height} style={StyleSheet.absoluteFill}>
      <Rect x={20} y={height - cardH - 120} width={cardW} height={cardH} fill="none" stroke="#38bdf8" strokeWidth={2} strokeDasharray="8 5" />
      <SvgText x={20} y={height - cardH - 128} fill="#38bdf8" fontSize={12}>Align card here (scale ref)</SvgText>
      <Rect x={width / 2 - 130} y={height / 2 - 170} width={260} height={200} fill="none" stroke="#4ade80" strokeWidth={2} />
      <SvgText x={width / 2 - 130} y={height / 2 - 178} fill="#4ade80" fontSize={12}>Full product view</SvgText>
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
    <Svg width={width} height={height} style={StyleSheet.absoluteFill}>
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

function CaptureScreen({ step: stepProp, onCapture }: { step: 1 | 2; onCapture: (uri: string) => void }): React.JSX.Element {
  const device = useCameraDevice("back");
  const { hasPermission, requestPermission } = useCameraPermission();
  const photoOutput = usePhotoOutput({});
  const [busy, setBusy] = useState(false);
  const { tiltDeg, level } = useTilt();

  useEffect(() => {
    if (!hasPermission) void requestPermission();
  }, [hasPermission, requestPermission]);

  if (!hasPermission) {
    return (
      <View style={styles.center}>
        <Text>Camera permission is required to photograph labels.</Text>
        <Button title="Grant permission" onPress={() => void requestPermission()} color={NAVY} />
      </View>
    );
  }
  if (!device) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
        <Text>Starting camera…</Text>
      </View>
    );
  }

  async function shoot(): Promise<void> {
    if (!level || busy) return;
    setBusy(true);
    try {
      const photo = await photoOutput.capturePhoto({ flashMode: "off" }, {});
      if (photo) {
        const path = await photo.saveToTemporaryFileAsync();
        onCapture(path.startsWith("file://") ? path : `file://${path}`);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.flex}>
      <Camera style={styles.flex} device={device} outputs={[photoOutput]} isActive={true} />
      {stepProp === 1 ? <CalibrationOverlay /> : <MacroOverlay />}
      <View style={styles.captureBar}>
        <Text style={styles.captureTitle}>Step {stepProp}: {stepProp === 1 ? "context (whole pack + card)" : "macro (declaration close-up)"}</Text>
        {tiltDeg != null && !level ? (
          <Text style={styles.tiltWarn}>Hold level — {tiltDeg.toFixed(0)}° tilt (max {TILT_LIMIT_DEG}°)</Text>
        ) : null}
        <Button title={busy ? "Capturing…" : level ? "Capture" : "Level the phone to capture"} onPress={shoot} disabled={!level || busy} color={NAVY} />
      </View>
    </View>
  );
}

function PreviewScreen({ uri, onRetake, onUse }: { uri: string; onRetake: () => void; onUse: () => void }): React.JSX.Element {
  return (
    <View style={styles.flex}>
      <Image source={{ uri }} style={styles.flex} resizeMode="contain" />
      <View style={styles.captureBar}>
        <Button title="Retake" onPress={onRetake} color="#6b7689" />
        <Button title="Use this shot" onPress={onUse} color={NAVY} />
      </View>
    </View>
  );
}

function verdictColor(v: string): string {
  if (v === "COMPLIANT") return "#1c6b3a";
  if (v === "INCOMPLETE") return "#8a5a00";
  return "#a4262c";
}

function ReviewScreen({ shots, session, onRestart }: { shots: string[]; session: Session; onRestart: () => void }): React.JSX.Element {
  const [result, setResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function analyze(): Promise<void> {
    setError("");
    setBusy(true);
    try {
      setResult(await uploadMerge(shots, session.token));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Analysis failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.form}>
      <Text style={styles.title}>Review shots</Text>
      <View style={styles.thumbs}>
        {shots.map((u, i) => (
          <Image key={i} source={{ uri: u }} style={styles.thumb} />
        ))}
      </View>
      <Text style={styles.hint}>Wide shot gives scale context; macro gives text. Both upload to /scans/merge as one verdict.</Text>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {busy ? (
        <ActivityIndicator />
      ) : result ? (
        <View style={styles.card}>
          <Text style={[styles.verdict, { color: verdictColor(result.verdict) }]}>{result.verdict}</Text>
          <Text style={styles.hint}>Engine {result.ocr_engine} · confidence {result.ocr_confidence}%</Text>
          {result.results
            .filter((r) => r.status !== "PASS")
            .slice(0, 8)
            .map((r) => (
              <Text key={r.rule_id} style={styles.rule}>
                {r.rule_id} [{r.status}]: {r.message}
              </Text>
            ))}
          <Text style={styles.hint}>Full detail, review and PDF live in the web dashboard.</Text>
        </View>
      ) : (
        <Button title="Analyze both shots" onPress={analyze} color={NAVY} />
      )}
      <View style={styles.gap} />
      <Button title="Start over" onPress={onRestart} color="#6b7689" />
    </ScrollView>
  );
}

export default function App(): React.JSX.Element {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [screen, setScreen] = useState<Screen>({ name: "auth" });
  const [shots, setShots] = useState<string[]>([]);

  useEffect(() => {
    loadSession().then((s) => {
      if (s) {
        setSession(s);
        setScreen({ name: "capture", step: 1 });
      }
      setReady(true);
    });
  }, []);

  if (!ready) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }
  if (!session) {
    return (
      <View style={styles.root}>
        <StatusBar style="auto" />
        <AuthScreen
          onDone={(s) => {
            setSession(s);
            setScreen({ name: "capture", step: 1 });
          }}
        />
      </View>
    );
  }

  async function signOut(): Promise<void> {
    await logout();
    setSession(null);
    setShots([]);
    setScreen({ name: "auth" });
  }

  return (
    <View style={styles.root}>
      <StatusBar style="auto" />
      {screen.name === "capture" && (
        <CaptureScreen
          step={screen.step}
          onCapture={(uri) => setScreen({ name: "preview", step: screen.step, uri })}
        />
      )}
      {screen.name === "preview" && (
        <PreviewScreen
          uri={screen.uri}
          onRetake={() => setScreen({ name: "capture", step: screen.step })}
          onUse={() => {
            const next = [...shots, screen.uri].slice(-2);
            setShots(next);
            setScreen(screen.step === 1 ? { name: "capture", step: 2 } : { name: "review" });
          }}
        />
      )}
      {screen.name === "review" && (
        <ReviewScreen shots={shots} session={session} onRestart={() => { setShots([]); setScreen({ name: "capture", step: 1 }); }} />
      )}
      <View style={styles.signout}>
        <Button title={`Sign out (${session.username})`} onPress={() => void signOut()} color="#6b7689" />
      </View>
    </View>
  );
}

const styles = {
  root: { flex: 1 as const, backgroundColor: "#f4f5f7" },
  flex: { flex: 1 as const },
  center: { flex: 1 as const, alignItems: "center" as const, justifyContent: "center" as const, gap: 12 },
  form: { padding: 24, gap: 4 },
  kicker: { fontSize: 11, fontWeight: "700" as const, letterSpacing: 1.2, color: "#6b7689", textTransform: "uppercase" as const },
  title: { fontSize: 22, fontWeight: "800" as const, color: "#1a2333", marginBottom: 12 },
  tabs: { flexDirection: "row" as const, marginBottom: 16 },
  tab: { flex: 1 as const, textAlign: "center" as const, padding: 10, fontWeight: "700" as const, color: "#6b7689", borderWidth: 1, borderColor: "#dfe3ea" },
  tabActive: { backgroundColor: NAVY, color: "#fff" },
  label: { fontSize: 13, fontWeight: "700" as const, color: "#3d4759", marginTop: 10, marginBottom: 4 },
  input: { borderWidth: 1, borderColor: "#dfe3ea", borderRadius: 8, padding: 10, fontSize: 15, backgroundColor: "#fff" },
  error: { color: "#a4262c", fontSize: 13, marginTop: 8 },
  hint: { color: "#6b7689", fontSize: 12, marginVertical: 8 },
  captureBar: { position: "absolute" as const, left: 0, right: 0, bottom: 0, padding: 20, backgroundColor: "rgba(10,15,25,0.55)", gap: 8 },
  captureTitle: { color: "#fff", fontWeight: "700" as const, fontSize: 14 },
  tiltWarn: { color: "#ffd166", fontWeight: "700" as const },
  thumbs: { flexDirection: "row" as const, gap: 10 },
  thumb: { width: 150, height: 200, borderRadius: 8, backgroundColor: "#dfe3ea" },
  card: { borderWidth: 1, borderColor: "#dfe3ea", borderRadius: 8, padding: 14, backgroundColor: "#fff", gap: 4 },
  verdict: { fontSize: 18, fontWeight: "800" as const },
  rule: { fontSize: 12, color: "#3d4759", marginTop: 4 },
  gap: { height: 12 },
  signout: { padding: 8 },
};
