"""Pure-unit tests: no Neo4j, no network, fast."""

from app.audit.agent import _extract_json
from app.audit.fixes import translate_formula


class TestTranslateFormula:
    def test_dragfill_shifts_relative_refs(self):
        src = "=ROUND(F3*(1+Assumptions!$B$3-Assumptions!$B$4),0)"
        assert translate_formula(src, 1) == \
            "=ROUND(G3*(1+Assumptions!$B$3-Assumptions!$B$4),0)"

    def test_anchored_refs_do_not_shift(self):
        assert translate_formula("=$B$3+$C4+D$5", 2) == "=$B$3+$C4+F$5"

    def test_row_delta(self):
        assert translate_formula("=A1+B2", 0, 3) == "=A4+B5"

    def test_numeric_literals_untouched(self):
        assert translate_formula("=B3*(1+0.15-12)", 1) == "=C3*(1+0.15-12)"

    def test_function_names_with_digits_survive(self):
        assert translate_formula("=LOG10(B3)", 1) == "=LOG10(C3)"

    def test_quoted_sheet_names_survive(self):
        assert translate_formula("='FY26'!A1+B2", 1) == "='FY26'!B1+C2"

    def test_bare_sheet_names_survive(self):
        assert translate_formula("=FY26!A1+B2", 1) == "=FY26!B1+C2"

    def test_range_shifts_both_ends(self):
        assert translate_formula("=SUM(B3:B6)", 1) == "=SUM(C3:C6)"


class TestExtractJson:
    def test_nested_braces(self):
        text = 'SCENARIO: {"changes": {"A!B1": 5}, "watch": ["A!C1"]}'
        assert _extract_json(text, "SCENARIO") == \
            {"changes": {"A!B1": 5}, "watch": ["A!C1"]}

    def test_prose_after_json(self):
        text = 'SCENARIO: {"changes": {"A!B1": 5}} and then some prose {'
        assert _extract_json(text, "SCENARIO") == {"changes": {"A!B1": 5}}

    def test_no_anchor_returns_none(self):
        assert _extract_json("no json here", "SCENARIO") is None

    def test_malformed_returns_none(self):
        assert _extract_json("SCENARIO: {broken", "SCENARIO") is None
