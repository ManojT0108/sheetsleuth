"""Small application-level integration result models."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class IntegrationStatus:
    provider: str
    attempted: bool
    ok: bool
    error: str | None = None

    @classmethod
    def skipped(cls, provider: str) -> "IntegrationStatus":
        return cls(provider=provider, attempted=False, ok=False)

    @classmethod
    def succeeded(cls, provider: str) -> "IntegrationStatus":
        return cls(provider=provider, attempted=True, ok=True)

    @classmethod
    def failed(cls, provider: str, error: Exception | str) -> "IntegrationStatus":
        message = str(error)
        return cls(provider=provider, attempted=True, ok=False, error=message[:500])

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class FallbackPolicy:
    allow_local_verification: bool
    allow_local_agent: bool
    expose_fallback_reason: bool
