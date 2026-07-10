"""Verification runners.

Runners execute jobs and return verdicts. They do not write graph state.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from ..errors import IntegrationUnavailable
from ..models.verification import RunnerOutcome
from .job import build_job


def run_local(job_dir: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, "verify_run.py"],
        cwd=job_dir,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:
        return {"verdict": "RUN_FAILED", "error": proc.stderr[-2000:]}
    return json.loads((job_dir / "verdict.json").read_text())


def run_sandboxed(
    job_dir: Path,
    allow_local_fallback: bool = True,
    use_daytona: bool = True,
) -> tuple[dict, str]:
    """Daytona sandbox first, local subprocess as explicit fallback."""
    if not use_daytona:
        if not allow_local_fallback:
            raise IntegrationUnavailable("verification runner unavailable")
        return run_local(job_dir), "local-subprocess"

    try:
        from ..services.daytona import run_job_in_sandbox

        return run_job_in_sandbox(job_dir), "daytona"
    except Exception as exc:
        if not allow_local_fallback:
            raise IntegrationUnavailable(f"daytona verification unavailable: {exc}") from exc
        return run_local(job_dir), "local-subprocess"


class DefaultVerificationRunner:
    def __init__(self, use_daytona: bool = True, allow_local_fallback: bool = True):
        self.use_daytona = use_daytona
        self.allow_local_fallback = allow_local_fallback

    def run(self, workbook_path: str | Path, fixes: dict) -> RunnerOutcome:
        started = time.time()
        job_dir = build_job(workbook_path, fixes)
        verdict, runner = run_sandboxed(
            job_dir,
            allow_local_fallback=self.allow_local_fallback,
            use_daytona=self.use_daytona,
        )
        return RunnerOutcome(
            verdict=verdict,
            runner=runner,
            seconds=time.time() - started,
        )
