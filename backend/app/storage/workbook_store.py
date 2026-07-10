"""Workbook file storage."""

from __future__ import annotations

from pathlib import Path

from ..errors import WorkbookNotFound


class LocalWorkbookStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def save(self, workbook_id: str, raw: bytes) -> Path:
        path = self.data_dir / f"{workbook_id}.xlsx"
        path.write_bytes(raw)
        return path

    def path_for(self, workbook_id: str) -> Path:
        path = self.data_dir / f"{workbook_id}.xlsx"
        if not path.exists():
            raise WorkbookNotFound(f"workbook {workbook_id} not found")
        return path

    def exists(self, workbook_id: str) -> bool:
        return (self.data_dir / f"{workbook_id}.xlsx").exists()
