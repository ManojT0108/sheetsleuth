"""Ask-agent adapters."""

from __future__ import annotations

from pathlib import Path


class RocketRideAskClient:
    async_capable = True

    def ask(self, workbook_id: str, question: str) -> dict:
        from ..services.rocketride import ask_cloud

        return ask_cloud(workbook_id, question)


class LocalAskClient:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir

    def ask(self, workbook_id: str, question: str) -> dict:
        from ..audit.agent import answer

        return answer(workbook_id, question, data_dir=self.data_dir)
