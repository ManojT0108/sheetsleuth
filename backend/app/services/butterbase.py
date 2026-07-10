"""Butterbase integration: mirrors product state (workbooks, reports, asks)
into the app's Postgres via the auto-generated REST API, and exposes the
AI gateway for LLM calls. Frontend auth/payments go through backend proxies."""

import os

import requests

BB_API = "https://api.butterbase.ai"
APP_ID = os.environ.get("BUTTERBASE_APP_ID", "app_x89ezf73vxrn")

# rows created before a user signs in are owned by the anonymous user
ANON_USER = "00000000-0000-0000-0000-000000000000"


class ButterbaseRequestError(RuntimeError):
    """Butterbase returned a non-success response."""


def _headers():
    return {
        "Authorization": f"Bearer {os.environ.get('BUTTERBASE_API_KEY', '')}",
        "Content-Type": "application/json",
    }


def _response_payload(response: requests.Response):
    if not response.text:
        return {}
    try:
        return response.json()
    except ValueError:
        return response.text


def _describe_response(action: str, response: requests.Response) -> str:
    body = response.text[:500] if response.text else "<empty response>"
    return f"{action} failed with HTTP {response.status_code} for {response.url}: {body}"


def _raise_for_status(action: str, response: requests.Response) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise ButterbaseRequestError(_describe_response(action, response)) from exc


def insert(table: str, row: dict):
    r = requests.post(f"{BB_API}/v1/{APP_ID}/{table}", json=row,
                      headers=_headers(), timeout=30)
    _raise_for_status(f"insert {table}", r)
    return _response_payload(r)


def upsert_workbook(row: dict):
    insert_response = requests.post(
        f"{BB_API}/v1/{APP_ID}/workbooks",
        json=row,
        headers=_headers(),
        timeout=30,
    )
    if insert_response.ok:
        return _response_payload(insert_response)

    insert_error = _describe_response("insert workbooks", insert_response)
    if insert_response.status_code not in {400, 409}:
        raise ButterbaseRequestError(insert_error)

    rid = row["id"]
    update_response = requests.patch(
        f"{BB_API}/v1/{APP_ID}/workbooks",
        params={"id": f"eq.{rid}"},
        json={k: v for k, v in row.items() if k != "id"},
        headers=_headers(),
        timeout=30,
    )
    if update_response.ok:
        return _response_payload(update_response)
    raise ButterbaseRequestError(
        f"{insert_error}; fallback update failed: "
        f"{_describe_response('update workbooks', update_response)}"
    )


def llm(messages: list[dict], model: str = "anthropic/claude-sonnet-4.6",
        max_tokens: int = 1200) -> str:
    """Call an LLM through the Butterbase AI gateway (OpenAI-compatible)."""
    last_err = None
    for attempt in range(3):
        try:
            r = requests.post(
                f"{BB_API}/v1/{APP_ID}/chat/completions",
                json={"model": model, "messages": messages,
                      "max_tokens": max_tokens},
                headers=_headers(), timeout=150,
            )
            _raise_for_status("chat completion", r)
            return r.json()["choices"][0]["message"]["content"]
        except (requests.Timeout, requests.ConnectionError) as e:
            last_err = e
    raise last_err
