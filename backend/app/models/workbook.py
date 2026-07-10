"""Workbook use-case result models."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .integrations import IntegrationStatus


@dataclass(frozen=True)
class GraphStats:
    cells: int
    edges: int
    sheets: int

    @classmethod
    def from_dict(cls, data: dict) -> "GraphStats":
        return cls(
            cells=int(data.get("cells", 0)),
            edges=int(data.get("edges", 0)),
            sheets=int(data.get("sheets", 0)),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class IngestResult:
    workbook: str
    name: str
    stats: GraphStats
    findings: int
    semantic_audit: IntegrationStatus
    workbook_mirror: IntegrationStatus

    def to_public_dict(self) -> dict:
        return {
            "workbook": self.workbook,
            "name": self.name,
            **self.stats.to_dict(),
            "findings": self.findings,
            "integrations": {
                "semanticAudit": self.semantic_audit.to_dict(),
                "workbookMirror": self.workbook_mirror.to_dict(),
            },
        }
