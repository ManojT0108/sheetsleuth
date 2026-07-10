"""Runtime configuration for SheetSleuth.

Environment is read here at app construction time. Lower-level modules receive
settings or adapters instead of reaching into process env from route handlers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).parents[2]


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    frontend_dist: Path
    demo_workbook: Path
    cors_origins: tuple[str, ...]
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_database: str
    semantic_audit_enabled: bool
    butterbase_enabled: bool
    butterbase_app_id: str | None
    daytona_enabled: bool
    rocketride_enabled: bool
    cognee_enabled: bool
    allow_local_verification: bool
    allow_local_agent: bool
    expose_fallback_reason: bool

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Settings":
        load_dotenv(env_file or ROOT / ".env")

        data_dir = Path(os.environ.get("SHEETSLEUTH_DATA_DIR", ROOT / "backend" / "data"))
        frontend_dist = Path(
            os.environ.get("SHEETSLEUTH_FRONTEND_DIST", ROOT / "frontend" / "dist")
        )
        demo_workbook = Path(
            os.environ.get(
                "SHEETSLEUTH_DEMO_WORKBOOK",
                ROOT / "demo" / "lumeo_fy2026_model.xlsx",
            )
        )
        cors = tuple(
            p.strip()
            for p in os.environ.get("SHEETSLEUTH_CORS_ORIGINS", "*").split(",")
            if p.strip()
        )

        butterbase_key_present = bool(os.environ.get("BUTTERBASE_API_KEY"))
        rocketride_key_present = bool(os.environ.get("ROCKETRIDE_APIKEY"))
        daytona_key_present = bool(os.environ.get("DAYTONA_API_KEY"))

        return cls(
            data_dir=data_dir,
            frontend_dist=frontend_dist,
            demo_workbook=demo_workbook,
            cors_origins=cors or ("*",),
            neo4j_uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_user=os.environ.get("NEO4J_USER", "neo4j"),
            neo4j_password=os.environ.get("NEO4J_PASSWORD", "sheetsleuth123"),
            neo4j_database=os.environ.get("NEO4J_DATABASE", "neo4j"),
            semantic_audit_enabled=not _bool_env("SHEETSLEUTH_SKIP_SEMANTIC", False)
            and _bool_env("SHEETSLEUTH_SEMANTIC_AUDIT", True),
            butterbase_enabled=_bool_env("SHEETSLEUTH_BUTTERBASE_ENABLED", False),
            butterbase_app_id=os.environ.get("BUTTERBASE_APP_ID", "app_x89ezf73vxrn"),
            daytona_enabled=_bool_env("SHEETSLEUTH_DAYTONA_ENABLED", daytona_key_present),
            rocketride_enabled=_bool_env("SHEETSLEUTH_ROCKETRIDE_ENABLED", rocketride_key_present),
            cognee_enabled=_bool_env("SHEETSLEUTH_COGNEE_ENABLED", butterbase_key_present),
            allow_local_verification=_bool_env("SHEETSLEUTH_ALLOW_LOCAL_VERIFICATION", True),
            allow_local_agent=_bool_env("SHEETSLEUTH_ALLOW_LOCAL_AGENT", True),
            expose_fallback_reason=_bool_env("SHEETSLEUTH_EXPOSE_FALLBACK_REASON", True),
        )
