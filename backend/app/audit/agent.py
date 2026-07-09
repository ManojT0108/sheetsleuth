"""The SheetSleuth audit agent — LLM reasoning over the Neo4j graph, with
the power to PROVE answers by executing scenarios in a sandbox.

Two capabilities:
  semantic_audit(wb): judges what structure alone can't — e.g. a cell labeled
    "Dec ARR" whose only precedent sits in November's column (off-by-one).
  answer(wb, question): agent Q&A. Wave 1 reasons over graph facts and may
    emit a SCENARIO (cell overrides). If it does, we execute the scenario via
    the sandbox recompute harness and run wave 2 with measured results.

All LLM calls route through the Butterbase AI gateway.
"""

import json
import re
from pathlib import Path

from ..graph.db import run as cypher
from ..services.butterbase import llm
from . import smells
from .verify import build_job, run_sandboxed

DATA_DIR = Path(__file__).parents[2] / "data"


def _reference_contexts(wb: str) -> list[dict]:
    """Formula cells with labels + the labels of every cell they reference."""
    return cypher(
        """
        MATCH (c:Cell {workbook:$wb, kind:'formula'})
        MATCH (lbl:Cell {workbook:$wb, sheet:c.sheet, row:c.row, kind:'text'})
        WHERE lbl.col < c.col
        WITH c, lbl ORDER BY lbl.col DESC
        WITH c, collect(lbl.value)[0] AS label
        MATCH (p:Cell)-[:FEEDS_INTO]->(c)
        OPTIONAL MATCH (ph:Cell {workbook:$wb, sheet:p.sheet, col:p.col,
                                 kind:'text'})
        WHERE ph.row < p.row
        WITH c, label, p, ph ORDER BY ph.row DESC
        WITH c, label, p, collect(ph.value)[0] AS colHeader
        OPTIONAL MATCH (prl:Cell {workbook:$wb, sheet:p.sheet, row:p.row,
                                  kind:'text'})
        WHERE prl.col < p.col
        WITH c, label, p, colHeader, prl ORDER BY prl.col DESC
        WITH c, label, p, colHeader, collect(prl.value)[0] AS rowLabel
        RETURN c.id AS cell, label, c.formula AS formula,
               collect({ref: p.sheet + '!' + p.address,
                        colHeader: colHeader, rowLabel: rowLabel}) AS refs
        """,
        wb=wb,
    )


def semantic_audit(wb: str) -> list[dict]:
    """LLM triage of label-vs-reference semantics; writes findings to Neo4j."""
    structural = smells.get_findings(wb)
    covered = {c for f in structural for c in (f.get("cells") or [])}
    ctxs = [c for c in _reference_contexts(wb)
            if c["label"] and c["cell"] not in covered]
    prompt = (
        "You audit spreadsheets. For each cell below, decide whether its "
        "references semantically match its label. Classic bug: a label names "
        "a period/scope (e.g. 'Dec ARR') but the reference points at a "
        "different one (e.g. November's column header). Only flag CLEAR "
        "mismatches you are confident about; when in doubt, omit. Never "
        "retract — simply leave uncertain cells out.\n\nCells:\n"
        + json.dumps(ctxs, default=str) +
        '\n\nReply with JSON only: {"mismatches":[{"cell":"...","reason":"...",'
        '"suggestedRef":"Sheet!ADDR or null"}]}'
    )
    try:
        raw = llm([{"role": "user", "content": prompt}], max_tokens=800)
        data = _extract_json(raw) or {}
    except Exception as e:
        print(f"semantic_audit LLM error: {e}")
        return []

    findings = []
    existing = len(structural)
    mismatches = [
        m for m in data.get("mismatches", [])
        if m.get("cell") and m["cell"] not in covered
        and not re.search(r"retract|ignore this", m.get("reason", ""), re.I)
    ]
    for i, m in enumerate(mismatches, 1):
        f = {
            "id": f"{wb}::F{existing + i}-label-reference-mismatch",
            "workbook": wb,
            "type": "label-reference-mismatch",
            "cells": [m["cell"]],
            "severity": 0.7,
            "status": "candidate",
            "evidence": {"reason": m["reason"],
                         "suggestedRef": m.get("suggestedRef")},
            "summary": f"{m['cell'].split('::')[1]}: {m['reason']}",
        }
        findings.append(f)
    if findings:
        cypher(
            """
            UNWIND $fs AS f
            MERGE (n:Finding {id:f.id})
            SET n.workbook=f.workbook, n.type=f.type, n.severity=f.severity,
                n.summary=f.summary, n.status=f.status, n.cells=f.cells,
                n.evidence=f.evidence
            WITH n, f UNWIND f.cells AS cid
            MATCH (c:Cell {id:cid}) MERGE (n)-[:AFFECTS]->(c)
            """,
            fs=[{**f, "evidence": json.dumps(f["evidence"])} for f in findings],
        )
    return findings


