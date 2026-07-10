"""Workbook ingestion use case."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from ..logger import get_logger
from ..models.integrations import IntegrationStatus
from ..models.workbook import IngestResult
from ..parser.extract import extract_workbook

log = get_logger(__name__)


def workbook_id_for(raw: bytes, original_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", original_name.lower())
    slug = slug.removesuffix("-xlsx").strip("-")[:40] or "workbook"
    return f"{slug}-{hashlib.sha1(raw).hexdigest()[:8]}"


@dataclass
class WorkbookIngestion:
    store: object
    workbooks: object
    findings: object
    semantic_audit: object
    workbook_mirror: object

    def ingest(self, raw: bytes, original_name: str) -> IngestResult:
        workbook_id = workbook_id_for(raw, original_name)
        path = self.store.save(workbook_id, raw)
        stats = self.workbooks.replace_graph(
            workbook_id, original_name, extract_workbook(path)
        )
        detected = self.findings.audit_structural(workbook_id)

        semantic_status = IntegrationStatus.skipped("butterbase-llm-semantic-audit")
        try:
            semantic_findings, semantic_status = self.semantic_audit.run(workbook_id)
            detected += semantic_findings
        except Exception as exc:
            semantic_status = IntegrationStatus.failed(
                "butterbase-llm-semantic-audit", exc
            )
            log.warning("semantic audit failed", extra={"workbook": workbook_id}, exc_info=exc)

        mirror_status = IntegrationStatus.skipped("butterbase-workbooks")
        try:
            mirror_status = self.workbook_mirror.mirror(
                {
                    "id": workbook_id,
                    "name": original_name,
                    "user_id": "00000000-0000-0000-0000-000000000000",
                    "cells": stats.cells,
                    "edges": stats.edges,
                    "sheets": stats.sheets,
                    "findings_count": len(detected),
                }
            )
        except Exception as exc:
            mirror_status = IntegrationStatus.failed("butterbase-workbooks", exc)
            log.warning("workbook mirror failed", extra={"workbook": workbook_id}, exc_info=exc)

        return IngestResult(
            workbook=workbook_id,
            name=original_name,
            stats=stats,
            findings=len(detected),
            semantic_audit=semantic_status,
            workbook_mirror=mirror_status,
        )

    def ingest_demo(self, raw: bytes) -> IngestResult:
        return self.ingest(raw, "Lumeo Analytics FY2026 (demo)")
