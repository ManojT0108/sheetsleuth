"""Butterbase integration: mirrors product state (workbooks, reports, asks)
into the app's Postgres via the auto-generated REST API, and exposes the
AI gateway for LLM calls. Frontend auth/payments hit Butterbase directly."""

import os

import requests

BB_API = "https://api.butterbase.ai"
APP_ID = os.environ.get("BUTTERBASE_APP_ID", "app_x89ezf73vxrn")


def _headers():
    return {
        "Authorization": f"Bearer {os.environ.get('BUTTERBASE_API_KEY', '')}",
        "Content-Type": "application/json",
    }


def insert(table: str, row: dict):
    r = requests.post(f"{BB_API}/v1/{APP_ID}/{table}", json=row,
                      headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def upsert_workbook(row: dict):
    try:
        return insert("workbooks", row)
    except requests.HTTPError:
        rid = row.pop("id")
        r = requests.patch(f"{BB_API}/v1/{APP_ID}/workbooks?id=eq.{rid}",
                           json=row, headers=_headers(), timeout=30)
        r.raise_for_status()
        return r.json() if r.text else {}


def llm(messages: list[dict], model: str = "claude-sonnet-5",
        max_tokens: int = 1200) -> str:
    """Call an LLM through the Butterbase AI gateway (OpenAI-compatible)."""
    r = requests.post(
        f"{BB_API}/v1/{APP_ID}/ai/chat/completions",
        json={"model": model, "messages": messages, "max_tokens": max_tokens},
        headers=_headers(), timeout=120,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]
