"""FastAPI application entrypoint for NEXUS."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_v1_router
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.db.database import SessionLocal, init_db
from app.db.seed import seed_initial_data


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialize SQLite schema and seed baseline topology on startup."""
    init_db()
    with SessionLocal() as db:
        seed_initial_data(db)
    yield


def create_app(initialize_db: bool = True) -> FastAPI:
    """Create and configure the NEXUS FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=f"{settings.app_name} — Autonomous Infrastructure Resilience & Trust Engine",
        version=settings.app_version,
        lifespan=lifespan if initialize_db else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()

