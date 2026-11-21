"""Idempotent seed data for the default 7-service simulated topology."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DependencyEdgeORM, ServiceNodeORM

DEFAULT_SERVICES: list[dict] = [
    {
        "id": "api-gateway",
        "name": "API Gateway",
        "tier": "edge",
        "status": "healthy",
        "criticality": 5,
        "baseline_latency_ms": 14.0,
        "slo_latency_ms": 300.0,
        "slo_error_rate": 0.01,
    },
    {
        "id": "auth-service",
        "name": "Auth Service",
        "tier": "application",
        "status": "healthy",
        "criticality": 4,
        "baseline_latency_ms": 18.0,
        "slo_latency_ms": 200.0,
        "slo_error_rate": 0.01,
    },
    {
        "id": "checkout-api",
        "name": "Checkout API",
        "tier": "application",
        "status": "healthy",
        "criticality": 5,
        "baseline_latency_ms": 32.0,
        "slo_latency_ms": 350.0,
        "slo_error_rate": 0.01,
    },
    {
        "id": "payment-service",
        "name": "Payment Service",
        "tier": "application",
        "status": "healthy",
        "criticality": 5,
        "baseline_latency_ms": 45.0,
        "slo_latency_ms": 400.0,
        "slo_error_rate": 0.01,
    },
    {
        "id": "order-queue",
        "name": "Order Queue",
        "tier": "messaging",
        "status": "healthy",
        "criticality": 4,
        "baseline_latency_ms": 8.0,
        "slo_latency_ms": 150.0,
        "slo_error_rate": 0.005,
    },
    {
        "id": "worker-fulfillment",
        "name": "Fulfillment Worker",
        "tier": "worker",
        "status": "healthy",
        "criticality": 3,
        "baseline_latency_ms": 55.0,
        "slo_latency_ms": 500.0,
        "slo_error_rate": 0.02,
    },
    {
        "id": "postgres-primary",
        "name": "Postgres Primary",
        "tier": "database",
        "status": "healthy",
        "criticality": 5,
        "baseline_latency_ms": 18.0,
        "slo_latency_ms": 100.0,
        "slo_error_rate": 0.005,
    },
]

DEFAULT_DEPENDENCIES: list[dict] = [
    {"id": "e-gw-auth", "source_id": "api-gateway", "target_id": "auth-service", "protocol": "grpc", "impact_weight": 0.4},
    {"id": "e-gw-chk", "source_id": "api-gateway", "target_id": "checkout-api", "protocol": "http", "impact_weight": 0.9},
    {"id": "e-chk-pay", "source_id": "checkout-api", "target_id": "payment-service", "protocol": "grpc", "impact_weight": 0.85},
    {"id": "e-chk-q", "source_id": "checkout-api", "target_id": "order-queue", "protocol": "amqp", "impact_weight": 0.5},
    {"id": "e-chk-pg", "source_id": "checkout-api", "target_id": "postgres-primary", "protocol": "tcp/postgres", "impact_weight": 0.8},
    {"id": "e-pay-pg", "source_id": "payment-service", "target_id": "postgres-primary", "protocol": "tcp/postgres", "impact_weight": 0.95},
    {"id": "e-wrk-q", "source_id": "worker-fulfillment", "target_id": "order-queue", "protocol": "amqp", "impact_weight": 0.75},
    {"id": "e-wrk-pg", "source_id": "worker-fulfillment", "target_id": "postgres-primary", "protocol": "tcp/postgres", "impact_weight": 0.9},
]


def seed_initial_data(db: Session) -> None:
    """Seed baseline topology nodes and edges if the database is empty."""
    existing = db.execute(select(ServiceNodeORM.id).limit(1)).first()
    if existing is not None:
        return

    for svc in DEFAULT_SERVICES:
        db.add(ServiceNodeORM(**svc))
    db.flush()

    for edge in DEFAULT_DEPENDENCIES:
        db.add(DependencyEdgeORM(**edge))

    db.commit()

