"""Agent memory adapters."""

from __future__ import annotations

import threading

from ..models.integrations import IntegrationStatus


class NoopMemoryStore:
    provider = "cognee-memory"

    def remember_verified(self, workbook_id: str, finding: dict, result: dict) -> IntegrationStatus:
        return IntegrationStatus.skipped(self.provider)


class CogneeMemoryStore:
    provider = "cognee-memory"

    def remember_verified(self, workbook_id: str, finding: dict, result: dict) -> IntegrationStatus:
        def _memorize() -> None:
            from ..services.cognee_mem import remember_sync

            top = (result.get("topDeltas") or [{}])[0]
            remember_sync(
                f"Verified finding in workbook {workbook_id}: {finding['summary']} "
                f"Verdict CONFIRMED by sandbox run ({result.get('runner')}), "
                f"{result.get('cellsChanged')} cells changed, top impact "
                f"{top.get('label')} {top.get('before')} -> {top.get('after')}."
            )

        threading.Thread(target=_memorize, daemon=True).start()
        return IntegrationStatus.succeeded(self.provider)
