"""Finding persistence and structural-audit repository."""

from __future__ import annotations

from ..audit import smells


class FindingRepository:
    def audit_structural(self, workbook_id: str) -> list[dict]:
        return smells.audit(workbook_id)

    def list_for_workbook(self, workbook_id: str) -> list[dict]:
        return smells.get_findings(workbook_id)

    def get(self, finding_id: str) -> dict | None:
        workbook_id = finding_id.split("::")[0]
        return next(
            (f for f in self.list_for_workbook(workbook_id) if f["id"] == finding_id),
            None,
        )
