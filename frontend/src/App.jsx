import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./App.css";

const API = ""; // same-origin via vite proxy / nginx

async function api(path, opts = {}) {
  const token = localStorage.getItem("token") ?? "";
  const r = await fetch(`${API}${path}`, {
    ...opts,
    headers: { ...(opts.headers || {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  const ct = r.headers.get("content-type") || "";
  return ct.includes("application/pdf") ? r.blob() : r.json();
}

/* ---------------- small building blocks ---------------- */

function Stencil() {
  return (
    <svg className="overlay-svg" viewBox="0 0 300 200" preserveAspectRatio="none">
      <rect x="10" y="140" width="86" height="54" fill="none" stroke="#38bdf8" strokeWidth="2" strokeDasharray="6 4" />
      <rect x="60" y="15" width="180" height="110" fill="none" stroke="#22c55e" strokeWidth="2" />
    </svg>
  );
}

function statusClass(s) {
  if (s === "PASS") return "green";
  if (s === "NOT_ASSESSABLE") return "amber";
  return "red"; // FAIL / NOT_FOUND
}

function VerdictBanner({ verdict, unassessed }) {
  if (verdict === "COMPLIANT")
    return (
      <div className="verdict pass">
        <div className="dot">✓</div>
        <div>
          <h2>COMPLIANT</h2>
          <p>All assessable declarations passed. No blocking violations.</p>
        </div>
      </div>
    );
  if (verdict === "INCOMPLETE")
    return (
      <div className="verdict incomplete">
        <div className="dot">!</div>
        <div>
          <h2>NEEDS MEASUREMENT — assessment incomplete</h2>
          <p>
            {unassessed} rule{unassessed === 1 ? "" : "s"} could not run (uncalibrated image).{" "}
            <strong>Unmeasured ≠ passed.</strong> Add a reference object or PPM to complete the check.
          </p>
        </div>
      </div>
    );
  return (
    <div className="verdict fail">
      <div className="dot">✕</div>
      <div>
        <h2>NON-COMPLIANT</h2>
        <p>One or more mandatory declarations failed or are missing. Review the rule cards below.</p>
      </div>
    </div>
  );
}

function RuleCard({ r }) {
  const cls = r.status === "PASS" ? "pass" : r.status === "NOT_ASSESSABLE" ? "na" : r.status === "NOT_FOUND" ? "notfound" : "fail";
  return (
    <div className={`rule ${cls}`}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span className="rid">{r.rule_id}</span>
        <span className={`pill ${statusClass(r.status)}`}>{r.status.replace("_", " ")}</span>
        {r.citation_verified ? <span className="pill green">✓ verified</span> : <span className="pill gray">unverified</span>}
      </div>
      <div className="cit">{r.citation}</div>
      <div className="msg">{r.message}</div>
      {(r.observed || r.expected) && (
        <div className="obs">
          <div>Observed: {r.observed ?? "—"}</div>
          <div>Expected: {r.expected ?? "—"}</div>
        </div>
      )}
      {r.remedy && <div className="remedy">Remedy: {r.remedy}</div>}
    </div>
  );
}

/* ---------------- auth ---------------- */

function LoginForm({ onLogin }) {
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const go = async (mode) => {
    setErr("");
    setBusy(true);
    try {
      await onLogin(u, p, mode);
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <h1>LMPC Compliance Scanner</h1>
        <p className="sub">Legal Metrology (Packaged Commodities) Rules, 2011 · SIH26034</p>
        <div className="badge-row">
          <span className="pill green">100% local CPU</span>
          <span className="pill">open-source models only</span>
          <span className="pill gray">no cloud keys</span>
        </div>
        <div className="field">
          <label>Username</label>
          <input className="input" placeholder="officer id" value={u} onChange={(e) => setU(e.target.value)} />
        </div>
        <div className="field">
          <label>Password</label>
          <input className="input" placeholder="••••••••" type="password" value={p} onChange={(e) => setP(e.target.value)} />
        </div>
        <div className="btn-row">
          <button className="btn btn-primary" disabled={busy || !u || !p} onClick={() => go("login")}>
            {busy ? <span className="spin" /> : null} Login
          </button>
          <button className="btn btn-ghost" disabled={busy || !u || !p} onClick={() => go("register")}>
            Register
          </button>
        </div>
        {err && <p className="auth-err">{err}</p>}
        <p className="footer-note">Officer accounts are JWT-secured and rate-limited. Admins can override findings; all reviews are audit-trailed.</p>
      </div>
    </div>
  );
}

/* ---------------- app ---------------- */

export default function App() {
  const [authed, setAuthed] = useState(!!localStorage.getItem("token"));
  const [user, setUser] = useState(localStorage.getItem("lmpc_user") || "");
  const [view, setView] = useState("capture");
  const [step, setStep] = useState(1);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [ppm, setPpm] = useState("");
  const [fontPx, setFontPx] = useState("");
  const [panelArea, setPanelArea] = useState("");
  const [embossed, setEmbossed] = useState(false);
  const [showBoxes, setShowBoxes] = useState(true);
  const [heatmap, setHeatmap] = useState(true);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [histFilter, setHistFilter] = useState("all");
  const [histQuery, setHistQuery] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [tiltWarn, setTiltWarn] = useState(false);
  const [notes, setNotes] = useState("");
  const [showOcr, setShowOcr] = useState(false);
  const [explanation, setExplanation] = useState("");
  const [explainBusy, setExplainBusy] = useState(false);
  const imgRef = useRef(null);
  const [scale, setScale] = useState({ x: 1, y: 1 });

  useEffect(() => {
    const onMotion = (e) => {
      const g = e.accelerationIncludingGravity;
      if (!g || g.x == null) return;
      setTiltWarn(Math.abs(g.x) > 7 || Math.abs(g.y) > 7);
    };
    window.addEventListener("devicemotion", onMotion);
    return () => window.removeEventListener("devicemotion", onMotion);
  }, []);

  useEffect(() => {
    const img = imgRef.current;
    if (!img || !preview) return;
    const upd = () => {
      if (!img.naturalWidth) return;
      setScale({ x: img.clientWidth / img.naturalWidth, y: img.clientHeight / img.naturalHeight });
    };
    upd();
    window.addEventListener("resize", upd);
    return () => window.removeEventListener("resize", upd);
  }, [preview, result]);

  const login = useCallback(async (u, p, mode) => {
    const r = await api(`/api/v1/auth/${mode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: u, password: p }),
    });
    localStorage.setItem("token", r.access_token);
    localStorage.setItem("lmpc_user", u);
    setUser(u);
    setAuthed(true);
  }, []);

  const logout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("lmpc_user");
    setUser("");
    setAuthed(false);
    setResult(null);
  };

  const loadHistory = useCallback(async () => {
    try {
      setHistory(await api("/api/v1/scans"));
    } catch (e) {
      setError(String(e.message || e));
    }
  }, []);

  useEffect(() => {
    if (authed && view === "history") loadHistory();
  }, [authed, view, loadHistory]);

  const stats = useMemo(() => {
    const total = history.length;
    const ok = history.filter((s) => s.verdict === "COMPLIANT").length;
    const bad = history.filter((s) => s.verdict === "NON_COMPLIANT").length;
    const inc = history.filter((s) => s.verdict === "INCOMPLETE").length;
    return { total, ok, bad, inc };
  }, [history]);

  const onFile = (f) => {
    setFile(f || null);
    setPreview(f ? URL.createObjectURL(f) : "");
    setResult(null);
    setError("");
  };

  const scan = async () => {
    if (!file) return;
    setError("");
    setBusy(true);
    const fd = new FormData();
    fd.append("file", file);
    if (ppm) fd.append("ppm", ppm);
    if (fontPx) fd.append("font_px", fontPx);
    if (panelArea) fd.append("panel_area_cm2", panelArea);
    fd.append("is_embossed", embossed ? "true" : "false");
    try {
      const r = await api("/api/v1/scans", { method: "POST", body: fd });
      setResult(r);
      if (step === 1) setStep(2);
      loadHistory();
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  const reviewScan = async (id, decision) => {
    setError("");
    try {
      if (decision === "override" && !notes.trim()) {
        setError("Override requires a written justification (audit trail).");
        return;
      }
      const r = await api(`/api/v1/scans/${id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, notes: notes || "verified on screen" }),
      });
      setResult((prev) => (prev && prev.id === id ? { ...prev, status: r.status, reviewed_by: r.reviewed_by } : prev));
      setNotes("");
      loadHistory();
    } catch (e) {
      setError(String(e.message || e));
    }
  };

  const explainScan = async (id) => {
    setError("");
    setExplanation("");
    setExplainBusy(true);
    try {
      const r = await api(`/api/v1/scans/${id}/explain`, { method: "POST" });
      setExplanation(r.explanation);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setExplainBusy(false);
    }
  };

  const downloadReport = async (id) => {
    const token = localStorage.getItem("token") ?? "";
    const r = await fetch(`${API}/api/v1/scans/${id}/report`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (r.status === 409) {
      setError("Report not final — confirm the review first, then download.");
      return;
    }
    if (!r.ok) {
      setError(`Report failed: ${r.status}`);
      return;
    }
    const blob = await r.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `scan-${id}.pdf`;
    a.click();
  };

  if (!authed) return <LoginForm onLogin={login} />;

  const unassessed = result?.results?.filter((r) => r.status === "NOT_ASSESSABLE").length ?? 0;
  const lowConf = result && result.ocr_confidence != null && result.ocr_confidence < 60;
  const filtered = history.filter((s) => {
    if (histFilter !== "all") {
      if (histFilter === "pending" || histFilter === "final") {
        if (s.status !== histFilter) return false;
      } else if (s.verdict !== histFilter) return false;
    }
    if (histQuery && !`${s.id} ${s.verdict} ${s.status} ${s.ocr_engine}`.toLowerCase().includes(histQuery.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">⚖</div>
          <div>
            <h2>LMPC Scanner</h2>
            <small>SIH26034 · LOCAL CPU</small>
          </div>
        </div>
        <button className={`nav-btn ${view === "capture" ? "active" : ""}`} onClick={() => setView("capture")}>◉ Capture &amp; Analyze</button>
        <button className={`nav-btn ${view === "history" ? "active" : ""}`} onClick={() => setView("history")}>▤ Scan History</button>
        <div className="side-foot">
          Tesseract OCR (CPU) · regex + spaCy NER · deterministic Rule 7 tables verified vs gazette PDF. No cloud calls.
        </div>
      </aside>

      <div className="main">
        <div className="topbar">
          <h1>{view === "capture" ? "Smart Capture & Compliance Analysis" : "Scan History & Audit Trail"}</h1>
          <div className="spacer" />
          <span className="user-chip"><span className="avatar">{(user || "?")[0].toUpperCase()}</span>{user}</span>
          <button className="btn btn-ghost" onClick={logout}>Logout</button>
        </div>

        <div className="content">
          {error && <div className="alert bad" role="alert">{error}</div>}
          {tiltWarn && view === "capture" && (
            <div className="alert warn">⚠ Phone tilted — perspective skew may hurt OCR. Straighten the device before capture.</div>
          )}

          {view === "capture" && (
            <div className="stack">
              <div className="stat-grid">
                <div className="stat"><div className="k">Session scans</div><div className="v">{stats.total}</div></div>
                <div className="stat"><div className="k">Compliant</div><div className="v green">{stats.ok}</div></div>
                <div className="stat"><div className="k">Non-compliant</div><div className="v red">{stats.bad}</div></div>
                <div className="stat"><div className="k">Incomplete</div><div className="v amber">{stats.inc}</div></div>
              </div>

              <div className="stepper">
                <div className={`step ${step === 1 ? "active" : "done"}`}><span className="n">{step > 1 ? "✓" : "1"}</span>Step 1 · Full product view (context)</div>
                <div className={`step ${step === 2 ? "active" : ""}`}><span className="n">2</span>Step 2 · Close-up label (macro)</div>
              </div>

              <div className="grid-2">
                <div className="card">
                  <h3>📷 Label capture</h3>
                  <p className="hint">{step === 1 ? "Frame the whole package with the card stencil for scale." : "Move close — fill the green frame with declaration text."}</p>
                  <div
                    className={`dropzone ${dragOver ? "over" : ""}`}
                    onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={(e) => { e.preventDefault(); setDragOver(false); if (e.dataTransfer.files?.[0]) onFile(e.dataTransfer.files[0]); }}
                  >
                    <div className="preview-frame">
                      {preview ? (
                        <>
                          <img ref={imgRef} src={preview} alt="label preview" />
                          <Stencil />
                          {showBoxes && result?.boxes && (
                            <svg className="overlay-svg" viewBox={`0 0 ${imgRef.current?.naturalWidth || 300} ${imgRef.current?.naturalHeight || 200}`} preserveAspectRatio="none">
                              {result.boxes.slice(0, 300).map((b, i) => (
                                <rect key={i} x={b.x} y={b.y} width={b.w} height={b.h} fill="none"
                                  stroke={!heatmap ? "#22c55e" : b.confidence >= 60 ? "#22c55e" : "#ef4444"} strokeWidth="2" />
                              ))}
                            </svg>
                          )}
                        </>
                      ) : (
                        <div className="preview-empty">Drag &amp; drop a label photo here<br />or choose a file below</div>
                      )}
                    </div>
                  </div>
                  <div className="btn-row" style={{ marginTop: 12 }}>
                    <input type="file" accept="image/*" capture="environment" onChange={(e) => onFile(e.target.files?.[0])} />
                  </div>
                  <div className="toggle-row">
                    <label><input type="checkbox" checked={showBoxes} onChange={(e) => setShowBoxes(e.target.checked)} /> OCR boxes</label>
                    <label><input type="checkbox" checked={heatmap} onChange={(e) => setHeatmap(e.target.checked)} /> confidence heatmap (red &lt; 60%)</label>
                  </div>
                  {step === 2 && <div className="btn-row" style={{ marginTop: 10 }}><button className="btn btn-ghost" onClick={() => { setStep(1); setResult(null); }}>‹ Back to context</button></div>}
                </div>

                <div className="card">
                  <h3>📐 Spatial calibration (Rule 7)</h3>
                  <p className="hint">Font height (mm) = pixels ÷ PPM. Without calibration, font rules return NOT_ASSESSABLE — never a pass.</p>
                  <div className="calib-grid">
                    <div className="field"><label>PPM (px/mm)</label><input className="input" placeholder="auto-detect" value={ppm} onChange={(e) => setPpm(e.target.value)} /></div>
                    <div className="field"><label>Glyph px (override)</label><input className="input" placeholder="median" value={fontPx} onChange={(e) => setFontPx(e.target.value)} /></div>
                    <div className="field"><label>Panel area cm²</label><input className="input" placeholder="Table-II" value={panelArea} onChange={(e) => setPanelArea(e.target.value)} /></div>
                  </div>
                  <div className="toggle-row">
                    <label><input type="checkbox" checked={embossed} onChange={(e) => setEmbossed(e.target.checked)} /> Blown / molded / embossed (higher minima)</label>
                  </div>
                  <div className="btn-row" style={{ marginTop: 14 }}>
                    <button className="btn btn-primary" disabled={!file || busy} onClick={scan}>
                      {busy ? <><span className="spin" /> Analyzing…</> : "⚡ Scan label"}
                    </button>
                  </div>
                  <div className="alert info">Pipeline: OpenCV enhance → Tesseract CPU → regex/spaCy extract → deterministic rule engine. Avg target &lt; 5 s/image.</div>
                </div>
              </div>

              {result && (
                <>
                  <VerdictBanner verdict={result.verdict} unassessed={unassessed} />
                  <div className="grid-3">
                    <div className="card">
                      <h3>🤖 OCR insight</h3>
                      <p className="hint">Engine: {result.ocr_engine} · boxes: {result.boxes?.length ?? 0} · font: {result.font_height_mm ?? "—"} mm</p>
                      <div className="kv">
                        <dt>Confidence</dt><dd>{result.ocr_confidence}%</dd>
                      </div>
                      <div className="meter" style={{ marginTop: 6 }}><span style={{ width: `${Math.min(100, result.ocr_confidence || 0)}%` }} /></div>
                      {lowConf && <div className="alert warn">Low OCR confidence (&lt; 60%) — label may be illegible; verify on the physical package.</div>}
                      {result.warnings?.map((w, i) => <div key={i} className="alert warn">⚠ {w}</div>)}
                      <div className="btn-row" style={{ marginTop: 10 }}>
                        <button className="btn btn-ghost" onClick={() => setShowOcr((v) => !v)}>{showOcr ? "Hide OCR text" : "Show OCR text"}</button>
                      </div>
                      {showOcr && <div className="alert" style={{ whiteSpace: "pre-wrap" }}>{result.ocr_text || "(empty)"}</div>}
                    </div>
                    <div className="card">
                      <h3>🧾 Review gate</h3>
                      <p className="hint">Status: <strong>{result.status}</strong>{result.reviewed_by ? ` · by ${result.reviewed_by}` : ""}</p>
                      <div className="field"><label>Review notes {` (required for override)`}</label>
                        <textarea className="textarea" rows={3} placeholder="verified on screen…" value={notes} onChange={(e) => setNotes(e.target.value)} />
                      </div>
                      {result.status !== "final" ? (
                        <div className="btn-row">
                          <button className="btn btn-ok" onClick={() => reviewScan(result.id, "confirm")}>Confirm &amp; finalize</button>
                          <button className="btn btn-danger" onClick={() => reviewScan(result.id, "override")}>Override (admin)</button>
                        </div>
                      ) : (
                        <div className="alert ok">Finalized{result.reviewed_by ? ` by ${result.reviewed_by}` : ""}. Report is exportable.</div>
                      )}
                    </div>
                    <div className="card">
                      <h3>📄 Report</h3>
                      <p className="hint">Printable PDF compliance summary (Rule 7 tables + findings + audit trail).</p>
                      <div className="btn-row">
                        <button className="btn btn-primary" onClick={() => downloadReport(result.id)}>Download PDF</button>
                        <button className="btn btn-ghost" disabled={explainBusy} onClick={() => explainScan(result.id)}>
                          {explainBusy ? <><span className="spin" style={{ borderTopColor: "var(--brand-700)" }} /> Explaining…</> : "✨ AI explain"}
                        </button>
                      </div>
                      {explanation && <div className="alert info" style={{ whiteSpace: "pre-wrap" }}>{explanation}</div>}
                      <p className="footer-note">Exports unlock only after review (pending_review → final). AI explanations need a server-side Gemini key; the pipeline itself never does.</p>
                    </div>
                  </div>
                  <div className="card">
                    <h3>📏 Rule findings ({result.results?.length ?? 0})</h3>
                    <p className="hint">Amber NOT_ASSESSABLE cards need measurement — they are never passes. ✓ = text verified vs gazette PDF.</p>
                    <div className="rule-grid">
                      {(result.results || []).map((r) => <RuleCard key={r.rule_id} r={r} />)}
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {view === "history" && (
            <div className="stack">
              <div className="stat-grid">
                <div className="stat"><div className="k">Total</div><div className="v">{stats.total}</div></div>
                <div className="stat"><div className="k">Compliant</div><div className="v green">{stats.ok}</div></div>
                <div className="stat"><div className="k">Non-compliant</div><div className="v red">{stats.bad}</div></div>
                <div className="stat"><div className="k">Incomplete</div><div className="v amber">{stats.inc}</div></div>
              </div>
              <div className="card">
                <div className="toolbar">
                  <input className="input" placeholder="Search id / verdict / engine…" value={histQuery} onChange={(e) => setHistQuery(e.target.value)} style={{ minWidth: 220 }} />
                  {["all", "COMPLIANT", "NON_COMPLIANT", "INCOMPLETE", "pending", "final"].map((f) => (
                    <button key={f} className={`chip-btn ${histFilter === f ? "active" : ""}`} onClick={() => setHistFilter(f)}>{f}</button>
                  ))}
                  <div className="spacer" style={{ flex: 1 }} />
                  <button className="btn btn-ghost" onClick={loadHistory}>↻ Refresh</button>
                </div>
                <div className="table-wrap">
                  <table className="data">
                    <thead><tr><th>ID</th><th>Verdict</th><th>Review</th><th>Engine</th><th>Created</th><th>Report</th></tr></thead>
                    <tbody>
                      {filtered.map((s) => (
                        <tr key={s.id}>
                          <td><code>{s.id}</code></td>
                          <td><span className={`pill ${s.verdict === "COMPLIANT" ? "green" : s.verdict === "INCOMPLETE" ? "amber" : "red"}`}>{s.verdict}</span></td>
                          <td>{s.status}</td>
                          <td>{s.ocr_engine}</td>
                          <td>{s.created_at}</td>
                          <td><button className="btn btn-ghost" onClick={() => downloadReport(s.id)}>PDF</button></td>
                        </tr>
                      ))}
                      {filtered.length === 0 && <tr><td colSpan={6} style={{ textAlign: "center", color: "var(--muted)" }}>No scans match.</td></tr>}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          <p className="footer-note">
            Citation honesty: Rule 7 checks are verified vs <code>docs/legal-source/LMPC-Rules-2011_WB-mirror.pdf</code> (pp. 8–9). All Rule 6 presence/format
            citations are transcribed and unverified — confirm with legal before enforcement use. Runs 100% on local CPU with open-source models only.
          </p>
        </div>
      </div>
    </div>
  );
}
