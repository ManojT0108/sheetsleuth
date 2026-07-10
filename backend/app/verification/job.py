"""Verification job packaging."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .script import VERIFY_SCRIPT


def build_job(workbook_path: str | Path, fixes: dict) -> Path:
    job_dir = Path(tempfile.mkdtemp(prefix="sheetsleuth-verify-"))
    wb_name = Path(workbook_path).name
    (job_dir / wb_name).write_bytes(Path(workbook_path).read_bytes())
    (job_dir / "job.json").write_text(
        json.dumps({"workbook": wb_name, "fixes": fixes})
    )
    (job_dir / "verify_run.py").write_text(VERIFY_SCRIPT)
    return job_dir
