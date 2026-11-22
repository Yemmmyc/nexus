"""Topology graph API schemas."""

from pydantic import BaseModel

from app.schemas.telemetry import ServiceHealthStatus, ServiceMetrics


class ServiceNodeState(BaseModel):
    """Service node enriched with current simulated metrics and incident overlays."""

    id: str
    name: str
    tier: str
    status: ServiceHealthStatus
    criticality: int
    baseline_latency_ms: float
    slo_latency_ms: float
    slo_error_rate: float
    metrics: ServiceMetrics
    in_blast_radius: bool = False
    is_root_cause_candidate: bool = False


class DependencyEdgeState(BaseModel):
    """Directed dependency edge (source depends on target) with live status."""

    id: str
    source: str
    target: str
    protocol: str
    impact_weight: float
    status: ServiceHealthStatus
    latency_ms: float


class TopologyResponse(BaseModel):
    """Complete simulated infrastructure topology snapshot."""

    tick: int
    sim_time_s: float
    active_scenario: str | None
    nodes: list[ServiceNodeState]
    edges: list[DependencyEdgeState]

