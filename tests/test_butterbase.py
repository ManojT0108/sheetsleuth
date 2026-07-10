import pytest
import requests


class FakeResponse:
    def __init__(self, status_code: int, url: str, text: str = "{}"):
        self.status_code = status_code
        self.url = url
        self.text = text
        self.ok = status_code < 400

    def json(self):
        return {"ok": self.ok}

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError(f"{self.status_code} error", response=self)


def test_upsert_workbook_reports_insert_and_update_failures(monkeypatch):
    from app.services import butterbase

    calls = []

    def fake_post(url, **kwargs):
        calls.append(("post", url, kwargs))
        return FakeResponse(400, url, '{"error":"bad workbooks payload"}')

    def fake_patch(url, **kwargs):
        calls.append(("patch", url, kwargs))
        return FakeResponse(404, url, '{"error":"row not found"}')

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("requests.patch", fake_patch)

    row = {"id": "wb-1", "name": "Workbook", "cells": 10}

    with pytest.raises(butterbase.ButterbaseRequestError) as exc_info:
        butterbase.upsert_workbook(row)

    message = str(exc_info.value)
    assert "bad workbooks payload" in message
    assert "fallback update failed" in message
    assert "row not found" in message
    assert row["id"] == "wb-1"
    assert calls[1][2]["params"] == {"id": "eq.wb-1"}
    assert calls[1][2]["json"] == {"name": "Workbook", "cells": 10}


def test_upsert_workbook_returns_insert_response_without_update(monkeypatch):
    from app.services import butterbase

    calls = []

    def fake_post(url, **kwargs):
        calls.append(("post", url, kwargs))
        return FakeResponse(201, url, '{"id":"wb-1"}')

    def fake_patch(url, **kwargs):
        calls.append(("patch", url, kwargs))
        raise AssertionError("patch should not be called")

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("requests.patch", fake_patch)

    assert butterbase.upsert_workbook({"id": "wb-1"}) == {"ok": True}
    assert [call[0] for call in calls] == ["post"]
