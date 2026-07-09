"""Full closed-loop test: detect findings -> propose fixes -> verify by
sandbox recomputation -> verdicts with measured $ impact in Neo4j."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))
from app.parser.extract import extract_workbook      # noqa: E402
from app.graph.loader import load_workbook           # noqa: E402
from app.audit import smells, fixes as fx            # noqa: E402
from app.audit.verify import verify_finding          # noqa: E402

WB = "demo-lumeo"
path = Path(__file__).parent / "lumeo_fy2026_model.xlsx"

load_workbook(WB, "Lumeo Analytics FY2026", extract_workbook(path))
findings = smells.audit(WB)
print(f"{len(findings)} candidate findings\n")

for f in findings:
    proposal = fx.propose(f)
    if proposal is None:
        print(f"[{f['type']}] {f['summary']}")
        print("   -> advisory/semantic; no deterministic fix\n")
        continue
    result = verify_finding(path, f, proposal)
    print(f"[{f['type']}] {f['summary']}")
    print(f"   fix: {proposal}")
    print(f"   VERDICT: {result['verdict']} via {result['runner']} "
          f"({result.get('cellsChanged', 0)} cells change)")
    for d in result.get("topDeltas", [])[:4]:
        if d.get("delta") is not None:
            print(f"     {d['cell']:16s} {d.get('label') or '':38.38s} "
                  f"{d['before']:>14,.0f} -> {d['after']:>14,.0f} "
                  f"(Δ {d['delta']:+,.0f})")
    print()
