"""Daytona sandbox runner for verification jobs.

Each verification runs in a fresh, isolated Daytona sandbox: create sandbox,
upload the job (workbook + job.json + runner script), install deps, execute,
read back verdict.json, delete the sandbox. verify.run_sandboxed() falls back
to a local subprocess when DAYTONA_API_KEY is not configured.
"""

import json
import os
from pathlib import Path


def run_job_in_sandbox(job_dir: Path) -> dict:
    if not os.environ.get("DAYTONA_API_KEY"):
        raise RuntimeError("DAYTONA_API_KEY not configured")

    from daytona import Daytona

    client = Daytona()
    sandbox = client.create()  # fresh default-snapshot sandbox (has python3)
    try:
        wd = sandbox.get_user_root_dir() or "/home/daytona"
        work = f"{wd}/verify"
        wb_name = json.loads((job_dir / "job.json").read_text())["workbook"]
        for name in ("job.json", "verify_run.py", wb_name):
            sandbox.fs.upload_file((job_dir / name).read_bytes(),
                                   f"{work}/{name}")

        install = sandbox.process.exec(
            "pip install --quiet formulas openpyxl", cwd=work, timeout=600)
        if install.exit_code != 0:
            raise RuntimeError(f"sandbox pip failed: {str(install.result)[-500:]}")

        result = sandbox.process.exec("python3 verify_run.py", cwd=work,
                                      timeout=600)
        if result.exit_code != 0:
            return {"verdict": "RUN_FAILED",
                    "error": str(result.result)[-2000:]}
        return json.loads(sandbox.fs.download_file(f"{work}/verdict.json"))
    finally:
        sandbox.delete()
