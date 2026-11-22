"""Static, allowlisted simulated remediation catalog.

No arbitrary commands, scripts, shell execution, or user-defined executable actions
are permitted. Every action maps strictly to a modeled simulation mitigation handler.
"""

from types import MappingProxyType

from app.schemas.remediation import RemediationActionDefinition

_CATALOG_ITEMS: dict[str, RemediationActionDefinition] = {
    "expand_db_connection_pool": RemediationActionDefinition(
        action_id="expand_db_connection_pool",
        name="Expand DB Connection Pool",
        description=(
            "Simulates increasing the available primary database connection pool capacity "
            "and releasing lock contention pressure on postgres-primary."
        ),
        allowed_targets=["postgres-primary"],
        default_parameters={"pool_multiplier": 2.0},
        parameter_bounds={"pool_multiplier": (1.2, 3.0)},
        expected_effect=(
            "Gradually relieves database connection pool saturation and query latency over 3-5 "
            "simulation ticks, allowing dependent services and order-queue to recover naturally."
        ),
        risk_classification="HIGH",
        policy_requirements="Requires explicit human approval (database tier / high risk).",
        preconditions=[
            "Incident must be active (not already RESOLVED).",
            "Target service postgres-primary must be degraded or critical.",
            "At least one traceable evidence reference must support the plan.",
        ],
        validation_conditions=[
            "postgres-primary status returns to healthy (latency < 125ms, saturation < 75%).",
            "Critical downstream services (payment-service, checkout-api, api-gateway) return to healthy.",
            "order-queue backlog drains below 250 pending messages.",
            "Healthy state holds across 2 consecutive verification ticks.",
        ],
        execution_identifier="sim.exec.expand_db_connection_pool",
    ),
    "enable_circuit_breaker": RemediationActionDefinition(
        action_id="enable_circuit_breaker",
        name="Enable Circuit Breaker",
        description=(
            "Simulates enabling a protective circuit breaker on an application service to "
            "dampen cascading upstream latency and error propagation."
        ),
        allowed_targets=["payment-service", "checkout-api"],
        default_parameters={"error_threshold_pct": 25.0},
        parameter_bounds={"error_threshold_pct": (5.0, 60.0)},
        expected_effect=(
            "Isolates cascading request pressure on the target application service, reducing "
            "propagated error and latency amplification by up to 65%."
        ),
        risk_classification="MEDIUM",
        policy_requirements="Auto-approved for LOW/MEDIUM incidents with high confidence; requires human approval for HIGH/CRITICAL incidents.",
        preconditions=[
            "Incident must be active (not already RESOLVED).",
            "Target application service must be degraded or critical.",
            "At least one traceable evidence reference must support the plan.",
        ],
        validation_conditions=[
            "Target service latency and error rate drop within SLO thresholds.",
            "Healthy state holds across 2 consecutive verification ticks.",
        ],
        execution_identifier="sim.exec.enable_circuit_breaker",
    ),
    "scale_queue_consumers": RemediationActionDefinition(
        action_id="scale_queue_consumers",
        name="Scale Queue Consumers",
        description=(
            "Simulates scaling fulfillment worker concurrency to increase order-queue drain "
            "capacity and clear accumulated message backlog."
        ),
        allowed_targets=["worker-fulfillment", "order-queue"],
        default_parameters={"consumer_multiplier": 2.4},
        parameter_bounds={"consumer_multiplier": (1.2, 4.0)},
        expected_effect=(
            "Increases queue consumer drain capacity by up to 2.4x to accelerate backlog "
            "drain on order-queue."
        ),
        risk_classification="LOW",
        policy_requirements="Auto-approved for LOW/MEDIUM incidents with high confidence; requires human approval for HIGH/CRITICAL incidents.",
        preconditions=[
            "Incident must be active (not already RESOLVED).",
            "Target messaging/worker service must be degraded or critical.",
            "At least one traceable evidence reference must support the plan.",
        ],
        validation_conditions=[
            "order-queue backlog drains below 250 pending messages.",
            "worker-fulfillment returns to healthy.",
            "Healthy state holds across 2 consecutive verification ticks.",
        ],
        execution_identifier="sim.exec.scale_queue_consumers",
    ),
}

RECOVERY_CATALOG = MappingProxyType(_CATALOG_ITEMS)


def list_catalog_actions() -> list[RemediationActionDefinition]:
    """Return all allowlisted simulated remediation actions in canonical order."""
    return list(RECOVERY_CATALOG.values())


def get_catalog_action(action_id: str) -> RemediationActionDefinition | None:
    """Return an allowlisted action definition or None if unknown."""
    return RECOVERY_CATALOG.get(action_id)


def validate_action_parameters(
    action: RemediationActionDefinition, parameters: dict[str, float | int | str | bool]
) -> list[str]:
    """Validate parameter keys and numeric bounds against the static catalog definition."""
    errors: list[str] = []
    for req_key in action.default_parameters:
        if req_key not in parameters:
            errors.append(f"Missing required parameter '{req_key}' for action '{action.action_id}'.")

    for key, (low, high) in action.parameter_bounds.items():
        if key not in parameters:
            continue
        val = parameters[key]
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            errors.append(f"Parameter '{key}' must be numeric.")
        elif not (low <= float(val) <= high):
            errors.append(
                f"Parameter '{key}' value {val} is outside safe bounds [{low}, {high}]."
            )

    unknown_keys = set(parameters.keys()) - set(action.default_parameters.keys())
    if unknown_keys:
        errors.append(
            f"Unsupported parameter(s) for '{action.action_id}': {', '.join(sorted(unknown_keys))}."
        )
    return errors

