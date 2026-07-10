"""Neo4j-backed workbook graph repository."""

from __future__ import annotations

from ..graph import queries as q
from ..graph.db import run as cypher
from ..graph.loader import clear_workbook, load_workbook
from ..models.workbook import GraphStats


class WorkbookGraphRepository:
    def replace_graph(self, workbook_id: str, name: str, extracted: dict) -> GraphStats:
        return GraphStats.from_dict(load_workbook(workbook_id, name, extracted))

    def clear(self, workbook_id: str) -> None:
        clear_workbook(workbook_id)

    def graph(self, workbook_id: str) -> dict:
        nodes = cypher(
            """
            MATCH (c:Cell {workbook:$wb})
            OPTIONAL MATCH (f:Finding)-[:AFFECTS]->(c)
            RETURN c{.id, .sheet, .address, .kind, .row, .col, .formula, .value}
                   AS cell, collect(f{.id, .type, .status})[0] AS finding
            """,
            wb=workbook_id,
        )
        edges = cypher(
            """
            MATCH (a:Cell {workbook:$wb})-[:FEEDS_INTO]->(b:Cell)
            RETURN a.id AS src, b.id AS dst
            """,
            wb=workbook_id,
        )
        return {"nodes": nodes, "edges": edges}

    def critical_cells(self, workbook_id: str) -> list[dict]:
        return q.critical_cells(workbook_id)

    def blast_radius(self, workbook_id: str, sheet: str, address: str) -> dict:
        return q.blast_radius(f"{workbook_id}::{sheet}!{address}")

    def health_check(self) -> bool:
        try:
            cypher("RETURN 1 AS ok")
            return True
        except Exception:
            return False
