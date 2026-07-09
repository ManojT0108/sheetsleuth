import os
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "backend"))

# deterministic, cheap tests: no LLM triage during ingest
os.environ.setdefault("SHEETSLEUTH_SKIP_SEMANTIC", "1")

# load .env so integration tests can reach Aura/Butterbase when present
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def demo_xlsx(tmp_path_factory):
    """A freshly generated demo workbook (never the repo copy, so tests can't
    corrupt the demo prop)."""
    import subprocess
    out = tmp_path_factory.mktemp("wb")
    gen = ROOT / "demo" / "make_demo_workbook.py"
    subprocess.run([sys.executable, str(gen)], check=True, cwd=ROOT / "demo")
    src = ROOT / "demo" / "lumeo_fy2026_model.xlsx"
    dst = out / "lumeo.xlsx"
    dst.write_bytes(src.read_bytes())
    return dst


def has_neo4j() -> bool:
    if not os.environ.get("NEO4J_URI"):
        return False
    try:
        from app.graph.db import run
        run("RETURN 1")
        return True
    except Exception:
        return False


needs_neo4j = pytest.mark.skipif(
    not has_neo4j(), reason="no reachable Neo4j (set NEO4J_URI etc.)")
