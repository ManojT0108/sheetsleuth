"""API integration via FastAPI TestClient. Needs Neo4j; LLM triage is
disabled via SHEETSLEUTH_SKIP_SEMANTIC and verification is forced onto the
local runner so tests don't depend on Daytona."""

import io
import uuid

import openpyxl
import pytest

from tests.conftest import needs_neo4j


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture(scope="module")
def uploaded(client, demo_xlsx):
    """Upload a byte-perturbed copy (unique hash => unique workbook id) and
    clean the graph afterwards."""
    wb = openpyxl.load_workbook(demo_xlsx)
    wb["Assumptions"]["Z99"] = f"pytest-{uuid.uuid4().hex[:6]}"
    buf = io.BytesIO()
    wb.save(buf)
    r = client.post(
        "/api/workbooks/upload",
        files={"file": ("pytest_model.xlsx", buf.getvalue())})
    assert r.status_code == 200, r.text
    data = r.json()
    yield data
    from app.graph.loader import clear_workbook
    clear_workbook(data["workbook"])


@needs_neo4j
def test_upload_reports_findings(uploaded):
    assert uploaded["cells"] == 197  # +1 pytest marker cell
    assert uploaded["findings"] == 4  # semantic (E4) skipped in tests


@needs_neo4j
def test_graph_endpoint_shape(client, uploaded):
    g = client.get(f"/api/workbooks/{uploaded['workbook']}/graph").json()
    assert len(g["nodes"]) == 197
    assert len(g["edges"]) == 247
    flagged = [n for n in g["nodes"] if n["finding"]]
    assert len(flagged) >= 14  # E1 + E2 + 12 short-sum cells + E5


@needs_neo4j
def test_findings_endpoint(client, uploaded):
    fs = client.get(f"/api/workbooks/{uploaded['workbook']}/findings").json()
    assert {f["type"] for f in fs} == {
        "hardcoded-constant-in-chain", "stale-pasted-constant",
        "short-sum-range", "orphaned-assumption"}
    assert all(f["status"] == "candidate" for f in fs)


@needs_neo4j
def test_verify_flow_confirms_finding(client, uploaded, monkeypatch):
    from app.audit import verify as verify_mod
    monkeypatch.setattr(
        verify_mod, "run_sandboxed",
        lambda job: (verify_mod.run_local(job), "local-test"))

    fs = client.get(f"/api/workbooks/{uploaded['workbook']}/findings").json()
    fid = next(f["id"] for f in fs if f["type"] == "short-sum-range")
    r = client.post(f"/api/findings/{fid}/verify")
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["verdict"] == "CONFIRMED"
    assert v["cellsChanged"] == 8

    fs2 = client.get(f"/api/workbooks/{uploaded['workbook']}/findings").json()
    updated = next(f for f in fs2 if f["id"] == fid)
    assert updated["status"] == "CONFIRMED"
    assert updated["runs"][0]["verdict"] == "CONFIRMED"


@needs_neo4j
def test_verify_advisory_finding_rejected(client, uploaded):
    fs = client.get(f"/api/workbooks/{uploaded['workbook']}/findings").json()
    fid = next(f["id"] for f in fs if f["type"] == "orphaned-assumption")
    assert client.post(f"/api/findings/{fid}/verify").status_code == 422


@needs_neo4j
def test_unknown_workbook_404(client):
    assert client.get("/api/workbooks/nope/findings").json() == []
    r = client.post("/api/findings/nope::F1-x/verify")
    assert r.status_code == 404


def test_health(client):
    assert client.get("/api/health").json()["ok"] is True
