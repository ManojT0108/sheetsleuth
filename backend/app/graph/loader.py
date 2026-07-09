"""Load extractor output into Neo4j.

Graph model:
  (:Workbook)-[:HAS_SHEET]->(:Sheet)-[:CONTAINS]->(:Cell)
  (:Cell)-[:FEEDS_INTO]->(:Cell)          # precedent -> dependent
  (:Finding)-[:AFFECTS]->(:Cell)          # written by the audit layer
  (:Run)-[:VERIFIES]->(:Finding)          # written by the verification engine
Cell ids are globally namespaced: "<workbook>::<sheet>!<address>".
"""

from .db import run

CONSTRAINTS = [
    "CREATE CONSTRAINT cell_id IF NOT EXISTS FOR (c:Cell) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT sheet_id IF NOT EXISTS FOR (s:Sheet) REQUIRE s.id IS UNIQUE",
    "CREATE CONSTRAINT wb_id IF NOT EXISTS FOR (w:Workbook) REQUIRE w.id IS UNIQUE",
    "CREATE CONSTRAINT finding_id IF NOT EXISTS FOR (f:Finding) REQUIRE f.id IS UNIQUE",
]


def ensure_schema():
    for c in CONSTRAINTS:
        run(c)


def clear_workbook(workbook_id: str):
    run(
        """
        MATCH (w:Workbook {id:$wb})
        OPTIONAL MATCH (w)-[:HAS_SHEET]->(s:Sheet)-[:CONTAINS]->(c:Cell)
        OPTIONAL MATCH (f:Finding {workbook:$wb})
        OPTIONAL MATCH (r:Run {workbook:$wb})
        DETACH DELETE w, s, c, f, r
        """,
        wb=workbook_id,
    )


def load_workbook(workbook_id: str, name: str, extracted: dict):
    """extracted = output of parser.extract.extract_workbook()."""
    ensure_schema()
    clear_workbook(workbook_id)

    def gid(local_id: str) -> str:
        return f"{workbook_id}::{local_id}"

    nodes = [
        {
            **n,
            "id": gid(n["id"]),
            "workbook": workbook_id,
            "literals": n.get("literals", []),
            "formula": n.get("formula"),
            # str() so mixed int/float/str survive the same property key
            "value": None if n.get("value") is None else str(n["value"]),
            "numValue": n["value"]
            if isinstance(n.get("value"), (int, float)) else None,
            "row": n.get("row"), "col": n.get("col"),
        }
        for n in extracted["nodes"]
    ]
    edges = [
        {"src": gid(e["src"]), "dst": gid(e["dst"])} for e in extracted["edges"]
    ]
    sheets = sorted({n["sheet"] for n in nodes})

    run("MERGE (w:Workbook {id:$wb}) SET w.name=$name", wb=workbook_id, name=name)
    run(
        """
        UNWIND $sheets AS s
        MERGE (sh:Sheet {id:$wb + '::' + s}) SET sh.name = s, sh.workbook = $wb
        WITH sh
        MATCH (w:Workbook {id:$wb}) MERGE (w)-[:HAS_SHEET]->(sh)
        """,
        sheets=sheets, wb=workbook_id,
    )
    run(
        """
        UNWIND $nodes AS n
        MERGE (c:Cell {id:n.id})
        SET c.sheet=n.sheet, c.address=n.address, c.row=n.row, c.col=n.col,
            c.kind=n.kind, c.formula=n.formula, c.value=n.value,
            c.numValue=n.numValue, c.literals=n.literals, c.workbook=n.workbook
        WITH c, n
        MATCH (sh:Sheet {id:n.workbook + '::' + n.sheet})
        MERGE (sh)-[:CONTAINS]->(c)
        """,
        nodes=nodes,
    )
    run(
        """
        UNWIND $edges AS e
        MATCH (a:Cell {id:e.src}), (b:Cell {id:e.dst})
        MERGE (a)-[:FEEDS_INTO]->(b)
        """,
        edges=edges,
    )
    return {"cells": len(nodes), "edges": len(edges), "sheets": len(sheets)}
