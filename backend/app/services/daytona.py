"""Daytona sandbox runner for verification jobs.

Each verification runs in a fresh, isolated Daytona sandbox: we create the
sandbox, upload the job directory (workbook + job.json + runner script),
install deps, execute, and read back verdict.json. verify.run_sandboxed()
falls back to a local subprocess when DAYTONA_API_KEY is not configured.
"""

import json
import os
from pathlib import Path


def run_job_in_sandbox(job_dir: Path) -> dict:
    api_key = os.environ.get("DAYTONA_API_KEY")
    if not api_key:
        raise RuntimeError("DAYTONA_API_KEY not configured")

    from daytona import CreateSandboxFromImageParams, Daytona

    client = Daytona()  # reads DAYTONA_API_KEY / DAYTONA_TARGET from env
    sandbox = client.create(
        CreateSandboxFromImageParams(image="python:3.12-slim"))
    try:
        for name in ("job.json", "verify_run.py"):
            sandbox.fs.upload_file(
                (job_dir / name).read_bytes(), f"/work/{name}")
        wb_name = json.loads((job_dir / "job.json").read_text())["workbook"]
        sandbox.fs.upload_file(
            (job_dir / wb_name).read_bytes(), f"/work/{wb_name}")

        install = sandbox.process.exec(
            "pip install -q formulas openpyxl", timeout=600)
        if install.exit_code != 0:
            raise RuntimeError(f"sandbox pip failed: {install.result[-500:]}")
        result = sandbox.process.exec(
            "cd /work && python verify_run.py", timeout=600)
        if result.exit_code != 0:
            return {"verdict": "RUN_FAILED", "error": str(result.result)[-2000:]}
        return json.loads(
            sandbox.fs.download_file("/work/verdict.json").decode())
    finally:
        sandbox.delete()
