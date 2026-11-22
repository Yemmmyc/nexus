"""Pydantic v2 schemas for Phase 2 incident intelligence, evidence, and logical agents."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.telemetry import ServiceHealthStatus, SeverityLevel

EvidenceSourceType = Literal[
    "monitoring_event",
    "telemetry_snapshot",
    "telemetry_trend",
    "topology_edge",
    "queue_metric",
    "detector_candidate",
]

ServiceCausalRole = Literal[
    "probable_root_cause",
    "contributing_cause",
    "downstream_symptom",
    "unaffected",
]

InferenceMode = Literal["DETERMINISTIC", "LLM"]
ConfidenceLevel = Literal["LOW", "MEDIUM", "HIGH"]


class EvidenceItem(BaseModel):
    """Single traceable, non-fabricated evidence record collected from NEXUS state."""

    evidence_id: str
    source_type: EvidenceSourceType
    source_ref: str
    service_id: str | None = None
    tick: int | None = None
    metric_name: str | None = None
    metric_value: float | None = None
    observation: str


class ServiceTrendSummary(BaseModel):
    """Before/after telemetry delta for a service around incident detection."""

    service_id: str
    tier: str
    current_status: ServiceHealthStatus
    baseline_latency_ms: float
    current_latency_ms: float
    latency_ratio: float
    current_error_rate: float
    current_cpu_pct: float
    current_saturation_pct: float
    current_queue_depth: int
    queue_delta: int


class EvidenceBundle(BaseModel):
    """Complete structured evidence package assembled by the Observer agent."""

    incident_id: str
    collected_at_tick: int
    collected_sim_time_s: float
    detected_tick: int
    detected_sim_time_s: float
    affected_services: list[str]
    unaffected_services: list[str]
    detector_root_cause_candidate: str | None = None
    detector_rationale: str | None = None
    service_trends: list[ServiceTrendSummary]
    propagation_paths: list[str]
    items: list[EvidenceItem]


class ServiceRoleAssessment(BaseModel):
    """Causal classification of a service within the incident."""

    service_id: str
    tier: str
    status: ServiceHealthStatus
    role: ServiceCausalRole
    rationale: str


class ConfidenceCriterion(BaseModel):
    """Explainable component of the investigation confidence score."""

    name: str
    score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)
    explanation: str


class ConfidenceAssessment(BaseModel):
    """Transparent, criteria-based confidence assessment."""

    score: float = Field(ge=0.0, le=1.0)
    level: ConfidenceLevel
    criteria: list[ConfidenceCriterion]


class BlastRadiusAssessment(BaseModel):
    """Operational impact and risk evaluation produced by the Risk Analyst agent."""

    risk_score: int = Field(ge=0, le=100)
    risk_level: SeverityLevel
    impacted_services: list[str]
    unaffected_services: list[str]
    impacted_service_count: int
    total_service_count: int
    customer_facing_impact: bool
    business_impact_summary: str
    factors: dict[str, float]


class LogicalAgentTrace(BaseModel):
    """Execution record for a logical agent role in the investigation pipeline."""

    agent_role: Literal["Observer", "Investigator", "Risk Analyst"]
    status: Literal["COMPLETED", "FAILED"]
    inference_mode: InferenceMode
    duration_ms: int = Field(ge=0)
    summary: str


class InvestigationResult(BaseModel):
    """Complete evidence-grounded investigation findings for an incident."""

    id: str
    incident_id: str
    status: Literal["COMPLETED", "FAILED"]
    inference_mode: InferenceMode
    model_name: str
    summary: str
    root_cause_hypothesis: str
    probable_root_cause_service: str | None = None
    supporting_evidence: list[EvidenceItem]
    limiting_evidence: list[str]
    affected_services: list[str]
    service_roles: list[ServiceRoleAssessment]
    contributing_factors: list[str]
    blast_radius: BlastRadiusAssessment
    confidence: ConfidenceAssessment
    recommended_next_steps: list[str]
    agent_trace: list[LogicalAgentTrace]
    created_at: datetime
    updated_at: datetime


class TimelineEntry(BaseModel):
    """Unified chronological entry combining monitoring events and audit trail records."""

    timestamp: datetime
    source: Literal["MONITORING_EVENT", "AUDIT_LOG"]
    event_type: str
    actor: str
    service_id: str | None = None
    tick: int | None = None
    summary: str
    details: dict = Field(default_factory=dict)


class IncidentTimelineResponse(BaseModel):
    """Chronological timeline for a specific incident."""

    incident_id: str
    entries: list[TimelineEntry]

