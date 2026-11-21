"""Health and standard error response schemas."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Service liveness and runtime readiness status."""

    status: Literal["ok", "degraded"]
    service: str
    version: str
    environment: str
    ai_mode: Literal["auto", "llm", "deterministic"]
    llm_configured: bool
    simulator_running: bool
    db_connected: bool
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ErrorResponse(BaseModel):
    """Consistent structured API error payload."""

    error: str
    detail: str
    path: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

