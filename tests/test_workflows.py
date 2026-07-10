"""Workflow tests: no Neo4j, no network."""

from pathlib import Path

from app.models.integrations import IntegrationStatus
from app.models.verification import RunRecord, RunnerOutcome
from app.models.workbook import GraphStats
from app.workflows.ask import AskWorkflow
from app.workflows.ingestion import WorkbookIngestion
from app.workflows.verification import FindingVerifier


class FakeStore:
    def __init__(self, path: Path):
        self.path = path
        self.saved = None

    def save(self, workbook_id: str, raw: bytes) -> Path:
        self.saved = (workbook_id, raw)
        self.path.write_bytes(raw)
        return self.path

    def path_for(self, workbook_id: str) -> Path:
        return self.path


class FakeWorkbooks:
    def __init__(self):
        self.loaded = None

    def replace_graph(self, workbook_id: str, name: str, extracted: dict) -> GraphStats:
        self.loaded = (workbook_id, name, extracted)
        return GraphStats(cells=2, edges=1, sheets=1)


class FakeFindings:
    def __init__(self, finding: dict | None = None):
        self.finding = finding

    def audit_structural(self, workbook_id: str) -> list[dict]:
        return [{"id": f"{workbook_id}::F1-short-sum-range"}]

    def get(self, finding_id: str) -> dict | None:
        return self.finding


class FakeSemanticAudit:
    def run(self, workbook_id: str) -> tuple[list[dict], IntegrationStatus]:
        return (
            [{"id": f"{workbook_id}::F2-label-reference-mismatch"}],
            IntegrationStatus.succeeded("semantic"),
        )


class FailingMirror:
    def mirror(self, row: dict) -> IntegrationStatus:
        raise RuntimeError("mirror down")


def test_ingestion_coordinates_storage_graph_audit_and_reports_mirror_failure(
    tmp_path, monkeypatch
):
    def fake_extract(path: Path) -> dict:
        assert path.exists()
        return {"nodes": [], "edges": []}

    monkeypatch.setattr("app.workflows.ingestion.extract_workbook", fake_extract)
    store = FakeStore(tmp_path / "book.xlsx")
    workbooks = FakeWorkbooks()

    result = WorkbookIngestion(
        store=store,
        workbooks=workbooks,
        findings=FakeFindings(),
        semantic_audit=FakeSemanticAudit(),
        workbook_mirror=FailingMirror(),
    ).ingest(b"xlsx-bytes", "Model.xlsx")

    public = result.to_public_dict()
    assert public["workbook"].startswith("model-")
    assert public["cells"] == 2
    assert public["findings"] == 2
    assert public["integrations"]["semanticAudit"]["ok"] is True
    assert public["integrations"]["workbookMirror"]["ok"] is False
    assert workbooks.loaded[1] == "Model.xlsx"


class FakeRuns:
    def __init__(self):
        self.recorded = None

    def record_verification(self, finding_id, runner, verdict, fixes, seconds):
        self.recorded = (finding_id, runner, verdict, fixes, seconds)
        return RunRecord(
            id="run-test",
            runner=runner,
            verdict=verdict["verdict"],
            cells_changed=verdict["cellsChanged"],
            max_abs_delta=verdict["maxAbsDelta"],
        )


class FakeRunner:
    def run(self, workbook_path: Path, fixes: dict) -> RunnerOutcome:
        return RunnerOutcome(
            verdict={
                "verdict": "CONFIRMED",
                "cellsChanged": 1,
                "maxAbsDelta": 12.0,
                "topDeltas": [{"cell": "SHEET!A1", "delta": 12.0}],
            },
            runner="fake-runner",
            seconds=0.25,
        )


class FakeMemory:
    def __init__(self):
        self.remembered = False

    def remember_verified(self, workbook_id: str, finding: dict, result: dict):
        self.remembered = True
        return IntegrationStatus.succeeded("memory")


def test_verifier_proposes_runs_records_and_memorizes_confirmed_result(
    tmp_path, monkeypatch
):
    workbook = tmp_path / "book.xlsx"
    workbook.write_bytes(b"xlsx")
    runs = FakeRuns()
    memory = FakeMemory()
    finding = {
        "id": "wb::F1-short-sum-range",
        "summary": "bad total",
        "type": "short-sum-range",
        "cells": ["wb::Sheet!A1"],
    }
    monkeypatch.setattr(
        "app.workflows.verification.fx.propose",
        lambda _: {"Sheet!A1": "=SUM(A1:A2)"},
    )

    result = FindingVerifier(
        store=FakeStore(workbook),
        findings=FakeFindings(finding),
        runs=runs,
        runner=FakeRunner(),
        memory=memory,
    ).verify("wb::F1-short-sum-range")

    assert result["runId"] == "run-test"
    assert result["runner"] == "fake-runner"
    assert result["verdict"] == "CONFIRMED"
    assert runs.recorded[3] == {"Sheet!A1": "=SUM(A1:A2)"}
    assert memory.remembered is True


class FailingCloud:
    def ask(self, workbook_id: str, question: str) -> dict:
        raise RuntimeError("cloud unavailable")


class FakeLocal:
    def ask(self, workbook_id: str, question: str) -> dict:
        return {"answer": "local answer", "source": "agent+graph"}


class FakeAskMirror:
    def mirror(self, workbook_id: str, question: str, result: dict):
        return IntegrationStatus.succeeded("ask-history")


def test_ask_workflow_makes_cloud_fallback_explicit():
    result = AskWorkflow(
        cloud_client=FailingCloud(),
        local_client=FakeLocal(),
        ask_history_mirror=FakeAskMirror(),
        allow_local_agent=True,
        expose_fallback_reason=True,
    ).ask("wb", "what changed?")

    assert result["answer"] == "local answer"
    assert result["source"] == "agent+graph"
    assert "RuntimeError: cloud unavailable" in result["cloudFallback"]
    assert result["integrations"]["askHistoryMirror"]["ok"] is True
