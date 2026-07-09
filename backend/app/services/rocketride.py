"""Client for the SheetSleuth audit-agent pipeline on RocketRide Cloud.

The deployed pipeline receives a question + workbook id, generates Cypher,
traverses Neo4j, and reasons over the results. Until the cloud endpoint is
configured (ROCKETRIDE_ENDPOINT / ROCKETRIDE_API_KEY), we return graph facts
directly so the UI stays functional during development.
"""

import os

import requests

from ..audit import smells
from ..graph import queries as q


def ask_agent(wb: str, question: str) -> dict:
    endpoint = os.environ.get("ROCKETRIDE_ENDPOINT")
    if endpoint:
        resp = requests.post(
            endpoint,
            json={"question": question, "workbook": wb},
            headers={"Authorization": f"Bearer {os.environ.get('ROCKETRIDE_API_KEY', '')}"},
            timeout=120,
        )
        resp.raise_for_status()
        return {"source": "rocketride-cloud", **resp.json()}

    # Dev fallback: no LLM, just structured graph facts.
    confirmed = [f for f in smells.get_findings(wb)
                 if f["status"] == "CONFIRMED"]
    return {
        "source": "dev-fallback (RocketRide endpoint not configured)",
        "question": question,
        "answer": None,
        "facts": {
            "confirmedFindings": [f["summary"] for f in confirmed],
            "criticalCells": q.critical_cells(wb, 5),
        },
    }
