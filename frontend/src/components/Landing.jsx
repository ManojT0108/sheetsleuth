import React from "react";

export default function Landing({ onDemo, onUpload }) {
  return (
    <div id="landing">
      <section id="hero">
        <h1>
          Your spreadsheet is <em>lying to you.</em>
        </h1>
        <p className="sub">
          SheetSleuth turns every formula into a living dependency graph, hunts
          down the errors hiding in the wiring — then <b>proves</b> each one by
          re-executing your workbook in an isolated sandbox and measuring the
          damage in dollars.
        </p>
        <div className="cta">
          <button className="primary" onClick={onDemo}>▶ Audit the demo model</button>
          <button onClick={onUpload}>Upload your .xlsx</button>
        </div>
        <div className="herostats">
          <span className="glass">⏱ audit in ~10 seconds</span>
          <span className="glass">🧪 verdicts proven by execution — never guessed</span>
          <span className="glass">📄 works on any .xlsx — try yours</span>
        </div>
      </section>

      <section id="pipeline">
        <div className="pipe glass">
          <span className="stage">.xlsx</span><span className="arr">→</span>
          <span className="stage">Neo4j graph</span><span className="arr">→</span>
          <span className="stage">Detectors</span><span className="arr">→</span>
          <span className="stage">Proposed fix</span><span className="arr">→</span>
          <span className="stage hot">Sandbox run</span><span className="arr">→</span>
          <span className="stage hot">$ verdict</span><span className="arr">→</span>
          <span className="stage">Ask anything</span>
        </div>
      </section>

      <section className="land" id="metrics">
        <div className="metrics">
          <div className="metric glass"><div className="v">~10s</div>
            <div className="l">from raw .xlsx to a full dependency graph with suspects flagged</div></div>
          <div className="metric glass"><div className="v">1 query</div>
            <div className="l">to trace any cell's full blast radius — every downstream cell, every sheet</div></div>
          <div className="metric glass"><div className="v">6 classes</div>
            <div className="l">of error caught: hardcodes · pasted constants · short SUMs · off-by-ones · orphans · cycles</div></div>
          <div className="metric glass"><div className="v"><em>100%</em></div>
            <div className="l">of verdicts proven by re-executing your workbook in a sandbox — zero pattern-match guesses</div></div>
        </div>
      </section>

      <section className="land" id="see">
        <h2 className="sec">Watch it work</h2>
        <p className="seclead">
          A real case from a live audit, told in three acts. The same loop runs
          on any workbook you upload.
        </p>
        <div className="workpanels">
          <div className="case glass">
            <div className="tag">Act I — The crime scene</div>
            <div className="minisheet">
              <table>
                <tbody>
                  <tr><td className="rl">Payroll</td><td className="sumzone">185,000</td></tr>
                  <tr><td className="rl">Marketing</td><td className="sumzone">21,850</td></tr>
                  <tr><td className="rl">Infrastructure</td><td className="sumzone">2,420</td></tr>
                  <tr><td className="rl">Office &amp; misc</td><td className="sumzone">22,000</td></tr>
                  <tr className="ghost"><td className="rl">Contractors ⚠️</td><td>15,000</td></tr>
                  <tr className="tot"><td className="rl">Total costs</td><td>231,270</td></tr>
                </tbody>
              </table>
            </div>
            <p>
              A contractors row was added <b>below</b> the totals. The SUM never
              learned about it — so <b>$15,000 a quarter simply doesn't exist</b>.
              Excel shows no error. A human sees nothing. The graph sees a cell
              that feeds… nothing.
            </p>
          </div>

          <div className="case glass">
            <div className="tag">Act II — The trial</div>
            <div className="trial">
              <div className="wbpill">📄 your workbook<br /><small>as-is</small></div>
              <div className="vs">recomputed<br />side by side</div>
              <div className="wbpill">📄 your workbook<br /><small>with the fix</small></div>
            </div>
            <div className="trialbox">
              🔒 inside an isolated Daytona sandbox — created, run, destroyed in ~7 seconds
            </div>
            <p>
              No opinions, no pattern-matching: we <b>re-execute your entire
              workbook both ways</b> and diff every single cell. Only the
              numbers get a vote.
            </p>
          </div>

          <div className="case glass">
            <div className="tag">Act III — The verdict</div>
            <div className="stampwrap"><span className="stamp">CONFIRMED</span></div>
            <div className="ledger">
              <div><span>Ending cash, as reported</span><b>−$82,065</b></div>
              <div><span>Ending cash, actual</span><b className="bad">−$117,065</b></div>
              <div className="sum"><span>Hidden damage, measured</span><b className="bad">$35,000</b></div>
            </div>
            <p>
              The verdict — with its exact dollar impact — is written back into
              the graph, the report, and the agent's memory. <b>Proof, not vibes.</b>
            </p>
          </div>
        </div>
      </section>

      <section className="land" id="pillars-sec">
        <h2 className="sec">Why it's different</h2>
        <p className="seclead">Spreadsheet linters flag patterns and stop. SheetSleuth closes the loop.</p>
        <div className="pillars">
          <div className="pillar glass"><span className="ico">🕸</span>
            <b>It sees the wiring</b>
            <span>A workbook is thousands of invisible "this feeds that" wires.
              We rebuild them as a Neo4j graph, so questions like "what depends
              on this cell?" become one traversal — not an afternoon of clicking
              Trace Precedents.</span></div>
          <div className="pillar glass"><span className="ico">🧪</span>
            <b>It proves, not lints</b>
            <span>Every suspect gets executed: a fresh Daytona sandbox recomputes
              your entire workbook with and without the fix and measures exactly
              which numbers change, in dollars. Verdicts, not vibes.</span></div>
          <div className="pillar glass"><span className="ico">🧠</span>
            <b>It answers with receipts</b>
            <span>Ask "what if payroll rises 10%?" — the cloud agent won't
              guess. It runs the scenario, cites the measured before/after, and
              remembers your past audits with long-term memory.</span></div>
        </div>
      </section>

      <section className="land" id="why">
        <h2 className="sec">This problem is expensive</h2>
        <p className="seclead">Spreadsheets run the world's decisions, and the research says they're quietly wrong.</p>
        <div className="problems">
          <div className="problem glass"><b>~90% error rate</b>
            Field audits (Panko et&nbsp;al.) consistently find errors in roughly
            nine out of ten large spreadsheets in production use.</div>
          <div className="problem glass"><b>$6,000,000,000</b>
            JPMorgan's "London Whale" loss was amplified by an Excel model with
            a copy-paste error in its risk calculation.</div>
          <div className="problem glass"><b>16,000 lost cases</b>
            The UK's COVID contact-tracing pipeline silently dropped thousands
            of positive cases to an Excel row limit.</div>
        </div>
      </section>

      <section className="land" id="catches">
        <h2 className="sec">What it catches</h2>
        <p className="seclead">
          The classics that quietly wreck real models — caught structurally in
          the graph, then <b>proven by re-execution</b>.
        </p>
        <div className="catchgrid">
          <div className="catch glass"><span className="ico">🔢</span>
            <b>Hardcoded constants in formula chains</b>
            <span>A "temporary" 15% typed into June's growth formula. Every month after is fiction.</span></div>
          <div className="catch glass"><span className="ico">📋</span>
            <b>Pasted-over formulas</b>
            <span>October's revenue overwritten with September's number during board prep. The formula never came back.</span></div>
          <div className="catch glass"><span className="ico">∑</span>
            <b>SUM ranges that stopped short</b>
            <span>A contractors row added below the totals — SUM never learned about row 7.</span></div>
          <div className="catch glass"><span className="ico">↔️</span>
            <b>Off-by-one references</b>
            <span>"Dec ARR" pointing at November's column. Classic drag-fill damage, caught by AI label triage.</span></div>
          <div className="catch glass"><span className="ico">🔌</span>
            <b>Orphaned assumptions</b>
            <span>Support cost per customer: defined, believed, and wired into… nothing at all.</span></div>
          <div className="catch glass"><span className="ico">🌀</span>
            <b>Circular references &amp; load-bearing cells</b>
            <span>Cycle detection plus centrality ranking: know which single cells your whole model hangs from.</span></div>
        </div>
      </section>

      <section className="land" id="how">
        <h2 className="sec">The loop, live</h2>
        <p className="seclead">
          Not a linter. A closed loop: extract → graph → detect →{" "}
          <b>execute → measure</b> → remember. Every stage is a different
          load-bearing technology — remove one and the product stops working.
        </p>
        <div className="walk">
          <div className="step glass"><b><span className="n">1</span>Parse</b>
            <span>Every formula reference becomes a FEEDS_INTO edge in a live property graph.</span>
            <div className="tech">Neo4j Aura</div></div>
          <div className="step glass"><b><span className="n">2</span>Detect</b>
            <span>Cypher traversals find structural smells; an LLM triages the semantic ones.</span>
            <div className="tech">Cypher + Butterbase AI gateway</div></div>
          <div className="step glass"><b><span className="n">3</span>Prove</b>
            <span>A fresh isolated sandbox recomputes the entire workbook, as-is vs fixed, and diffs every cell.</span>
            <div className="tech">Daytona</div></div>
          <div className="step glass"><b><span className="n">4</span>Ask</b>
            <span>A cloud-deployed agent answers what-ifs by actually running them — and remembers past audits.</span>
            <div className="tech">RocketRide Cloud + Cognee</div></div>
        </div>
        <div className="basecamp glass">
          🧈 All of it runs on <b>Butterbase</b> — auth, Postgres, the $9 report
          checkout, the AI gateway behind every LLM call, and the hosting
          serving this very page.
        </div>
      </section>

      <section id="closing">
        <h2>
          Stop trusting your spreadsheet.<br /><em>Start proving it.</em>
        </h2>
        <div className="cta">
          <button className="primary" onClick={onDemo}>▶ Audit the demo model</button>
          <button onClick={onUpload}>Upload your .xlsx</button>
        </div>
      </section>

      <footer>
        Built for <b>HackwithBay 3.0</b> · July 2026 · Track 10 — Open Innovation ·{" "}
        <a href="https://github.com/ManojT0108/sheetsleuth" target="_blank" rel="noreferrer">source</a>
      </footer>
    </div>
  );
}
