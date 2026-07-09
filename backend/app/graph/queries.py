"""Smell-detector and analysis Cypher queries — the Neo4j heart of SheetSleuth.

Each detector returns CANDIDATE findings; the audit agent triages them and the
verification engine proves impact by re-executing the workbook in a sandbox.
Every query here is a genuine graph traversal — none of this is expressible
as a SQL join over a cells table.
"""

from .db import run

TRIVIAL_LITERALS = [0.0, 1.0, 12.0]  # ROUND digits, (1+x) algebra, months/year


def hardcoded_constants(wb: str) -> list[dict]:
    """Formula cells mixing cell refs with non-trivial numeric literals —
    magic numbers buried inside dependency chains — ranked by blast radius."""
    return run(
        """
        MATCH (c:Cell {workbook:$wb, kind:'formula'})
        WHERE size([l IN c.literals WHERE NOT l IN $trivial]) > 0
          AND EXISTS { MATCH (:Cell)-[:FEEDS_INTO]->(c) }
        CALL (c) {
            MATCH (c)-[:FEEDS_INTO*1..]->(d:Cell)
            RETURN count(DISTINCT d) AS blast
        }
        RETURN c.id AS cell, c.sheet AS sheet, c.address AS address,
               c.formula AS formula,
               [l IN c.literals WHERE NOT l IN $trivial] AS suspects,
               blast
        ORDER BY blast DESC
        """,
        wb=wb, trivial=TRIVIAL_LITERALS,
    )


def inconsistent_siblings(wb: str) -> list[dict]:
    """A static number sitting inside a row of formulas — the classic
    'pasted over the formula during board prep' failure."""
    return run(
        """
        MATCH (c:Cell {workbook:$wb, kind:'number'})
        MATCH (s:Cell {workbook:$wb, sheet:c.sheet, row:c.row, kind:'formula'})
        WITH c, collect(s) AS sibs, min(s.col) AS minCol, max(s.col) AS maxCol
        WHERE size(sibs) >= 3 AND minCol < c.col < maxCol
        CALL (c) {
            MATCH (c)-[:FEEDS_INTO*1..]->(d:Cell)
            RETURN count(DISTINCT d) AS blast
        }
        RETURN c.id AS cell, c.sheet AS sheet, c.address AS address,
               c.numValue AS value, size(sibs) AS formulaSiblings,
               sibs[0].formula AS siblingFormula, blast
        """,
        wb=wb,
    )


def short_aggregation_ranges(wb: str) -> list[dict]:
    """Vertical SUM totals that stop short of populated cells directly
    between the range end and the total row — rows added after the total."""
    return run(
        """
        MATCH (t:Cell {workbook:$wb, kind:'formula'})
        WHERE t.formula CONTAINS 'SUM('
        MATCH (p:Cell)-[:FEEDS_INTO]->(t)
        WITH t, collect(p) AS ps, max(p.row) AS lastRow
        WHERE size(ps) >= 2
          AND all(x IN ps WHERE x.sheet = t.sheet AND x.col = t.col)
        WITH t, lastRow
        MATCH (gap:Cell {workbook:$wb, sheet:t.sheet, col:t.col})
        WHERE gap.row > lastRow AND gap.row < t.row
          AND gap.kind IN ['number','formula']
          AND NOT (gap)-[:FEEDS_INTO]->(t)
        RETURN t.id AS cell, t.sheet AS sheet, t.address AS address,
               t.formula AS formula, collect(gap.id) AS missedCells,
               sum(coalesce(gap.numValue, 0)) AS missedStaticValue
        """,
        wb=wb,
    )


def orphaned_inputs(wb: str) -> list[dict]:
    """Labeled numeric inputs that feed nothing, on sheets where sibling
    inputs in the same column do feed the model — assumptions the author
    believes are wired in but aren't."""
    return run(
        """
        MATCH (c:Cell {workbook:$wb, kind:'number'})
        WHERE NOT (c)-[:FEEDS_INTO]->()
        MATCH (lbl:Cell {workbook:$wb, sheet:c.sheet, row:c.row, kind:'text'})
        WHERE lbl.col = c.col - 1
        MATCH (n:Cell {workbook:$wb, sheet:c.sheet, col:c.col, kind:'number'})
        WHERE n.row <> c.row AND (n)-[:FEEDS_INTO]->()
        RETURN DISTINCT c.id AS cell, c.sheet AS sheet, c.address AS address,
               c.numValue AS value, lbl.value AS label
        """,
        wb=wb,
    )


def circular_references(wb: str) -> list[dict]:
    return run(
        """
        MATCH p = (c:Cell {workbook:$wb})-[:FEEDS_INTO*1..8]->(c)
        RETURN DISTINCT c.id AS cell,
               [n IN nodes(p) | n.id] AS cycle
        LIMIT 25
        """,
        wb=wb,
    )


def blast_radius(cell_id: str) -> dict:
    rows = run(
        """
        MATCH p = (c:Cell {id:$id})-[:FEEDS_INTO*1..]->(d:Cell)
        RETURN d.id AS cell, d.sheet AS sheet, min(length(p)) AS hops
        ORDER BY hops, cell
        """,
        id=cell_id,
    )
    return {
        "source": cell_id,
        "cells": rows,
        "count": len(rows),
        "maxHops": max((r["hops"] for r in rows), default=0),
        "sheetsReached": sorted({r["sheet"] for r in rows}),
    }


def critical_cells(wb: str, limit: int = 10) -> list[dict]:
    """Load-bearing cells ranked by how much of the workbook depends on them."""
    return run(
        """
        MATCH (c:Cell {workbook:$wb})
        WHERE c.kind IN ['formula','number']
        CALL (c) {
            MATCH (c)-[:FEEDS_INTO*1..]->(d:Cell)
            RETURN count(DISTINCT d) AS reach
        }
        WITH c, reach WHERE reach > 0
        RETURN c.id AS cell, c.sheet AS sheet, c.address AS address,
               c.kind AS kind, reach
        ORDER BY reach DESC LIMIT $limit
        """,
        wb=wb, limit=limit,
    )


def cell_context(cell_id: str) -> dict:
    """Nearby labels (row label to the left, column header above) so the
    LLM can reason about a cell's semantic meaning."""
    rows = run(
        """
        MATCH (c:Cell {id:$id})
        OPTIONAL MATCH (rl:Cell {workbook:c.workbook, sheet:c.sheet,
                                 row:c.row, kind:'text'})
        WHERE rl.col < c.col
        WITH c, rl ORDER BY rl.col DESC
        WITH c, collect(rl.value)[0] AS rowLabel
        OPTIONAL MATCH (ch:Cell {workbook:c.workbook, sheet:c.sheet,
                                 col:c.col, kind:'text'})
        WHERE ch.row < c.row
        WITH c, rowLabel, ch ORDER BY ch.row DESC
        RETURN c.id AS cell, c.formula AS formula, c.value AS value,
               rowLabel, collect(ch.value)[0] AS colHeader
        """,
        id=cell_id,
    )
    return rows[0] if rows else {}
