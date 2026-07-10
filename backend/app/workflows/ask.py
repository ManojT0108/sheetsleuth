"""Ask-agent use case."""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import IntegrationUnavailable
from ..logger import get_logger
from ..models.integrations import IntegrationStatus

log = get_logger(__name__)


@dataclass
class AskWorkflow:
    cloud_client: object | None
    local_client: object | None
    ask_history_mirror: object
    allow_local_agent: bool = True
    expose_fallback_reason: bool = True

    def ask(self, workbook_id: str, question: str) -> dict:
        question = question or ""
        fallback_reason = None

        if self.cloud_client is not None:
            try:
                result = {"question": question, **self.cloud_client.ask(workbook_id, question)}
                self._mirror(workbook_id, question, result)
                return result
            except Exception as exc:
                fallback_reason = f"{type(exc).__name__}: {str(exc)[:120]}"
                log.warning(
                    "rocketride ask failed",
                    extra={"workbook": workbook_id},
                    exc_info=exc,
                )
        else:
            fallback_reason = "ROCKETRIDE_APIKEY not configured"

        if not self.allow_local_agent or self.local_client is None:
            raise IntegrationUnavailable(f"ask agent unavailable: {fallback_reason}")

        result = {"question": question, **self.local_client.ask(workbook_id, question)}
        if self.expose_fallback_reason:
            result["cloudFallback"] = fallback_reason
        self._mirror(workbook_id, question, result)
        return result

    def _mirror(self, workbook_id: str, question: str, result: dict) -> IntegrationStatus:
        try:
            status = self.ask_history_mirror.mirror(workbook_id, question, result)
        except Exception as exc:
            status = IntegrationStatus.failed("butterbase-ask-history", exc)
            log.warning("ask mirror failed", extra={"workbook": workbook_id}, exc_info=exc)
        result.setdefault("integrations", {})["askHistoryMirror"] = status.to_dict()
        return status
