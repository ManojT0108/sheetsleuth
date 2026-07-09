"""RocketRide Cloud client — the app's Ask flow invokes the deployed
sheetsleuth_agent pipeline on cloud.rocketride.ai (mandatory requirement:
a managed production endpoint the app calls).

The pipeline hosts the reasoning agent: LLM via the Butterbase gateway,
db_neo4j tool doing text-to-Cypher against Neo4j Aura, an HTTP tool that
calls back into this backend for sandbox-executed what-ifs, and internal
memory. Local direct-agent path remains as a resilience fallback.
"""

import asyncio
import os
from pathlib import Path

PIPE_PATH = Path(__file__).parents[3] / "pipelines" / "sheetsleuth_agent.pipe"


def _pipe_project_id() -> str:
    import json
    return json.loads(PIPE_PATH.read_text())["project_id"]


async def _ask_cloud(wb: str, question: str) -> dict:
    from rocketride import RocketRideClient
    from rocketride.schema import Question

    client = RocketRideClient()
    await client.connect()
    try:
        # reuse the already-running deployed pipeline; deploy if absent
        token = await client.get_task_token(_pipe_project_id(), "chat_1")
        if not token:
            result = await client.use(filepath=str(PIPE_PATH))
            token = result["token"]
        q = Question()
        q.addQuestion(
            f"(Context: the workbook id is '{wb}'.) {question}")
        resp = await client.chat(token=token, question=q)
        answers = resp.get("answers") or []
        return {
            "answer": answers[0] if answers else str(resp),
            "source": "rocketride-cloud",
            "pipeline": "sheetsleuth_agent.pipe (attached)" if token else
                        "sheetsleuth_agent.pipe (deployed)",
        }
    finally:
        await client.disconnect()


def ask_agent(wb: str, question: str) -> dict:
    if os.environ.get("ROCKETRIDE_APIKEY"):
        try:
            result = asyncio.run(_ask_cloud(wb, question))
            _mirror_ask(wb, question, result)
            return {"question": question, **result}
        except Exception as e:
            fallback_reason = f"{type(e).__name__}: {str(e)[:120]}"
    else:
        fallback_reason = "ROCKETRIDE_APIKEY not configured"

    from ..audit.agent import answer
    result = {"question": question, **answer(wb, question),
              "cloudFallback": fallback_reason}
    _mirror_ask(wb, question, result)
    return result


def _mirror_ask(wb: str, question: str, result: dict):
    try:
        from .butterbase import insert
        insert("ask_history", {
            "user_id": "00000000-0000-0000-0000-000000000000",
            "workbook_id": wb,
            "question": question,
            "answer": str(result.get("answer"))[:8000],
            "pipeline": result.get("source"),
        })
    except Exception:
        pass
