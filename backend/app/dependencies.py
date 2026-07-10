"""Application service construction."""

from __future__ import annotations

from dataclasses import dataclass

from .config import Settings
from .graph.db import configure as configure_neo4j
from .integrations.ask_clients import LocalAskClient, RocketRideAskClient
from .integrations.memory import CogneeMemoryStore, NoopMemoryStore
from .integrations.mirrors import (
    ButterbaseAskHistoryMirror,
    ButterbaseWorkbookMirror,
    NoopAskHistoryMirror,
    NoopWorkbookMirror,
)
from .integrations.semantic import DisabledSemanticAudit, LocalSemanticAudit
from .repositories.findings import FindingRepository
from .repositories.runs import RunRepository
from .repositories.workbooks import WorkbookGraphRepository
from .storage.workbook_store import LocalWorkbookStore
from .verification.runner import DefaultVerificationRunner
from .workflows.ask import AskWorkflow
from .workflows.ingestion import WorkbookIngestion
from .workflows.queries import WorkbookQueries
from .workflows.verification import FindingVerifier


@dataclass
class AppServices:
    ingestion: WorkbookIngestion
    queries: WorkbookQueries
    verifier: FindingVerifier
    ask: AskWorkflow


def build_services(settings: Settings) -> AppServices:
    configure_neo4j(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        database=settings.neo4j_database,
    )

    store = LocalWorkbookStore(settings.data_dir)
    workbooks = WorkbookGraphRepository()
    findings = FindingRepository()
    runs = RunRepository()

    semantic = LocalSemanticAudit() if settings.semantic_audit_enabled else DisabledSemanticAudit()
    workbook_mirror = (
        ButterbaseWorkbookMirror() if settings.butterbase_enabled else NoopWorkbookMirror()
    )
    ask_history_mirror = (
        ButterbaseAskHistoryMirror() if settings.butterbase_enabled else NoopAskHistoryMirror()
    )
    memory = CogneeMemoryStore() if settings.cognee_enabled else NoopMemoryStore()
    cloud_ask = RocketRideAskClient() if settings.rocketride_enabled else None
    local_ask = LocalAskClient(settings.data_dir) if settings.allow_local_agent else None

    return AppServices(
        ingestion=WorkbookIngestion(
            store=store,
            workbooks=workbooks,
            findings=findings,
            semantic_audit=semantic,
            workbook_mirror=workbook_mirror,
        ),
        queries=WorkbookQueries(workbooks=workbooks, findings=findings),
        verifier=FindingVerifier(
            store=store,
            findings=findings,
            runs=runs,
            runner=DefaultVerificationRunner(
                use_daytona=settings.daytona_enabled,
                allow_local_fallback=settings.allow_local_verification
            ),
            memory=memory,
        ),
        ask=AskWorkflow(
            cloud_client=cloud_ask,
            local_client=local_ask,
            ask_history_mirror=ask_history_mirror,
            allow_local_agent=settings.allow_local_agent,
            expose_fallback_reason=settings.expose_fallback_reason,
        ),
    )
