"""Verification run persistence."""

from __future__ import annotations

import json
import uuid

from ..graph.db import run as cypher
from ..models.verification import RunRecord


class RunRepository:
    def record_verification(
        self,
        finding_id: str,
        runner: str,
        verdict: dict,
        fixes: dict,
        seconds: float,
    ) -> RunRecord:
        run_id = f"run-{uuid.uuid4().hex[:10]}"
        verdict_name = verdict.get("verdict")
        cells_changed = verdict.get("cellsChanged", 0)
        max_delta = verdict.get("maxAbsDelta", 0.0)
        cypher(
            """
            MATCH (f:Finding {id:$fid})
            CREATE (r:Run {id:$rid, workbook:f.workbook, runner:$runner,
                           verdict:$verdict, cellsChanged:$changed,
                           maxAbsDelta:$maxDelta, fixes:$fixes,
                           topDeltas:$topDeltas, seconds:$secs, ts:timestamp()})
            CREATE (r)-[:VERIFIES]->(f)
            SET f.status = CASE $verdict WHEN 'CONFIRMED' THEN 'CONFIRMED'
                           WHEN 'NO_IMPACT' THEN 'NO_IMPACT' ELSE f.status END,
                f.maxAbsDelta = $maxDelta, f.cellsChanged = $changed
            """,
            fid=finding_id,
            rid=run_id,
            runner=runner,
            verdict=verdict_name,
            changed=cells_changed,
            maxDelta=max_delta,
            fixes=json.dumps(fixes),
            topDeltas=json.dumps(verdict.get("topDeltas", []))[:8000],
            secs=round(seconds, 2),
        )
        return RunRecord(
            id=run_id,
            runner=runner,
            verdict=verdict_name,
            cells_changed=cells_changed,
            max_abs_delta=max_delta,
        )
