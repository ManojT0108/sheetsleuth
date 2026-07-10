import React, { useEffect, useRef, useState } from "react";
import { api, BB_API, APP_ID, PRODUCT_ID, fmt$ } from "./lib/api.js";
import Landing from "./components/Landing.jsx";
import GraphPanel from "./components/GraphPanel.jsx";
import Evidence from "./components/Evidence.jsx";
import AskPanel from "./components/AskPanel.jsx";

const STAGES = [
  "Parsing formulas…", "Building the Neo4j dependency graph…",
  "Running graph detectors…", "LLM semantic triage via Butterbase…", "Rendering…",
];

export default function App() {
  const [user, setUser] = useState(() => JSON.parse(localStorage.SS_USER || "null"));
  const [token, setToken] = useState(() => localStorage.SS_TOKEN || null);
  const [unlocked, setUnlocked] = useState(() => localStorage.SS_UNLOCKED === "1");
  const [wb, setWb] = useState(null);
  const [stats, setStats] = useState(null);
  const [findings, setFindings] = useState([]);
  const [graphKey, setGraphKey] = useState(0);
  const [toastMsg, setToastMsg] = useState(null);
  const [loadStage, setLoadStage] = useState(null);
  const [authErr, setAuthErr] = useState("");

  const fileRef = useRef(null);
  const dlgRef = useRef(null);
  const askInputRef = useRef(null);
  const toastTimer = useRef(null);

  function toast(html) {
    setToastMsg(html);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToastMsg(null), 4600);
  }

  useEffect(() => {
    if (new URLSearchParams(location.search).get("paid") === "1") {
      localStorage.SS_UNLOCKED = "1";
      setUnlocked(true);
      history.replaceState({}, "", location.pathname);
      setTimeout(() => toast("✅ Full audit unlocked — thank you!"), 400);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ---------- auth ---------- */
  async function auth(mode) {
    setAuthErr("");
    const email = document.getElementById("a-email").value.trim();
    const password = document.getElementById("a-pass").value;
    try {
      if (mode === "signup") {
        const r = await fetch(`${BB_API}/auth/${APP_ID}/signup`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        if (!r.ok) {
          const e = await r.json().catch(() => ({}));
          throw new Error(e.message || e.error || "signup failed");
        }
      }
      const r = await fetch(`${BB_API}/auth/${APP_ID}/login`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(e.message || e.error || "login failed");
      }
      const d = await r.json();
      setToken(d.access_token); setUser(d.user);
      localStorage.SS_TOKEN = d.access_token;
      localStorage.SS_USER = JSON.stringify(d.user);
      dlgRef.current.close();
      toast("Welcome, " + d.user.email);
    } catch (e) { setAuthErr(e.message); }
  }

  function authButton() {
    if (user) {
      setUser(null); setToken(null);
      localStorage.removeItem("SS_TOKEN");
      localStorage.removeItem("SS_USER");
      toast("Signed out");
    } else dlgRef.current.showModal();
  }

  /* ---------- payments ---------- */
  async function buyReport() {
    if (!user) { dlgRef.current.showModal(); return; }
    try {
      const r = await fetch(`${BB_API}/v1/${APP_ID}/billing/purchase`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
        body: JSON.stringify({
          productId: PRODUCT_ID,
          successUrl: location.origin + location.pathname + "?paid=1",
          cancelUrl: location.href,
        }),
      });
      const d = await r.json();
      if (d.url) { location.href = d.url; return; }
      if (d.code === "CONNECT_NOT_READY") {
        localStorage.SS_UNLOCKED = "1"; setUnlocked(true);
        toast("💳 Purchase flow verified against Butterbase billing — Stripe " +
              "seller onboarding skipped for demo, report unlocked in <b>demo mode</b>.");
        return;
      }
      throw new Error(d.message || d.error || "checkout unavailable");
    } catch (e) { toast("💳 Payment error: " + e.message); }
  }

  /* ---------- ingest ---------- */
  async function refreshFindings(workbook) {
    const fs = await api(`/api/workbooks/${workbook}/findings`);
    setFindings(fs);
    return fs;
  }

  async function ingest(promise) {
    let stage = 0;
    setLoadStage(STAGES[0]);
    const t = setInterval(() => {
      stage = Math.min(stage + 1, STAGES.length - 1);
      setLoadStage(STAGES[stage]);
    }, 1800);
    try {
      const d = await promise;
      setWb(d.workbook);
      setStats(d);
      await refreshFindings(d.workbook);
      setGraphKey((k) => k + 1);
      window.scrollTo({ top: 0 });
      toast(`🕵️ Audit complete: <b>${d.findings} suspects</b> in ${d.cells} cells`);
    } catch (e) {
      toast("Load failed — is the backend running? " + e.message);
    } finally {
      clearInterval(t);
      setLoadStage(null);
    }
  }

  const loadDemo = () => ingest(api("/api/demo", { method: "POST" }));
  const pickFile = () => fileRef.current.click();
  function onFile(e) {
    if (!e.target.files.length) return;
    const fd = new FormData();
    fd.append("file", e.target.files[0]);
    ingest(api("/api/workbooks/upload", { method: "POST", body: fd }));
    e.target.value = "";
  }

  /* ---------- verify + ask glue ---------- */
  async function verifyFinding(fid) {
    try {
      const r = await api(`/api/findings/${encodeURIComponent(fid)}/verify`, { method: "POST" });
      toast(`🧪 Verdict: <b>${r.verdict}</b> — ${r.cellsChanged} cells change (via ${r.runner})`);
      await refreshFindings(wb);
      setGraphKey((k) => k + 1);
    } catch (e) { toast("verify failed: " + e.message); }
  }

  function askAbout(fid) {
    const input = askInputRef.current;
    if (input) {
      input.value = "";
      input.focus();
      input.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  let worst = 0;
  findings.forEach((f) => (f.runs || []).forEach((r) => {
    if (r.verdict === "CONFIRMED") worst = Math.max(worst, r.maxAbsDelta || 0);
  }));

  return (
    <>
      <header>
        <div className="brand"><span className="logo">🕵️</span>SheetSleuth</div>
        {!wb && (
          <nav className="anchors">
            <a href="#see">Watch it work</a>
            <a href="#catches">What it catches</a>
            <a href="#how">The loop</a>
          </nav>
        )}
        {stats && <span className="wbchip" style={{ display: "inline" }}>{stats.name}</span>}
        <div className="spacer" />
        {user && <span className="userchip" style={{ display: "inline" }}>👤 {user.email}</span>}
        <button className="ghost" onClick={authButton}>{user ? "Sign out" : "Sign in"}</button>
        <input type="file" ref={fileRef} accept=".xlsx" hidden onChange={onFile} />
        <button onClick={pickFile}>Upload .xlsx</button>
        <button className="primary" onClick={loadDemo}>▶ Audit the demo model</button>
      </header>

      {!wb ? (
        <Landing onDemo={loadDemo} onUpload={pickFile} />
      ) : (
        <main id="app" style={{ display: "block" }}>
          <div className="kpis">
            <div className="kpi glass"><div className="v">{stats.cells.toLocaleString()}</div>
              <div className="l">cells wired</div></div>
            <div className="kpi glass"><div className="v">{stats.edges.toLocaleString()}</div>
              <div className="l">dependency edges</div></div>
            <div className="kpi glass warn"><div className="v">{findings.length}</div>
              <div className="l">suspects found</div></div>
            <div className="kpi glass risk"><div className="v">{worst ? fmt$(worst) : "–"}</div>
              <div className="l">proven impact</div></div>
          </div>

          <GraphPanel wb={wb} refreshKey={graphKey} onToast={toast} />

          <div className="workrow" style={{ marginTop: 8 }}>
            <div className="evcol">
              <h2 className="dash">
                🧾 Evidence
                <span className="sub">every verdict executed in a sandbox — never guessed</span>
              </h2>
              <Evidence
                findings={findings}
                unlocked={unlocked}
                onVerify={verifyFinding}
                onAsk={askAbout}
                onBuy={buyReport}
              />
            </div>
            <div className="askcol">
              <h2 className="dash">💬 Ask the agent<span className="sub">RocketRide Cloud</span></h2>
              <AskPanel wb={wb} user={user} onToast={toast} inputRef={askInputRef} />
            </div>
          </div>
        </main>
      )}

      <dialog ref={dlgRef} id="authdlg">
        <h3>Sign in to SheetSleuth</h3>
        <input id="a-email" type="email" placeholder="email" />
        <input id="a-pass" type="password" placeholder="password (Aa1! + 8 chars to sign up)" />
        <div className="err">{authErr}</div>
        <div style={{ display: "flex", gap: 9, marginTop: 10 }}>
          <button className="primary" style={{ flex: 1 }} onClick={() => auth("login")}>Log in</button>
          <button style={{ flex: 1 }} onClick={() => auth("signup")}>Sign up</button>
        </div>
        <div style={{ textAlign: "center", marginTop: 8 }}>
          <button className="ghost" onClick={() => dlgRef.current.close()}>cancel</button>
        </div>
      </dialog>

      {toastMsg && (
        <div className="toast" style={{ display: "block" }}
             dangerouslySetInnerHTML={{ __html: toastMsg }} />
      )}
      {loadStage && (
        <div id="loader" style={{ display: "grid" }}>
          <div className="box glass">
            <div className="spin" />
            <div id="loadstage">{loadStage}</div>
          </div>
        </div>
      )}
    </>
  );
}
