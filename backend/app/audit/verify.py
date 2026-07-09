"""Verification engine: prove a finding actually corrupts the numbers.

The agent proposes a fix (deterministic for structural types, LLM for
semantic ones). This module packages a self-contained verification job —
workbook + fixes + runner script — executes it in an isolated sandbox
(Daytona in production, local subprocess as fallback), and writes the
verdict back to Neo4j as a (:Run)-[:VERIFIES]->(:Finding).

The runner recomputes the ENTIRE workbook twice (as-is vs fixed) and diffs
every computed cell, so impact numbers are measured, never estimated.
"""

import json
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from ..graph.db import run as cypher

# Runs inside the sandbox. Self-contained: only needs formulas + openpyxl.
VERIFY_SCRIPT = r'''
import json, re
from pathlib import Path
import formulas, openpyxl

job = json.loads(Path("job.json").read_text())
src = job["workbook"]

def compute(path):
    sol = formulas.ExcelModel().loads(path).finish().calculate()
    fname = Path(path).name.upper()
    out = {}
    for k, v in sol.items():
        m = re.match(r"^'\[(.+?)\](.+?)'!([A-Z]{1,3}[0-9]+)$", k)
        if not m or m.group(1).upper() != fname:
            continue
        try:
            val = v.value[0, 0]
        except Exception:
            continue
        if hasattr(val, "item"):
            val = val.item()
        out[f"{m.group(2)}!{m.group(3)}"] = val
    return out

wb = openpyxl.load_workbook(src)
labels = {}
for ws in wb.worksheets:
    for row in ws.iter_rows():
        label = None
        for cell in row:
            if isinstance(cell.value, str) and not cell.value.startswith("="):
                label = label or cell.value
            elif cell.value is not None and label:
                labels[f"{ws.title.upper()}!{cell.coordinate}"] = label

baseline = compute(src)

sheets = {s.upper(): s for s in wb.sheetnames}
for ref, formula in job["fixes"].items():
    sheet, addr = ref.split("!")
    if isinstance(formula, str) and not formula.startswith("="):
        try:
            formula = float(formula) if "." in formula else int(formula)
        except ValueError:
            pass  # genuinely a text value
    wb[sheets[sheet.upper()]][addr] = formula
fixed_path = "fixed.xlsx"
wb.save(fixed_path)
fixed = compute(fixed_path)

deltas = []
for key, before in baseline.items():
    after = fixed.get(key)
    if isinstance(before, (int, float)) and isinstance(after, (int, float)):
        if abs(after - before) > 0.005:
            deltas.append({"cell": key, "label": labels.get(key),
                           "before": before, "after": after,
                           "delta": after - before})
    elif after != before:
        deltas.append({"cell": key, "label": labels.get(key),
                       "before": str(before), "after": str(after),
                       "delta": None})

deltas.sort(key=lambda d: -abs(d["delta"] or 0))
verdict = {
    "verdict": "CONFIRMED" if deltas else "NO_IMPACT",
    "cellsChanged": len(deltas),
    "maxAbsDelta": max((abs(d["delta"]) for d in deltas if d["delta"]), default=0),
    "topDeltas": deltas[:12],
}
Path("verdict.json").write_text(json.dumps(verdict, indent=2))
print(json.dumps(verdict))
'''


def build_job(workbook_path: str | Path, fixes: dict) -> Path:
    job_dir = Path(tempfile.mkdtemp(prefix="sheetsleuth-verify-"))
    wb_name = Path(workbook_path).name
    (job_dir / wb_name).write_bytes(Path(workbook_path).read_bytes())
    (job_dir / "job.json").write_text(
        json.dumps({"workbook": wb_name, "fixes": fixes}))
    (job_dir / "verify_run.py").write_text(VERIFY_SCRIPT)
    return job_dir


def run_local(job_dir: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, "verify_run.py"], cwd=job_dir,
        capture_output=True, text=True, timeout=300,
    )
    if proc.returncode != 0:
        return {"verdict": "RUN_FAILED", "error": proc.stderr[-2000:]}
    return json.loads((job_dir / "verdict.json").read_text())


def run_sandboxed(job_dir: Path) -> tuple[dict, str]:
    """Daytona sandbox first, local subprocess as honest fallback."""
    try:
        from ..services.daytona import run_job_in_sandbox
        return run_job_in_sandbox(job_dir), "daytona"
    except Exception:
        return run_local(job_dir), "local-subprocess"


def verify_finding(workbook_path: str | Path, finding: dict,
                   fixes: dict) -> dict:
    started = time.time()
    job_dir = build_job(workbook_path, fixes)
    verdict, runner = run_sandboxed(job_dir)

    run_id = f"run-{uuid.uuid4().hex[:10]}"
    cypher(
        """
        MATCH (f:Finding {id:$fid})
        CREATE (r:Run {id:$rid, workbook:f.workbook, runner:$runner,
                       verdict:$verdict, cellsChanged:$changed,
                       maxAbsDelta:$maxDelta, fixes:$fixes,
                       topDeltas:$topDeltas, seconds:$secs, ts:timestamp()})
        CREATE (r)-[:VERIFIES]->(f)
        SET f.status = CASE $verdict WHEN 'CONFIRMED' THEN 'CONFIRMED'
                       WHEN 'NO_IMPACT' THEN 'NO_IMPACT' ELSE f.status END,
            f.maxAbsDelta = $maxDelta, f.cellsChanged = $changed
        """,
        fid=finding["id"], rid=run_id, runner=runner,
        verdict=verdict.get("verdict"),
        changed=verdict.get("cellsChanged", 0),
        maxDelta=verdict.get("maxAbsDelta", 0.0),
        fixes=json.dumps(fixes),
        topDeltas=json.dumps(verdict.get("topDeltas", []))[:8000],
        secs=round(time.time() - started, 2),
    )
    return {"runId": run_id, "runner": runner, **verdict}
