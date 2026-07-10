"""FastAPI routes for the SheetSleuth backend."""

from __future__ import annotations

from fastapi import APIRouter, FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from ..dependencies import AppServices

router = APIRouter()


def get_services(request: Request) -> AppServices:
    return request.app.state.services


@router.post("/api/workbooks/upload")
async def upload(request: Request, file: UploadFile):
    services = get_services(request)
    result = services.ingestion.ingest(
        await file.read(), file.filename or "workbook"
    )
    return result.to_public_dict()


@router.post("/api/demo")
def demo(request: Request):
    services = get_services(request)
    raw = request.app.state.settings.demo_workbook.read_bytes()
    return services.ingestion.ingest_demo(raw).to_public_dict()


@router.get("/api/workbooks/{workbook_id}/graph")
def graph(request: Request, workbook_id: str):
    return get_services(request).queries.graph(workbook_id)


@router.get("/api/workbooks/{workbook_id}/findings")
def findings(request: Request, workbook_id: str):
    return get_services(request).queries.findings_for_workbook(workbook_id)


@router.get("/api/workbooks/{workbook_id}/critical")
def critical(request: Request, workbook_id: str):
    return get_services(request).queries.critical_cells(workbook_id)


@router.get("/api/workbooks/{workbook_id}/blast/{sheet}/{address}")
def blast(request: Request, workbook_id: str, sheet: str, address: str):
    return get_services(request).queries.blast_radius(workbook_id, sheet, address)


@router.post("/api/findings/{finding_id:path}/verify")
def verify(request: Request, finding_id: str):
    return get_services(request).verifier.verify(finding_id)


@router.post("/api/workbooks/{workbook_id}/ask")
def ask(request: Request, workbook_id: str, body: dict):
    return get_services(request).ask.ask(workbook_id, body.get("question", ""))


@router.post("/api/auth/{action}")
def auth_proxy(action: str, body: dict):
    """Proxy Butterbase end-user auth to avoid browser CORS preflight failures."""
    if action not in ("signup", "login"):
        raise HTTPException(404, "unknown auth action")

    import requests as rq

    from ..services.butterbase import APP_ID, BB_API

    response = rq.post(f"{BB_API}/auth/{APP_ID}/{action}", json=body, timeout=30)
    return JSONResponse(status_code=response.status_code, content=response.json())


@router.post("/api/billing/purchase")
def purchase_proxy(body: dict):
    """Proxy Butterbase checkout while forwarding the user's JWT."""
    import requests as rq

    from ..services.butterbase import APP_ID, BB_API

    payload = dict(body)
    token = payload.pop("access_token", "")
    response = rq.post(
        f"{BB_API}/v1/{APP_ID}/billing/purchase",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    return JSONResponse(status_code=response.status_code, content=response.json())


@router.get("/api/health")
def health(request: Request):
    return get_services(request).queries.health()


def register_routes(app: FastAPI) -> None:
    app.include_router(router)
