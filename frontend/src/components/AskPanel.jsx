import React, { useEffect, useRef, useState } from "react";
import { api } from "../lib/api.js";
import { md } from "../lib/md.js";

const SUGGESTIONS = [
  "What happens to runway if payroll rises 10%?",
  "Which Summary cells depend on Revenue!G3?",
  "Which findings are CONFIRMED and what do they cost us?",
];

export default function AskPanel({ wb, user, onToast, inputRef }) {
  const [log, setLog] = useState([
    { role: "a", html:
      "Structural answers come from <b>live Neo4j traversals</b>; what-if " +
      "answers are <b>actually executed in a Daytona sandbox</b> — never guessed." },
  ]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const logRef = useRef(null);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [log, busy]);

  async function ask(text) {
    const question = (text ?? q).trim();
    if (!question || !wb || busy) return;
    setQ("");
    setLog((l) => [...l, { role: "q", text: question }]);
    setBusy(true);
    try {
      const r = await api(`/api/workbooks/${wb}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, user_id: user?.id || null }),
      });
      const badge = r.source === "rocketride-cloud"
        ? "☁️ RocketRide Cloud pipeline"
        : "🤖 " + (r.source || "agent");
      const extra = r.executedVia
        ? ` · scenario executed via <b>${r.executedVia}</b>` : "";
      setLog((l) => [...l, {
        role: "a",
        html: md(String(r.answer || "(no answer)")) +
              `<div class="src">${badge}${extra}</div>`,
      }]);
    } catch (e) {
      setLog((l) => [...l, {
        role: "a",
        html: `<span style="color:var(--t-red)">Agent error: ${e.message}</span>`,
      }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card glass">
      <div id="asklog" ref={logRef}>
        {log.map((m, i) =>
          m.role === "q" ? (
            <div className="msg q" key={i}>{m.text}</div>
          ) : (
            <div className="msg a" key={i} dangerouslySetInnerHTML={{ __html: m.html }} />
          )
        )}
        {busy && (
          <div className="msg a">
            <span className="typing">agent reasoning — graph traversal / sandbox run</span>
          </div>
        )}
      </div>
      <div className="sugs">
        {SUGGESTIONS.map((s) => (
          <button key={s} onClick={() => ask(s)}>{s}</button>
        ))}
      </div>
      <div className="askbar">
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask()}
          placeholder="What happens to runway if payroll rises 10%?"
        />
        <button className="primary" onClick={() => ask()} disabled={busy}>Ask</button>
      </div>
    </div>
  );
}
