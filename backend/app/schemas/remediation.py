"""Pydantic v2 schemas for Phase 3 policy-gated simulated recovery and verification."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.telemetry import ServiceHealthStatus

RiskClassification = Literal["LOW", "MEDIUM", "HIGH"]
PolicyDecision = Literal["AUTO_APPROVE", "REQUIRE_HUMAN_APPROVAL", "DENY"]
ApprovalStatus = Literal["NOT_REQUIRED", "PENDING", "APPROVED", "REJECTED", "DENIED"]
ExecutionStatus = Literal["NOT_STARTED", "RUNNING", "COMPLETED", "FAILED"]
VerificationStatus = Literal["NOT_STARTED", "IN_PROGRESS", "VERIFIED", "FAILED"]


class RemediationActionDefinition(BaseModel):
    """Static allowlisted simulated remediation action catalog entry."""

    action_id: str
    name: str
    description: str
    allowed_targets: list[str]
    default_parameters: dict[str, float | int | str | bool]
    parameter_bounds: dict[str, tuple[float, float]] = Field(default_factory=dict)
    expected_effect: str
    risk_classification: RiskClassification
    policy_requirements: str
    preconditions: list[str]
    validation_conditions: list[str]
    execution_identifier: str


class RemediationCatalogResponse(BaseModel):
    """List of static allowlisted simulated remediation actions."""

    actions: list[RemediationActionDefinition]


class PolicyRuleMatch(BaseModel):
    """Single declarative Trust Agent policy rule evaluation outcome."""

    rule_id: str
    outcome: PolicyDecision
    reason: str


class PolicyEvaluationResult(BaseModel):
    """Deterministic, explainable Trust Agent policy verdict."""

    decision: PolicyDecision
    matched_rules: list[PolicyRuleMatch]
    reasons: list[str]
    evaluated_at: datetime


class ExecutionRecord(BaseModel):
    """Simulated remediation execution record."""

    execution_id: str
    plan_id: str
    incident_id: str
    action_id: str
    execution_identifier: str
    target_service: str
    parameters: dict[str, float | int | str | bool]
    status: ExecutionStatus
    applied_tick: int
    applied_sim_time_s: float
    modeled_effect_summary: str
    started_at: datetime
    completed_at: datetime | None = None
    error: str | None = None


class ServiceVerificationCheck(BaseModel):
    """Single service SLO verification check at the current simulation tick."""

    service_id: str
    status: ServiceHealthStatus
    latency_ms: float
    slo_latency_ms: float
    error_rate: float
    slo_error_rate: float
    saturation_pct: float
    queue_depth: int
    passed: bool
    note: str


class VerificationResult(BaseModel):
    """Verification Agent assessment across consecutive simulation ticks."""

    plan_id: str
    incident_id: str
    status: VerificationStatus
    evaluated_tick: int
    evaluated_sim_time_s: float
    applied_tick: int
    elapsed_ticks_since_execution: int
    consecutive_healthy_ticks: int
    required_consecutive_healthy_ticks: int
    max_verification_ticks: int
    resilience_score: float
    checks: list[ServiceVerificationCheck]
    summary: str
    evaluated_at: datetime


class RemediationPlan(BaseModel):
    """Persisted policy-gated simulated remediation plan."""

    id: str
    incident_id: str
    action_id: str
    action_name: str
    target_service: str
    parameters: dict[str, float | int | str | bool]
    evidence_refs: list[str]
    rationale: str
    expected_effects: list[str]
    limitations: list[str]
    risks: list[str]
    preconditions: list[str]
    policy_decision: PolicyDecision
    policy_evaluation: PolicyEvaluationResult
    approval_status: ApprovalStatus
    approved_by: str | None = None
    approval_comment: str | None = None
    approved_at: datetime | None = None
    execution_status: ExecutionStatus
    execution_record: ExecutionRecord | None = None
    verification_status: VerificationStatus
    verification_result: VerificationResult | None = None
    created_at: datetime
    updated_at: datetime


class RemediationPlanListResponse(BaseModel):
    """Collection of remediation plans."""

    plans: list[RemediationPlan]


class CreateRemediationRequest(BaseModel):
    """Optional override parameters when requesting a recovery plan for an incident."""

    action_id: str | None = None
    target_service: str | None = None
    parameters: dict[str, float | int | str | bool] | None = None


class ApprovalDecisionRequest(BaseModel):
    """Human operator approval or rejection request."""

    actor: str = Field(default="sre-operator", min_length=1, max_length=64)
    comment: str = Field(default="", max_length=512)

