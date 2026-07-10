"""SheetSleuth FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import Settings
from .dependencies import AppServices, build_services
from .http.errors import register_error_handlers
from .http.routes import register_routes


def create_app(
    settings: Settings | None = None,
    services: AppServices | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="SheetSleuth")
    app.state.settings = settings
    app.state.services = services or build_services(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    register_routes(app)

    if settings.frontend_dist.exists():
        app.mount(
            "/",
            StaticFiles(directory=settings.frontend_dist, html=True),
            name="frontend",
        )

    return app


app = create_app()
