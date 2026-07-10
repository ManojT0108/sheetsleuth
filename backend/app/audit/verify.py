"""Compatibility imports for the verification engine.

The low-level verifier now lives under ``app.verification`` and only executes
jobs. This module keeps older scripts/tests working and provides a compatibility
``verify_finding`` wrapper that records the run through ``RunRepository``.
"""

from __future__ import annotations

from pathlib import Path

from ..repositories.runs import RunRepository
from ..verification.job import build_job
from ..verification.runner import run_local, run_sandboxed
from ..verification.script import VERIFY_SCRIPT


def verify_finding(workbook_path: str | Path, finding: dict, fixes: dict) -> dict:
    import time

    started = time.time()
    job_dir = build_job(workbook_path, fixes)
    verdict, runner = run_sandboxed(job_dir)
    run = RunRepository().record_verification(
        finding_id=finding["id"],
        runner=runner,
        verdict=verdict,
        fixes=fixes,
        seconds=time.time() - started,
    )
    return {"runId": run.id, "runner": runner, **verdict}
