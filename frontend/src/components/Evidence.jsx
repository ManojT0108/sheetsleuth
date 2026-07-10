import React, { useState } from "react";
import { api, fmt$, fmtN } from "../lib/api.js";

const PROVABLE = new Set([
  "hardcoded-constant-in-chain", "stale-pasted-constant", "short-sum-range",
]);

function VerdictBlock({ run }) {
  if (!run) return null;
  const top = (run.topDeltas || [])[0];
  return (
    <div className="verdict">
      {top && top.delta != null && (
        <div className="impact">
          📉 <span className="delta">
            {(top.delta > 0 ? "+" : "") + fmt$(top.delta).replace("$-", "-$")}
          </span>{" "}
          <span style={{ color: "var(--ink2)", fontWeight: 500, fontSize: 14 }}>
            {top.label || top.cell}
          </span>
        </div>
      )}
      <span className={"chip " + run.verdict}>{run.verdict}</span>
      <span className="runmeta">
        &nbsp;{run.cellsChanged} cells change · executed in a{" "}
        <b>{run.runner || "sandbox"}</b> sandbox{run.seconds ? ` · ${run.seconds}s` : ""}
      </span>
      <table>
        <tbody>
          <tr><th>cell</th><th>label</th><th>as-is</th><th>fixed</th><th>Δ</th></tr>
          {(run.topDeltas || []).slice(0, 5).map((d, i) => (
            <tr key={i}>
              <td className="mono">{d.cell}</td>
              <td>{d.label || ""}</td>
              <td className="num">{fmtN(d.before)}</td>
              <td className="num">{fmtN(d.after)}</td>
              <td className={"num " + (d.delta < 0 ? "d-neg" : "d-pos")}>
                {d.delta != null ? (d.delta > 0 ? "▲ +" : "▼ ") + fmtN(d.delta) : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FindingCard({ f, onVerify, onAsk }) {
  const [busy, setBusy] = useState(false);
  const run = (f.runs || [])[0];
  const provable = PROVABLE.has(f.type);

  async function verify() {
    setBusy(true);
    try { await onVerify(f.id); } finally { setBusy(false); }
  }

  return (
    <div className={"finding glass " + (f.status || "")}>
      <div className="fhead">
        <h4>{f.summary}</h4>
        <span className={"chip " + f.status}>{f.status}</span>
        {provable ? (
          <button onClick={verify} disabled={busy}>
            {busy ? "⏳ sandbox running…" : run ? "↺ re-prove" : "🧪 Prove it"}
          </button>
        ) : (
          <button onClick={() => onAsk(f.id)}>🤖 Ask the agent</button>
        )}
      </div>
      <div className="meta">
        <span className="chip type">{f.type}</span>
        <span>
          severity{" "}
          <span className="sev"><i style={{ width: `${(f.severity * 100) | 0}%` }} /></span>
        </span>
        <span className="mono">
          {(f.cells || []).slice(0, 3).map((c) => c.split("::")[1]).join(" · ")}
          {(f.cells || []).length > 3 ? " …" : ""}
        </span>
      </div>
      <VerdictBlock run={run} />
    </div>
  );
}

export default function Evidence({ findings, unlocked, onVerify, onAsk, onBuy }) {
  if (!findings.length)
    return <div className="card glass">No findings — load a workbook first.</div>;
  return (
    <div>
      {findings.map((f, i) => {
        const card = <FindingCard key={f.id} f={f} onVerify={onVerify} onAsk={onAsk} />;
        if (unlocked || i === 0) return card;
        return (
          <div className="paywall" key={f.id}>
            <div className="inner">{card}</div>
            <div className="pay-overlay">
              <b>🔒 {findings.length - 1} more findings, verified &amp; waiting</b>
              <button className="buy" onClick={onBuy}>
                Unlock full audit report — $9
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
