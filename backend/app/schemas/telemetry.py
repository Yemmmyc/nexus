"""Telemetry and monitoring event schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ServiceHealthStatus = Literal["healthy", "degraded", "critical"]
SeverityLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class ServiceMetrics(BaseModel):
    """Point-in-time metrics for a simulated infrastructure service."""

    latency_ms: float = Field(ge=0.0)
    error_rate: float = Field(ge=0.0, le=1.0)
    throughput_rps: float = Field(ge=0.0)
    cpu_pct: float = Field(ge=0.0, le=100.0)
    saturation_pct: float = Field(ge=0.0, le=100.0)
    queue_depth: int = Field(ge=0)


class ServiceTelemetrySample(BaseModel):
    """Timestamped metric sample emitted at a simulation tick."""

    tick: int = Field(ge=0)
    sim_time_s: float = Field(ge=0.0)
    timestamp: datetime
    service_id: str
    status: ServiceHealthStatus
    metrics: ServiceMetrics


class MonitoringEvent(BaseModel):
    """Threshold-based monitoring event emitted by the deterministic simulator."""

    id: str
    tick: int = Field(ge=0)
    sim_time_s: float = Field(ge=0.0)
    timestamp: datetime
    service_id: str
    event_type: str
    severity: SeverityLevel
    metric_name: str
    metric_value: float
    threshold_value: float
    message: str


class TelemetryHistoryResponse(BaseModel):
    """Collection of recent telemetry samples."""

    tick: int
    samples: list[ServiceTelemetrySample]

