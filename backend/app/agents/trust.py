"""Trust Agent: independent, deterministic, declarative safety & policy gate."""

from datetime import datetime, timezone

from app.recovery.catalog import get_catalog_action, validate_action_parameters
from app.schemas.investigation import InvestigationResult
from app.schemas.remediation import PolicyDecision, PolicyEvaluationResult, PolicyRuleMatch
from app.schemas.simulation import DetectedIncident
from app.simulator.engine import SimulationEngine


class TrustAgent:
    """Evaluates recovery plans independently against declarative safety policies.

    Policy outcomes are strictly reproducible: AUTO_APPROVE, REQUIRE_HUMAN_APPROVAL, or DENY.
    Human approval can never bypass the action allowlist or override a DENY decision.
    """

    def evaluate(
        self,
        *,
        action_id: str,
        target_service: str,
        parameters: dict[str, float | int | str | bool],
        evidence_refs: list[str],
        incident: DetectedIncident,
        investigation: InvestigationResult | None,
        engine: SimulationEngine,
    ) -> PolicyEvaluationResult:
        """Evaluate a proposed remediation plan against declarative rules POL-001..POL-008."""
        matched: list[PolicyRuleMatch] = []
        now = datetime.now(timezone.utc)

        # POL-001: Action must exist in static allowlist catalog
        action_def = get_catalog_action(action_id)
        if action_def is None:
            matched.append(
                PolicyRuleMatch(
                    rule_id="POL-001",
                    outcome="DENY",
                    reason=f"Action '{action_id}' is not in the static allowlisted recovery catalog.",
                )
            )
            return self._finalize("DENY", matched, now)

        # POL-002: Target service must exist in topology and be permitted for this action
        topo_ids = {s.id for s in engine.topology.services}
        if target_service not in topo_ids or target_service not in action_def.allowed_targets:
            matched.append(
                PolicyRuleMatch(
                    rule_id="POL-002",
                    outcome="DENY",
                    reason=(
                        f"Target service '{target_service}' is invalid for action '{action_id}'. "
                        f"Allowed targets: {', '.join(action_def.allowed_targets)}."
                    ),
                )
            )
            return self._finalize("DENY", matched, now)

        # POL-003: Required parameters must be present and within safe bounds
        param_errors = validate_action_parameters(action_def, parameters)
        if param_errors:
            matched.append(
                PolicyRuleMatch(
                    rule_id="POL-003",
                    outcome="DENY",
                    reason="; ".join(param_errors),
                )
            )
            return self._finalize("DENY", matched, now)

        # POL-004: Plan must cite traceable evidence
        if not evidence_refs:
            matched.append(
                PolicyRuleMatch(
                    rule_id="POL-004",
                    outcome="DENY",
                    reason="Missing required traceable evidence references; ungrounded remediation is denied.",
                )
            )
            return self._finalize("DENY", matched, now)

        # POL-005: Preconditions check (incident active & target service currently unhealthy)
        topo_nodes = {n.id: n for n in engine.get_topology_snapshot().nodes}
        target_node = topo_nodes[target_service]
        if incident.status == "RESOLVED":
            matched.append(
                PolicyRuleMatch(
                    rule_id="POL-005",
                    outcome="DENY",
                    reason=f"Precondition failed: incident '{incident.id}' is already RESOLVED.",
                )
            )
            return self._finalize("DENY", matched, now)

        if target_node.status == "healthy":
            matched.append(
                PolicyRuleMatch(
                    rule_id="POL-005",
                    outcome="DENY",
                    reason=(
                        f"Precondition failed: target service '{target_service}' is currently "
                        f"healthy; simulated remediation is unnecessary."
                    ),
                )
            )
            return self._finalize("DENY", matched, now)

        # Non-denial checks: determine REQUIRE_HUMAN_APPROVAL vs AUTO_APPROVE
        target_tier = engine.topology.get_service(target_service).tier
        require_human = False

        # POL-006: High-risk or database-tier actions always require human approval
        if action_def.risk_classification == "HIGH" or target_tier == "database":
            require_human = True
            matched.append(
                PolicyRuleMatch(
                    rule_id="POL-006",
                    outcome="REQUIRE_HUMAN_APPROVAL",
                    reason=(
                        f"Action '{action_id}' has risk={action_def.risk_classification} "
                        f"on tier='{target_tier}'; explicit human authorization is mandatory."
                    ),
                )
            )

        # POL-007: HIGH/CRITICAL severity or lower investigation confidence require human approval
        confidence_score = investigation.confidence.score if investigation is not None else 0.0
        if incident.severity in ("HIGH", "CRITICAL") or confidence_score < 0.75:
            require_human = True
            matched.append(
                PolicyRuleMatch(
                    rule_id="POL-007",
                    outcome="REQUIRE_HUMAN_APPROVAL",
                    reason=(
                        f"Incident severity is {incident.severity} (confidence={confidence_score:.2f}); "
                        f"human approval gate enforced."
                    ),
                )
            )

        if require_human:
            return self._finalize("REQUIRE_HUMAN_APPROVAL", matched, now)

        # POL-008: Safe LOW/MEDIUM non-database action on LOW/MEDIUM incident with high confidence
        matched.append(
            PolicyRuleMatch(
                rule_id="POL-008",
                outcome="AUTO_APPROVE",
                reason=(
                    f"Allowlisted {action_def.risk_classification}-risk non-database action "
                    f"on {incident.severity} incident with confidence {confidence_score:.2f} >= 0.75."
                ),
            )
        )
        return self._finalize("AUTO_APPROVE", matched, now)

    @staticmethod
    def _finalize(
        decision: PolicyDecision,
        matched: list[PolicyRuleMatch],
        evaluated_at: datetime,
    ) -> PolicyEvaluationResult:
        return PolicyEvaluationResult(
            decision=decision,
            matched_rules=matched,
            reasons=[f"[{m.rule_id}] {m.reason}" for m in matched],
            evaluated_at=evaluated_at,
        )

