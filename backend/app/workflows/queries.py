"""Workbook query use cases."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WorkbookQueries:
    workbooks: object
    findings: object

    def graph(self, workbook_id: str) -> dict:
        return self.workbooks.graph(workbook_id)

    def findings_for_workbook(self, workbook_id: str) -> list[dict]:
        return self.findings.list_for_workbook(workbook_id)

    def critical_cells(self, workbook_id: str) -> list[dict]:
        return self.workbooks.critical_cells(workbook_id)

    def blast_radius(self, workbook_id: str, sheet: str, address: str) -> dict:
        return self.workbooks.blast_radius(workbook_id, sheet, address)

    def health(self) -> dict:
        return {"ok": True, "neo4j": self.workbooks.health_check()}
