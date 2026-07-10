"""SheetSleuth API — thin HTTP layer over the audit spine.

Flow: upload workbook -> dependency graph in Neo4j -> smell detection ->
per-finding sandbox verification -> agent Q&A (via RocketRide pipeline).
"""

import hashlib
import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / ".env")  # before app imports read env

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .audit import fixes as fx
from .audit import smells
from .audit.verify import verify_finding
from .graph import queries as q
from .graph.db import run as cypher
from .graph.loader import load_workbook
from .parser.extract import extract_workbook

log = logging.getLogger("sheetsleuth")

DATA_DIR = Path(__file__).parents[1] / "data"
DATA_DIR.mkdir(exist_ok=True)
FRONTEND_DIST = Path(__file__).parents[2] / "frontend" / "dist"
DEMO_XLSX = Path(__file__).parents[2] / "demo" / "lumeo_fy2026_model.xlsx"

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


def _ingest(raw: bytes, name: str) -> dict:
    """Persist an uploaded workbook, build its graph, and run the audit."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower())
    slug = slug.removesuffix("-xlsx").strip("-")[:40]
    wb = f"{slug}-{hashlib.sha1(raw).hexdigest()[:8]}"
    path = DATA_DIR / f"{wb}.xlsx"
    path.write_bytes(raw)

    stats = load_workbook(wb, name, extract_workbook(path))
    findings = smells.audit(wb)
    findings += _semantic_findings(wb)
    _mirror_workbook(wb, name, stats, len(findings))
    return {"workbook": wb, "name": name, **stats, "findings": len(findings)}


def _semantic_findings(wb: str) -> list:
    """LLM triage for label/reference mismatches. Best-effort: an LLM or
    gateway outage degrades the audit to structural-only, never fails it."""
    if os.environ.get("SHEETSLEUTH_SKIP_SEMANTIC"):
        return []
    try:
        from .audit.agent import semantic_audit
        return semantic_audit(wb)
    except Exception:
        log.warning("semantic audit skipped", exc_info=True)
        return []


def _mirror_workbook(wb: str, name: str, stats: dict, n_findings: int):
    """Best-effort mirror into the Butterbase Postgres workbooks table."""
    try:
        from .services.butterbase import ANON_USER, upsert_workbook
        upsert_workbook({"id": wb, "name": name, "user_id": ANON_USER,
                         "cells": stats["cells"], "edges": stats["edges"],
                         "sheets": stats["sheets"],
                         "findings_count": n_findings})
    except Exception:
        log.warning("butterbase workbook mirror failed", exc_info=True)


@app.post("/api/workbooks/upload")
async def upload(file: UploadFile):
    return _ingest(await file.read(), file.filename or "workbook")


@app.post("/api/demo")
def demo():
    return _ingest(DEMO_XLSX.read_bytes(), "Lumeo Analytics FY2026 (demo)")


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

    result = verify_finding(_wb_path(wb), finding, proposal)
    if result.get("verdict") == "CONFIRMED":
        from .services.cognee_mem import remember_verdict_async
        remember_verdict_async(wb, finding, result)
    return result


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


app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True),
          name="frontend")
