"""Assert every planted error in the demo workbook is structurally visible
in the extracted dependency graph. This is the project's de-risk gate."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))
from app.parser.extract import extract_workbook  # noqa: E402

g = extract_workbook(Path(__file__).parent / "lumeo_fy2026_model.xlsx")
nodes = {n["id"]: n for n in g["nodes"]}
out_edges = {}
in_edges = {}
for e in g["edges"]:
    out_edges.setdefault(e["src"], []).append(e["dst"])
    in_edges.setdefault(e["dst"], []).append(e["src"])

checks = []

# E1: hardcoded 0.15 literal inside Revenue!G3's formula
n = nodes.get("Revenue!G3", {})
checks.append(("E1 hardcoded 0.15 in Revenue!G3",
               0.15 in n.get("literals", [])))

# E2: Revenue!K5 (Oct) is a static number while its row-5 siblings are formulas
siblings = [nodes.get(f"Revenue!{c}5", {}).get("kind")
            for c in "BCDEFGHIJLM"]
checks.append(("E2 Revenue!K5 static amid formula siblings",
               nodes.get("Revenue!K5", {}).get("kind") == "number"
               and all(k == "formula" for k in siblings)))

# E3: Costs!B7 holds data but does not feed the total Costs!B8
checks.append(("E3 Costs!B7 not feeding total Costs!B8",
               "Costs!B7" in nodes
               and "Costs!B8" not in out_edges.get("Costs!B7", [])
               and set(in_edges.get("Costs!B8", [])) ==
               {f"Costs!B{r}" for r in range(3, 7)}))

# E4: Summary!B10 fed by Revenue!L6 (November) — off-by-one is in the graph
checks.append(("E4 Summary!B10 <- Revenue!L6 (not M6)",
               in_edges.get("Summary!B10") == ["Revenue!L6"]))

# E5: Assumptions!B12 feeds nothing; healthy assumptions feed many cells
checks.append(("E5 Assumptions!B12 orphaned",
               "Assumptions!B12" not in out_edges
               and len(out_edges.get("Assumptions!B3", [])) >= 10))

# Bonus: blast radius of E1 reaches the board summary
def downstream(start):
    seen, stack = set(), [start]
    while stack:
        for nxt in out_edges.get(stack.pop(), []):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen

blast = downstream("Revenue!G3")
checks.append(("E1 blast radius reaches Summary sheet",
               any(c.startswith("Summary!") for c in blast)))
print(f"   (E1 blast radius: {len(blast)} downstream cells)")

failed = [name for name, ok in checks if not ok]
for name, ok in checks:
    print(("PASS" if ok else "FAIL"), name)
print()
if failed:
    print(json.dumps({k: nodes.get(k) for k in
                      ("Revenue!G3", "Revenue!J5", "Summary!B10")}, indent=2))
    sys.exit(f"{len(failed)} check(s) failed")
print("ALL CHECKS PASSED — every planted error is visible in the graph.")
