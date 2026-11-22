"""Scenario registry and manager for deterministic fault injection."""

from app.schemas.simulation import ScenarioDefinition
from app.simulator.models import FaultSpec, ScenarioSpec


class ScenarioManager:
    """Manages built-in reproducible infrastructure failure scenarios."""

    def __init__(self) -> None:
        self._scenarios: dict[str, ScenarioSpec] = {
            "db_latency_cascade": ScenarioSpec(
                id="db_latency_cascade",
                name="Database Latency Cascade",
                description=(
                    "Primary Postgres connection pool saturates under lock contention, "
                    "causing query latency spikes that propagate to Payment Service, "
                    "Checkout API, API Gateway, Fulfillment Worker, and Order Queue."
                ),
                root_service="postgres-primary",
                expected_severity="CRITICAL",
                faults=(
                    FaultSpec(
                        target_service_id="postgres-primary",
                        ramp_tau_ticks=2.2,
                        latency_linear_gain=12.0,
                        latency_quadratic_gain=85.0,
                        saturation_delta_pct=71.0,
                        cpu_delta_pct=64.0,
                        error_rate_delta=0.14,
                    ),
                ),
            )
        }

    def list_definitions(self) -> list[ScenarioDefinition]:
        """Return API-ready metadata for all registered scenarios."""
        return [
            ScenarioDefinition(
                id=spec.id,
                name=spec.name,
                description=spec.description,
                root_service=spec.root_service,
                expected_severity=spec.expected_severity,
            )
            for spec in self._scenarios.values()
        ]

    def get_scenario(self, scenario_id: str) -> ScenarioSpec:
        """Look up a scenario by ID, raising KeyError if unknown."""
        if scenario_id not in self._scenarios:
            raise KeyError(f"Unknown scenario '{scenario_id}'.")
        return self._scenarios[scenario_id]

