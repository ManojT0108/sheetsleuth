"""Run the graph smell detectors and persist candidate Findings to Neo4j."""

import json

from ..graph import queries as q
from ..graph.db import run


def detect(wb: str) -> list[dict]:
    findings: list[dict] = []

    for r in q.hardcoded_constants(wb):
        findings.append({
            "type": "hardcoded-constant-in-chain",
            "cells": [r["cell"]],
            "severity": min(1.0, 0.4 + r["blast"] / 100),
            "evidence": {"formula": r["formula"], "suspects": r["suspects"],
                         "blast": r["blast"]},
            "summary": f"{r['cell'].split('::')[1]} mixes the magic number(s) "
                       f"{r['suspects']} into a formula chain that feeds "
                       f"{r['blast']} downstream cells.",
        })

    for r in q.inconsistent_siblings(wb):
        findings.append({
            "type": "stale-pasted-constant",
            "cells": [r["cell"]],
            "severity": min(1.0, 0.4 + r["blast"] / 100),
            "evidence": {"value": r["value"], "blast": r["blast"],
                         "siblingFormula": r["siblingFormula"]},
            "summary": f"{r['cell'].split('::')[1]} is a pasted constant "
                       f"({r['value']}) inside a row of "
                       f"{r['formulaSiblings']} live formulas.",
        })

    # group short-SUM rows: one finding per (sheet, total row)
    by_total_row: dict[tuple, list[dict]] = {}
    for r in q.short_aggregation_ranges(wb):
        sheet, addr = r["cell"].split("::")[1].split("!")
        row = int("".join(ch for ch in addr if ch.isdigit()))
        by_total_row.setdefault((sheet, row), []).append(r)
    for (sheet, row), rows in by_total_row.items():
        missed = sorted({m for r in rows for m in r["missedCells"]})
        missed_value = sum(r["missedStaticValue"] or 0 for r in rows)
        findings.append({
            "type": "short-sum-range",
            "cells": [r["cell"] for r in rows],
            "severity": 0.8,
            "evidence": {"missedCells": missed, "missedStaticValue": missed_value,
                         "exampleFormula": rows[0]["formula"]},
            "summary": f"{sheet} row {row} totals stop short of "
                       f"{len(missed)} populated cell(s) directly above them — "
                       f"at least ${missed_value:,.0f} is invisible to the total.",
        })

    for r in q.orphaned_inputs(wb):
        findings.append({
            "type": "orphaned-assumption",
            "cells": [r["cell"]],
            "severity": 0.5,
            "evidence": {"label": r["label"], "value": r["value"]},
            "summary": f"{r['cell'].split('::')[1]} ({r['label']}) feeds "
                       f"nothing — this input is not wired into the model.",
        })

    for r in q.circular_references(wb):
        findings.append({
            "type": "circular-reference",
            "cells": [r["cell"]],
            "severity": 0.9,
            "evidence": {"cycle": r["cycle"]},
            "summary": f"Circular reference through {r['cell'].split('::')[1]}.",
        })

    for i, f in enumerate(findings, 1):
        f["id"] = f"{wb}::F{i}-{f['type']}"
        f["workbook"] = wb
        f["status"] = "candidate"
    return findings


def write_findings(wb: str, findings: list[dict]):
    run("MATCH (f:Finding {workbook:$wb}) DETACH DELETE f", wb=wb)
    run(
        """
        UNWIND $fs AS f
        MERGE (n:Finding {id:f.id})
        SET n.workbook=f.workbook, n.type=f.type, n.severity=f.severity,
            n.summary=f.summary, n.status=f.status, n.cells=f.cells,
            n.evidence=f.evidence
        WITH n, f
        UNWIND f.cells AS cid
        MATCH (c:Cell {id:cid})
        MERGE (n)-[:AFFECTS]->(c)
        """,
        fs=[{**f, "evidence": json.dumps(f["evidence"])} for f in findings],
    )


def get_findings(wb: str) -> list[dict]:
    rows = run(
        """
        MATCH (f:Finding {workbook:$wb})
        OPTIONAL MATCH (r:Run)-[:VERIFIES]->(f)
        WITH f, r ORDER BY r.ts DESC
        RETURN f{.*} AS f, collect(r{.*}) AS runs
        ORDER BY f.severity DESC
        """,
        wb=wb,
    )
    out = []
    for row in rows:
        f = row["f"]
        f["evidence"] = json.loads(f.get("evidence") or "{}")
        for r in row["runs"]:
            r["topDeltas"] = json.loads(r.get("topDeltas") or "[]")
            r["fixes"] = json.loads(r.get("fixes") or "{}")
        f["runs"] = row["runs"]
        out.append(f)
    return out


def audit(wb: str) -> list[dict]:
    findings = detect(wb)
    write_findings(wb, findings)
    return findings
