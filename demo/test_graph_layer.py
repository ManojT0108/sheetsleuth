"""End-to-end test of the Neo4j layer: extract demo workbook -> load ->
run every smell detector -> compare against ground truth."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))
from app.parser.extract import extract_workbook          # noqa: E402
from app.graph.loader import load_workbook               # noqa: E402
from app.graph import queries as q                       # noqa: E402

WB = "demo-lumeo"
path = Path(__file__).parent / "lumeo_fy2026_model.xlsx"

stats = load_workbook(WB, "Lumeo Analytics FY2026", extract_workbook(path))
print(f"loaded: {stats}")

print("\n-- hardcoded_constants (expect E1: Revenue!G3, 0.15) --")
for r in q.hardcoded_constants(WB):
    print(f"  {r['cell']}  suspects={r['suspects']}  blast={r['blast']}")

print("\n-- inconsistent_siblings (expect E2: Revenue!K5) --")
for r in q.inconsistent_siblings(WB):
    print(f"  {r['cell']}  value={r['value']}  sibs={r['formulaSiblings']}"
          f"  blast={r['blast']}")

print("\n-- short_aggregation_ranges (expect E3: Costs row 8, 12 columns) --")
rows = q.short_aggregation_ranges(WB)
for r in rows[:3]:
    print(f"  {r['cell']}  missed={r['missedCells']}"
          f"  missedValue={r['missedStaticValue']}")
print(f"  ... total flagged: {len(rows)}")

print("\n-- orphaned_inputs (expect E5: Assumptions!B12) --")
for r in q.orphaned_inputs(WB):
    print(f"  {r['cell']}  label={r['label']!r}  value={r['value']}")

print("\n-- circular_references (expect none) --")
print(f"  {q.circular_references(WB)}")

print("\n-- critical_cells (top 5 load-bearing) --")
for r in q.critical_cells(WB, 5):
    print(f"  {r['cell']:28s} reach={r['reach']}")

print("\n-- blast_radius of E1 --")
br = q.blast_radius(f"{WB}::Revenue!G3")
print(f"  {br['count']} cells, {br['maxHops']} hops, sheets={br['sheetsReached']}")

print("\n-- cell_context of Summary!B10 (for LLM off-by-one reasoning) --")
print(f"  {q.cell_context(f'{WB}::Summary!B10')}")
