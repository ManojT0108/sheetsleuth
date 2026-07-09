"""Extractor invariants against the generated demo workbook (the ground-truth
oracle). No services needed."""

from app.parser.extract import extract_workbook


def _index(graph):
    nodes = {n["id"]: n for n in graph["nodes"]}
    out_edges, in_edges = {}, {}
    for e in graph["edges"]:
        out_edges.setdefault(e["src"], []).append(e["dst"])
        in_edges.setdefault(e["dst"], []).append(e["src"])
    return nodes, out_edges, in_edges


def test_counts_and_kinds(demo_xlsx):
    g = extract_workbook(demo_xlsx)
    kinds = {}
    for n in g["nodes"]:
        kinds[n["kind"]] = kinds.get(n["kind"], 0) + 1
    assert kinds["formula"] == 115
    assert len(g["edges"]) == 247


def test_e1_hardcoded_literal_visible(demo_xlsx):
    nodes, _, _ = _index(extract_workbook(demo_xlsx))
    assert 0.15 in nodes["Revenue!G3"].get("literals", [])


def test_e2_pasted_constant_amid_formulas(demo_xlsx):
    nodes, _, _ = _index(extract_workbook(demo_xlsx))
    assert nodes["Revenue!K5"]["kind"] == "number"
    siblings = [nodes[f"Revenue!{c}5"]["kind"] for c in "BCDEFGHIJLM"]
    assert all(k == "formula" for k in siblings)


def test_e3_gap_row_not_feeding_total(demo_xlsx):
    nodes, out_edges, in_edges = _index(extract_workbook(demo_xlsx))
    assert "Costs!B8" not in out_edges.get("Costs!B7", [])
    assert set(in_edges["Costs!B8"]) == {f"Costs!B{r}" for r in range(3, 7)}


def test_e4_off_by_one_edge_present(demo_xlsx):
    _, _, in_edges = _index(extract_workbook(demo_xlsx))
    assert in_edges["Summary!B10"] == ["Revenue!L6"]


def test_e5_orphaned_assumption(demo_xlsx):
    _, out_edges, _ = _index(extract_workbook(demo_xlsx))
    assert "Assumptions!B12" not in out_edges
    assert len(out_edges["Assumptions!B3"]) >= 10


def test_cross_sheet_refs_resolved(demo_xlsx):
    _, out_edges, _ = _index(extract_workbook(demo_xlsx))
    # Assumptions feed Revenue and Costs across sheets
    dsts = {d.split("!")[0] for d in out_edges["Assumptions!B5"]}
    assert "Revenue" in dsts


def test_blast_radius_reaches_summary(demo_xlsx):
    _, out_edges, _ = _index(extract_workbook(demo_xlsx))
    seen, stack = set(), ["Revenue!G3"]
    while stack:
        for nxt in out_edges.get(stack.pop(), []):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    assert len(seen) == 52
    assert any(c.startswith("Summary!") for c in seen)
