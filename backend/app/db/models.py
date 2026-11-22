"""Foundational SQLAlchemy 2.0 ORM models for NEXUS."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ServiceNodeORM(Base):
    """Simulated infrastructure service node."""

    __tablename__ = "services"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    tier: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="healthy")
    criticality: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    baseline_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=20.0)
    slo_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=250.0)
    slo_error_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.01)


class DependencyEdgeORM(Base):
    """Directed dependency edge (source depends on target)."""

    __tablename__ = "dependencies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(64), ForeignKey("services.id"), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), ForeignKey("services.id"), nullable=False)
    protocol: Mapped[str] = mapped_column(String(32), nullable=False)
    impact_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)


class AuditLogORM(Base):
    """Append-only audit trail entry."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    incident_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_name: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, index=True)


class IncidentORM(Base):
    """Persistent incident record synchronized with deterministic simulator detection."""

    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    scenario_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DETECTED")
    detected_tick: Mapped[int] = mapped_column(Integer, nullable=False)
    detected_sim_time_s: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_tick: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)
    root_cause_candidate: Mapped[str | None] = mapped_column(String(64), nullable=True)
    root_cause_rationale: Mapped[str | None] = mapped_column(String(512), nullable=True)
    affected_services: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    supporting_events: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    investigation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_STARTED")


class InvestigationORM(Base):
    """Persistent evidence-grounded investigation findings for an incident."""

    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("incidents.id"), nullable=False, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="COMPLETED")
    inference_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="DETERMINISTIC")
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    summary: Mapped[str] = mapped_column(String(1024), nullable=False)
    root_cause_hypothesis: Mapped[str] = mapped_column(String(1024), nullable=False)
    probable_root_cause_service: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supporting_evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    limiting_evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    affected_services: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    service_roles: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    contributing_factors: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    blast_radius: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    confidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    recommended_next_steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    agent_trace: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    evidence_bundle: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)

