"""Verification use-case models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunnerOutcome:
    verdict: dict
    runner: str
    seconds: float


@dataclass(frozen=True)
class RunRecord:
    id: str
    runner: str
    verdict: str | None
    cells_changed: int
    max_abs_delta: float
