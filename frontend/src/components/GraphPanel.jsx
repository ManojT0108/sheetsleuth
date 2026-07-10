import React, { useEffect, useRef, useState } from "react";
import { DataSet, Network } from "vis-network/standalone";
import { api, esc } from "../lib/api.js";

const SHEET_PREFIX = "__sheet__";

export default function GraphPanel({ wb, refreshKey, onToast }) {
  const netRef = useRef(null);
  const nodesRef = useRef(null);
  const containerRef = useRef(null);
  const [selected, setSelected] = useState(null);
  const [critical, setCritical] = useState([]);

  async function blast(id) {
    const [sheet, address] = id.split("::")[1].split("!");
    const br = await api(`/api/workbooks/${wb}/blast/${sheet}/${address}`);
    const hit = new Set(br.cells.map((c) => c.cell));
    const nodes = nodesRef.current;
    nodes.forEach((n) => {
      if (String(n.id).startsWith(SHEET_PREFIX)) return;
      if (n.id === id)
        nodes.update({ id: n.id, color: { background: "#dc2626" }, size: 21 });
      else if (hit.has(n.id))
        nodes.update({ id: n.id, color: { background: "#f59e0b" }, size: 12 });
      else nodes.update({ id: n.id, color: { background: "#ddd6c8" } });
    });
    onToast(
      `💥 Blast radius of <b>${esc(sheet)}!${esc(address)}</b>: ${br.count} ` +
      `downstream cells across ${br.sheetsReached.join(", ")} (${br.maxHops} hops deep)`
    );
  }

  async function draw() {
    const g = await api(`/api/workbooks/${wb}/graph`);
    const CW = 64, RH = 38, QW = 1120, QH = 640;
    const sheets = [...new Set(g.nodes.map((n) => n.cell.sheet))];
    const qpos = (s) => {
      const i = sheets.indexOf(s);
      return { qx: (i % 2) * QW, qy: Math.floor(i / 2) * QH };
    };

    const nodes = g.nodes
      .filter((n) => n.cell.kind !== "text")
      .map((n) => {
        const c = n.cell, f = n.finding, { qx, qy } = qpos(c.sheet);
        let color = "#8a8478", size = 8, font = { color: "transparent", size: 1 };
        if (c.kind === "formula") { color = "#2563eb"; size = 10; }
        if (f) {
          color = f.status === "CONFIRMED" ? "#dc2626" : "#d97706";
          size = 19;
          font = { color: "#7c3a12", size: 13, vadjust: -2,
                   strokeWidth: 4, strokeColor: "rgba(244,240,231,.9)" };
        }
        return {
          id: c.id, label: f ? c.sheet + "!" + c.address : c.address,
          color: { background: color, border: "rgba(255,255,255,.9)" },
          size, borderWidth: 1.5, shape: "dot", font,
          x: qx + c.col * CW, y: qy + c.row * RH,
          title: (c.sheet + "!" + c.address + "  " + (c.formula || c.value || "")).trim(),
          _cell: c, _finding: f,
        };
      });

    sheets.forEach((s) => {
      const { qx, qy } = qpos(s);
      nodes.push({
        id: SHEET_PREFIX + s, label: s.toUpperCase(), shape: "text",
        font: { color: "#8b857a", size: 18, face: "ui-monospace, Menlo" },
        x: qx + 2 * CW, y: qy - 14, physics: false, chosen: false,
      });
    });

    const edges = g.edges.map((e) => ({
      from: e.src, to: e.dst,
      arrows: { to: { enabled: true, scaleFactor: 0.3 } },
      color: { color: "#b4aa97", opacity: 0.55 }, width: 1,
      smooth: { type: "cubicBezier", roundness: 0.35 },
    }));

    const nodeSet = new DataSet(nodes);
    nodesRef.current = nodeSet;
    netRef.current?.destroy();
    const net = new Network(
      containerRef.current,
      { nodes: nodeSet, edges: new DataSet(edges) },
      { physics: false, interaction: { hover: true, tooltipDelay: 120 } }
    );
    net.fit({ animation: false });
    net.on("click", (p) => {
      if (p.nodes.length && !String(p.nodes[0]).startsWith(SHEET_PREFIX))
        setSelected(nodeSet.get(p.nodes[0]));
    });
    net.on("doubleClick", (p) => {
      if (p.nodes.length && !String(p.nodes[0]).startsWith(SHEET_PREFIX))
        blast(p.nodes[0]);
    });
    netRef.current = net;
  }

  useEffect(() => {
    if (!wb) return;
    draw();
    api(`/api/workbooks/${wb}/critical`).then((rows) => setCritical(rows.slice(0, 6)));
    return () => { netRef.current?.destroy(); netRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wb, refreshKey]);

  const c = selected?._cell, f = selected?._finding;

  return (
    <>
      <h2 className="dash">
        🕸 Dependency graph
        <span className="sub">click = inspect · double-click = blast radius</span>
      </h2>
      <div className="legend">
        <span><span className="dot" style={{ background: "#2563eb" }} />formula</span>
        <span><span className="dot" style={{ background: "#8a8478" }} />static value</span>
        <span><span className="dot" style={{ background: "#d97706" }} />suspect</span>
        <span><span className="dot" style={{ background: "#dc2626" }} />CONFIRMED error</span>
        <button className="ghost" style={{ padding: "2px 10px", fontSize: 12.5 }} onClick={draw}>
          ↺ reset view
        </button>
      </div>
      <div className="row">
        <div className="grow"><div ref={containerRef} id="net" className="glass" /></div>
        <div className="side">
          <div className="card glass">
            <h3>Cell inspector</h3>
            {!c ? (
              <span style={{ color: "var(--ink3)" }}>Click any node.</span>
            ) : (
              <div>
                <div className="kv"><span className="k">cell</span>
                  <span className="mono">{c.sheet}!{c.address}</span></div>
                {c.formula && <div style={{ margin: "7px 0" }}><code>{c.formula}</code></div>}
                {c.value && !c.formula && (
                  <div className="kv"><span className="k">value</span>
                    <span className="mono">{c.value}</span></div>
                )}
                {f && (
                  <div style={{ margin: "9px 0 4px" }}>
                    <span className={"chip " + f.status}>{f.status}</span>{" "}
                    <span className="chip type">{f.type}</span>
                  </div>
                )}
                <div style={{ marginTop: 10 }}>
                  <button onClick={() => blast(selected.id)}>💥 Blast radius</button>
                </div>
              </div>
            )}
          </div>
          <div className="card glass">
            <h3>Most load-bearing cells</h3>
            {critical.map((r) => (
              <div className="kv" key={r.cell}>
                <span className="mono">{r.cell.split("::")[1]}</span>
                <span style={{ color: "var(--ink2)" }}>{r.reach} cells depend</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
