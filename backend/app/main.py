"""SheetSleuth API — thin HTTP layer over the audit spine.

Flow: upload workbook -> dependency graph in Neo4j -> smell detection ->
per-finding sandbox verification -> agent Q&A (via RocketRide pipeline).
"""

import hashlib
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .audit import fixes as fx
from .audit import smells
from .audit.verify import verify_finding
from .graph import queries as q
from .graph.db import run as cypher
from .graph.loader import load_workbook
from .parser.extract import extract_workbook

DATA_DIR = Path(__file__).parents[1] / "data"
DATA_DIR.mkdir(exist_ok=True)

app = FastAPI(title="SheetSleuth")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
    allow_headers=["*"],
)


def _wb_path(wb: str) -> Path:
    path = DATA_DIR / f"{wb}.xlsx"
    if not path.exists():
        raise HTTPException(404, f"workbook {wb} not found")
    return path


@app.post("/api/workbooks/upload")
async def upload(file: UploadFile):
    raw = await file.read()
    slug = re.sub(r"[^a-z0-9]+", "-", (file.filename or "book").lower())
    slug = slug.removesuffix("-xlsx").strip("-")[:40]
    wb = f"{slug}-{hashlib.sha1(raw).hexdigest()[:8]}"
    (DATA_DIR / f"{wb}.xlsx").write_bytes(raw)

    stats = load_workbook(wb, file.filename or wb, extract_workbook(raw_path := DATA_DIR / f"{wb}.xlsx"))
    findings = smells.audit(wb)
    return {"workbook": wb, "name": file.filename, **stats,
            "findings": len(findings)}


@app.get("/api/workbooks/{wb}/graph")
def graph(wb: str):
    nodes = cypher(
        """
        MATCH (c:Cell {workbook:$wb})
        OPTIONAL MATCH (f:Finding)-[:AFFECTS]->(c)
        RETURN c{.id, .sheet, .address, .kind, .row, .col, .formula, .value}
               AS cell, collect(f{.id, .type, .status})[0] AS finding
        """,
        wb=wb,
    )
    edges = cypher(
        """
        MATCH (a:Cell {workbook:$wb})-[:FEEDS_INTO]->(b:Cell)
        RETURN a.id AS src, b.id AS dst
        """,
        wb=wb,
    )
    return {"nodes": nodes, "edges": edges}


@app.get("/api/workbooks/{wb}/findings")
def findings(wb: str):
    return smells.get_findings(wb)


@app.get("/api/workbooks/{wb}/critical")
def critical(wb: str):
    return q.critical_cells(wb)


@app.get("/api/workbooks/{wb}/blast/{sheet}/{address}")
def blast(wb: str, sheet: str, address: str):
    return q.blast_radius(f"{wb}::{sheet}!{address}")


@app.post("/api/findings/{fid:path}/verify")
def verify(fid: str):
    wb = fid.split("::")[0]
    finding = next((f for f in smells.get_findings(wb) if f["id"] == fid), None)
    if not finding:
        raise HTTPException(404, "finding not found")
    proposal = fx.propose(finding)
    if proposal is None:
        raise HTTPException(422, "no deterministic fix; use the agent (/ask)")
    return verify_finding(_wb_path(wb), finding, proposal)


@app.post("/api/workbooks/{wb}/ask")
def ask(wb: str, body: dict):
    """Agent Q&A — routed through the RocketRide Cloud pipeline."""
    from .services.rocketride import ask_agent
    return ask_agent(wb, body.get("question", ""))


@app.get("/api/health")
def health():
    try:
        cypher("RETURN 1 AS ok")
        neo4j_ok = True
    except Exception:
        neo4j_ok = False
    return {"ok": True, "neo4j": neo4j_ok}
