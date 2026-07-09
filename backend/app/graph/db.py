"""Neo4j connection helper. Env-driven so local Docker and Aura are a
one-variable swap (NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD)."""

import os

from neo4j import GraphDatabase

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            auth=(
                os.environ.get("NEO4J_USER", "neo4j"),
                os.environ.get("NEO4J_PASSWORD", "sheetsleuth123"),
            ),
        )
    return _driver


def run(query: str, **params) -> list[dict]:
    with get_driver().session() as session:
        return [dict(r) for r in session.run(query, **params)]
