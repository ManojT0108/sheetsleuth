"""Deterministic fix proposals for finding types where structure alone
determines the correction. Semantic cases (e.g. off-by-one references) are
proposed by the LLM audit agent instead; both paths feed the same verifier.
"""

import re

from openpyxl.utils import column_index_from_string, get_column_letter

from ..graph.db import run

# A1-style ref: optional $ on col/row. Negative lookahead avoids function
# names like LOG10( and sheet-name references like 'FY26'! or FY26!A1.
REF_RE = re.compile(r"(\$?)([A-Z]{1,3})(\$?)(\d+)(?![A-Z0-9_('!])")


def translate_formula(formula: str, col_delta: int, row_delta: int = 0) -> str:
    """Shift relative references in an A1 formula, like Excel drag-fill."""
    def shift(m: re.Match) -> str:
        cd, col, rd, row = m.groups()
        if not cd and col_delta:
            col = get_column_letter(column_index_from_string(col) + col_delta)
        if not rd and row_delta:
            row = str(int(row) + row_delta)
        return f"{cd}{col}{rd}{row}"

    return REF_RE.sub(shift, formula)


def _cell(cell_id: str) -> dict:
    return run("MATCH (c:Cell {id:$id}) RETURN c{.*} AS c", id=cell_id)[0]["c"]


def _nearest_formula_sibling(cell_id: str) -> dict | None:
    rows = run(
        """
        MATCH (c:Cell {id:$id})
        MATCH (s:Cell {workbook:c.workbook, sheet:c.sheet, row:c.row,
                       kind:'formula'})
        WHERE s.col <> c.col
        RETURN s{.*} AS s, abs(s.col - c.col) AS dist
        ORDER BY dist LIMIT 1
        """,
        id=cell_id,
    )
    return rows[0]["s"] if rows else None


def propose(finding: dict) -> dict | None:
    """Return {cell_local_id: fixed_formula} or None if the fix is semantic
    (LLM's job) or purely advisory."""
    ftype = finding["type"]

    if ftype in ("hardcoded-constant-in-chain", "stale-pasted-constant"):
        # restore drag-fill consistency with the nearest formula sibling
        fixes = {}
        for cid in finding["cells"]:
            cell = _cell(cid)
            sib = _nearest_formula_sibling(cid)
            if not sib:
                return None
            fixes[f"{cell['sheet']}!{cell['address']}"] = translate_formula(
                sib["formula"], cell["col"] - sib["col"])
        return fixes

    if ftype == "short-sum-range":
        # extend SUM(X3:X6) to cover everything up to the row above the total
        fixes = {}
        for cid in finding["cells"]:
            cell = _cell(cid)
            new_end = cell["row"] - 1
            fixed = re.sub(
                r"SUM\((\$?[A-Z]{1,3}\$?\d+):(\$?[A-Z]{1,3})\$?\d+\)",
                rf"SUM(\1:\g<2>{new_end})",
                cell["formula"],
            )
            if fixed == cell["formula"]:
                return None
            fixes[f"{cell['sheet']}!{cell['address']}"] = fixed
        return fixes

    return None  # orphaned-assumption / circular-reference / semantic types
