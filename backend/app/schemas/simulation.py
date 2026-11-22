"""Simulation control and deterministic incident schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.telemetry import MonitoringEvent, SeverityLevel

IncidentStatus = Literal["DETECTED", "ACTIVE", "RESOLVED"]
InvestigationStatus = Literal["NOT_STARTED", "RUNNING", "COMPLETED", "FAILED"]


class ScenarioDefinition(BaseModel):
    """Metadata describing an injectable fault scenario."""

    id: str
    name: str
    description: str
    root_service: str
    expected_severity: SeverityLevel


class ScenarioListResponse(BaseModel):
    """List of available failure scenarios."""

    scenarios: list[ScenarioDefinition]


class SimulationStatusResponse(BaseModel):
    """Current simulator runtime and health summary."""

    running: bool
    tick: int = Field(ge=0)
    sim_time_s: float = Field(ge=0.0)
    tick_interval_seconds: float = Field(gt=0.0)
    active_scenario: str | None
    resilience_score: float = Field(ge=0.0, le=100.0)
    total_services: int
    healthy_services: int
    degraded_services: int
    critical_services: int
    active_incidents_count: int


class InjectScenarioRequest(BaseModel):
    """Request body to inject a named failure scenario."""

    scenario_id: str = Field(min_length=1)


class AdvanceTicksRequest(BaseModel):
    """Request body to advance simulation deterministically by N ticks."""

    ticks: int = Field(default=1, ge=1, le=50)


class ResetSimulationRequest(BaseModel):
    """Request body to reset simulation state."""

    clear_incidents: bool = True


class DetectedIncident(BaseModel):
    """Deterministic incident produced by threshold & topology correlation."""

    id: str
    title: str
    scenario_id: str | None = None
    status: IncidentStatus
    severity: SeverityLevel
    affected_services: list[str]
    root_cause_candidate: str | None = None
    root_cause_rationale: str | None = None
    triggering_evidence: list[MonitoringEvent]
    detected_tick: int
    detected_sim_time_s: float = 0.0
    detected_at: datetime
    updated_tick: int
    updated_at: datetime
    investigation_status: InvestigationStatus = "NOT_STARTED"


class IncidentListResponse(BaseModel):
    """Collection of detected incidents."""

    incidents: list[DetectedIncident]

