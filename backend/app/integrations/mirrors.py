"""Best-effort product-state mirrors."""

from __future__ import annotations

from ..models.integrations import IntegrationStatus


class NoopWorkbookMirror:
    provider = "butterbase-workbooks"

    def mirror(self, row: dict) -> IntegrationStatus:
        return IntegrationStatus.skipped(self.provider)


class ButterbaseWorkbookMirror:
    provider = "butterbase-workbooks"

    def mirror(self, row: dict) -> IntegrationStatus:
        from ..services.butterbase import upsert_workbook

        upsert_workbook(row)
        return IntegrationStatus.succeeded(self.provider)


class NoopAskHistoryMirror:
    provider = "butterbase-ask-history"

    def mirror(self, workbook_id: str, question: str, result: dict) -> IntegrationStatus:
        return IntegrationStatus.skipped(self.provider)


class ButterbaseAskHistoryMirror:
    provider = "butterbase-ask-history"

    def mirror(self, workbook_id: str, question: str, result: dict) -> IntegrationStatus:
        from ..services.butterbase import insert

        insert(
            "ask_history",
            {
                "user_id": "00000000-0000-0000-0000-000000000000",
                "workbook_id": workbook_id,
                "question": question,
                "answer": str(result.get("answer"))[:8000],
                "pipeline": result.get("source"),
            },
        )
        return IntegrationStatus.succeeded(self.provider)
