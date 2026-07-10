"""Finding verification use case."""

from __future__ import annotations

from dataclasses import dataclass

from ..audit import fixes as fx
from ..errors import FindingNotFound, NoDeterministicFix
from ..logger import get_logger
from ..models.integrations import IntegrationStatus

log = get_logger(__name__)


@dataclass
class FindingVerifier:
    store: object
    findings: object
    runs: object
    runner: object
    memory: object

    def verify(self, finding_id: str) -> dict:
        finding = self.findings.get(finding_id)
        if not finding:
            raise FindingNotFound("finding not found")

        proposal = fx.propose(finding)
        if proposal is None:
            raise NoDeterministicFix("no deterministic fix; use the agent (/ask)")

        workbook_id = finding_id.split("::")[0]
        outcome = self.runner.run(self.store.path_for(workbook_id), proposal)
        run = self.runs.record_verification(
            finding_id=finding["id"],
            runner=outcome.runner,
            verdict=outcome.verdict,
            fixes=proposal,
            seconds=outcome.seconds,
        )
        result = {"runId": run.id, "runner": outcome.runner, **outcome.verdict}

        memory_status = IntegrationStatus.skipped("cognee-memory")
        if result.get("verdict") == "CONFIRMED":
            try:
                memory_status = self.memory.remember_verified(workbook_id, finding, result)
            except Exception as exc:
                memory_status = IntegrationStatus.failed("cognee-memory", exc)
                log.warning(
                    "memory write failed",
                    extra={"workbook": workbook_id, "finding": finding_id},
                    exc_info=exc,
                )

        result["integrations"] = {"memory": memory_status.to_dict()}
        return result