def _graph_facts(wb: str) -> dict:
    findings = smells.get_findings(wb)
    crit = cypher(
        """
        MATCH (c:Cell {workbook:$wb}) WHERE c.kind IN ['formula','number']
        CALL (c) { MATCH (c)-[:FEEDS_INTO*1..]->(d) RETURN count(DISTINCT d) AS r }
        WITH c, r WHERE r > 0
        RETURN c.sheet + '!' + c.address AS cell, r AS reach
        ORDER BY r DESC LIMIT 8
        """,
        wb=wb,
    )
    inputs = cypher(
        """
        MATCH (c:Cell {workbook:$wb, kind:'number'})
        MATCH (lbl:Cell {workbook:$wb, sheet:c.sheet, row:c.row, kind:'text'})
        WHERE lbl.col < c.col AND (c)-[:FEEDS_INTO]->()
        RETURN c.sheet + '!' + c.address AS cell, lbl.value AS label,
               c.numValue AS value
        LIMIT 30
        """,
        wb=wb,
    )
    return {
        "findings": [
            {"id": f["id"], "type": f["type"], "status": f["status"],
             "summary": f["summary"],
             "impact": (f.get("runs") or [{}])[0].get("topDeltas", [])[:3]}
            for f in findings
        ],
        "loadBearingCells": crit,
        "modelInputs": inputs,
    }


def _extract_json(text: str, anchor: str | None = None) -> dict | None:
    """Parse the first balanced JSON object after `anchor` (or anywhere)."""
    start = text.find(anchor) if anchor else 0
    if start < 0:
        return None
    brace = text.find("{", start)
    if brace < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[brace:])
        return obj
    except json.JSONDecodeError:
        return None


def answer(wb: str, question: str) -> dict:
    facts = _graph_facts(wb)
    wave1 = llm([
        {"role": "system", "content":
            "You are SheetSleuth's audit agent. You answer questions about a "
            "spreadsheet using graph facts (findings, verified impacts, "
            "load-bearing cells, model inputs). If the question is a "
            "what-if/scenario that requires changing input cells, DO NOT "
            "guess numbers. Instead output a line: "
            'SCENARIO: {"changes": {"Sheet!ADDR": newValue, ...}, '
            '"watch": ["Sheet!ADDR", ...]} using modelInputs cells. '
            "Otherwise answer directly, citing cells and verified impacts. "
            "Be concise and concrete."},
        {"role": "user", "content":
            f"Graph facts:\n{json.dumps(facts, default=str)}\n\n"
            f"Question: {question}"},
    ])

    scenario = (_extract_json(wave1, "SCENARIO")
                if "SCENARIO" in wave1 else None)
    if not scenario:
        return {"answer": wave1, "waves": 1, "source": "agent+graph"}

    try:
        wb_path = DATA_DIR / f"{wb}.xlsx"
        job = build_job(wb_path, scenario.get("changes", {}))
        verdict, runner = run_sandboxed(job)
        wave2 = llm([
            {"role": "system", "content":
                "You are SheetSleuth's audit agent. The scenario was ACTUALLY "
                "EXECUTED by recomputing the workbook in a sandbox. Answer "
                "the user's question using these measured results. Cite "
                "before/after numbers. Be concise."},
            {"role": "user", "content":
                f"Question: {question}\nScenario applied: {json.dumps(scenario)}\n"
                f"Measured results:\n{json.dumps(verdict, default=str)[:6000]}"},
        ])
        return {"answer": wave2, "waves": 2, "scenario": scenario,
                "executedVia": runner, "cellsChanged": verdict.get("cellsChanged"),
                "source": "agent+graph+sandbox"}
    except Exception as e:
        return {"answer": wave1, "waves": 1, "source": "agent+graph",
                "scenarioError": str(e)[:200]}
