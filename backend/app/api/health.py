"""Health check endpoint."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.database import check_db_connection, get_db
from app.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="System health check")
def get_health(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Return service liveness, database connectivity, and runtime mode."""
    db_ok = check_db_connection(db)
    sim_controller = getattr(request.app.state, "simulation_service", None)
    sim_running = bool(sim_controller.is_running) if sim_controller is not None else False
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        ai_mode=settings.ai_mode,
        llm_configured=bool(settings.llm_api_key),
        simulator_running=sim_running,
        db_connected=db_ok,
    )

