"""Semantic audit adapters."""

from __future__ import annotations

from ..models.integrations import IntegrationStatus


class DisabledSemanticAudit:
    provider = "butterbase-llm-semantic-audit"

    def run(self, workbook_id: str) -> tuple[list[dict], IntegrationStatus]:
        return [], IntegrationStatus.skipped(self.provider)


class LocalSemanticAudit:
    provider = "butterbase-llm-semantic-audit"

    def run(self, workbook_id: str) -> tuple[list[dict], IntegrationStatus]:
        from ..audit.agent import semantic_audit

        findings = semantic_audit(workbook_id)
        return findings, IntegrationStatus.succeeded(self.provider)
