"""Cognee OSS — the agent's long-term memory (bonus track).

Configuration (env, set in .env):
  - Graph store: our Neo4j Aura instance (GRAPH_DATABASE_PROVIDER=neo4j)
  - LLM + embeddings: routed through the Butterbase AI gateway
    (OpenAI-compatible custom endpoint)

What we remember: every audit (findings + verdicts), every proven what-if,
and user decisions. On later sessions the agent recalls this context, so a
returning workbook gets smarter answers ("this model had the same short-SUM
bug last quarter").
"""

import asyncio
import os

_configured = False


def _configure():
    global _configured
    if _configured:
        return
    key = os.environ.get("BUTTERBASE_API_KEY", "")
    app = os.environ.get("BUTTERBASE_APP_ID", "")
    base = f"https://api.butterbase.ai/v1/{app}"
    # single-tenant: Aura Free has one database (no CREATE DATABASE perms)
    os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "false")
    os.environ.setdefault("REQUIRE_AUTHENTICATION", "false")
    os.environ.setdefault("LLM_PROVIDER", "custom")
    os.environ.setdefault("LLM_MODEL", "openai/anthropic/claude-haiku-4.5")
    os.environ.setdefault("LLM_ENDPOINT", base)
    os.environ.setdefault("LLM_API_KEY", key)
    # local embeddings (gateway embedding models were flaky at build time)
    os.environ.setdefault("EMBEDDING_PROVIDER", "fastembed")
    os.environ.setdefault("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    os.environ.setdefault("EMBEDDING_DIMENSIONS", "384")
    os.environ.setdefault("EMBEDDING_MAX_TOKENS", "256")
    # Cognee's knowledge graph lives in its own Neo4j so its entity graph
    # and our audit graph don't collide (COGNEE_NEO4J_* overrides in .env)
    os.environ.setdefault("GRAPH_DATABASE_PROVIDER", "neo4j")
    os.environ.setdefault("GRAPH_DATABASE_URL",
                          os.environ.get("COGNEE_NEO4J_URI",
                                         "bolt://localhost:7687"))
    os.environ.setdefault("GRAPH_DATABASE_USERNAME",
                          os.environ.get("COGNEE_NEO4J_USER", "neo4j"))
    os.environ.setdefault("GRAPH_DATABASE_PASSWORD",
                          os.environ.get("COGNEE_NEO4J_PASSWORD",
                                         "sheetsleuth123"))
    os.environ.setdefault("GRAPH_DATABASE_NAME", "neo4j")
    _configured = True


async def remember(text: str, dataset: str = "sheetsleuth"):
    """Store an audit event in the agent's memory and index it."""
    _configure()
    import cognee
    await cognee.add(text, dataset_name=dataset)
    await cognee.cognify(datasets=[dataset])


async def recall(query: str) -> list[str]:
    """Retrieve relevant memories for a query."""
    _configure()
    import cognee
    try:
        results = await cognee.search(query_text=query)
        return [str(r) for r in results][:5]
    except Exception:
        return []


def remember_verdict_async(wb: str, finding: dict, result: dict):
    """Fire-and-forget: record a CONFIRMED verdict in long-term memory
    without blocking the API response."""
    import logging
    import threading

    def _memorize():
        try:
            top = (result.get("topDeltas") or [{}])[0]
            remember_sync(
                f"Verified finding in workbook {wb}: {finding['summary']} "
                f"Verdict CONFIRMED by sandbox run ({result.get('runner')}), "
                f"{result.get('cellsChanged')} cells changed, top impact "
                f"{top.get('label')} {top.get('before')} -> {top.get('after')}."
            )
        except Exception:
            logging.getLogger("sheetsleuth").warning(
                "cognee memorization failed", exc_info=True)

    threading.Thread(target=_memorize, daemon=True).start()


def remember_sync(text: str):
    try:
        asyncio.run(remember(text))
    except RuntimeError:  # already inside an event loop
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(remember(text))
        finally:
            loop.close()


def recall_sync(query: str) -> list[str]:
    try:
        return asyncio.run(recall(query))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(recall(query))
        finally:
            loop.close()
