"""Neo4j connection helper."""

import os
from dataclasses import dataclass

from neo4j import GraphDatabase

_driver = None
_config = None


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str
    user: str
    password: str
    database: str


def _env_config() -> Neo4jConfig:
    return Neo4jConfig(
        uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        user=os.environ.get("NEO4J_USER", "neo4j"),
        password=os.environ.get("NEO4J_PASSWORD", "sheetsleuth123"),
        database=os.environ.get("NEO4J_DATABASE", "neo4j"),
    )


def configure(uri: str, user: str, password: str, database: str = "neo4j") -> None:
    """Configure the process-wide Neo4j client.

    The legacy graph modules still call ``run`` directly. App startup now owns
    the configuration, and command-line/demo scripts keep the env fallback.
    """
    global _config, _driver
    next_config = Neo4jConfig(uri=uri, user=user, password=password, database=database)
    if _config != next_config:
        if _driver is not None:
            _driver.close()
        _driver = None
        _config = next_config


def get_driver():
    global _driver
    config = _config or _env_config()
    if _driver is None:
        _driver = GraphDatabase.driver(
            config.uri,
            auth=(config.user, config.password),
        )
    return _driver


def run(query: str, **params) -> list[dict]:
    database = (_config or _env_config()).database
    with get_driver().session(database=database) as session:
        return [dict(r) for r in session.run(query, **params)]
