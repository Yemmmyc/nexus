"""Recovery Agent: proposes structured, allowlisted simulated remediation plans."""

from dataclasses import dataclass

from app.agents.trust import TrustAgent
from app.recovery.catalog import get_catalog_action
from app.schemas.investigation import EvidenceBundle, InvestigationResult
from app.schemas.remediation import PolicyEvaluationResult
from app.schemas.simulation import DetectedIncident
from app.simulator.engine import SimulationEngine


@dataclass
class RecoveryPlanDraft:
    """Structured recovery plan proposal before persistence (never executed by RecoveryAgent)."""

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
    policy_evaluation: PolicyEvaluationResult


class RecoveryAgent:
    """Selects an allowlisted simulated recovery action from evidence and submits to TrustAgent."""

    def __init__(self, trust_agent: TrustAgent | None = None) -> None:
        self._trust = trust_agent or TrustAgent()

    def propose_plan(
        self,
        *,
        incident: DetectedIncident,
        investigation: InvestigationResult | None,
        evidence_bundle: EvidenceBundle | None,
        engine: SimulationEngine,
        override_action_id: str | None = None,
        override_target_service: str | None = None,
        override_parameters: dict[str, float | int | str | bool] | None = None,
    ) -> RecoveryPlanDraft:
        """Select a safe remediation action, assemble structured rationale, and run TrustAgent."""
        action_id, target_service = self._select_action_and_target(
            incident=incident,
            investigation=investigation,
            override_action_id=override_action_id,
            override_target_service=override_target_service,
        )

        action_def = get_catalog_action(action_id)
        if action_def is not None:
            action_name = action_def.name
            parameters = dict(action_def.default_parameters)
            if override_parameters is not None:
                parameters = dict(override_parameters)
            expected_effects = [action_def.expected_effect]
            preconditions = list(action_def.preconditions)
            risks = self._build_risks(action_def.risk_classification, target_service)
        else:
            # Unknown action is preserved verbatim so TrustAgent explicitly DENYs it via POL-001
            action_name = f"Unrecognized Action ({action_id})"
            parameters = dict(override_parameters or {})
            expected_effects = ["None — action is not in the static allowlisted catalog."]
            preconditions = ["Action must exist in the static allowlist catalog."]
            risks = ["Unallowlisted actions are strictly prohibited by TrustAgent policy."]

        evidence_refs = self._collect_evidence_refs(incident, investigation, evidence_bundle)
        rationale = self._build_rationale(
            action_id=action_id,
            target_service=target_service,
            incident=incident,
            investigation=investigation,
            evidence_refs=evidence_refs,
        )
        limitations = [
            "Remediation is strictly simulated within the local NEXUS engine; no real infrastructure is modified.",
            "Recovery unfolds progressively over multiple simulation ticks and must pass Verification Agent SLO checks before incident resolution.",
        ]

        # Submit plan to independent TrustAgent policy gate
        policy_eval = self._trust.evaluate(
            action_id=action_id,
            target_service=target_service,
            parameters=parameters,
            evidence_refs=evidence_refs,
            incident=incident,
            investigation=investigation,
            engine=engine,
        )

        return RecoveryPlanDraft(
            action_id=action_id,
            action_name=action_name,
            target_service=target_service,
            parameters=parameters,
            evidence_refs=evidence_refs,
            rationale=rationale,
            expected_effects=expected_effects,
            limitations=limitations,
            risks=risks,
            preconditions=preconditions,
            policy_evaluation=policy_eval,
        )

    @staticmethod
    def _select_action_and_target(
        *,
        incident: DetectedIncident,
        investigation: InvestigationResult | None,
        override_action_id: str | None,
        override_target_service: str | None,
    ) -> tuple[str, str]:
        if override_action_id is not None:
            action_def = get_catalog_action(override_action_id)
            default_target = (
                action_def.allowed_targets[0]
                if action_def is not None
                else (incident.root_cause_candidate or "postgres-primary")
            )
            return override_action_id, override_target_service or default_target

        root = (
            (investigation.probable_root_cause_service if investigation else None)
            or incident.root_cause_candidate
            or "postgres-primary"
        )

        if root == "postgres-primary":
            return "expand_db_connection_pool", override_target_service or "postgres-primary"
        if root in ("order-queue", "worker-fulfillment"):
            return "scale_queue_consumers", override_target_service or root
        if root in ("payment-service", "checkout-api"):
            return "enable_circuit_breaker", override_target_service or root

        return "expand_db_connection_pool", override_target_service or "postgres-primary"

    @staticmethod
    def _collect_evidence_refs(
        incident: DetectedIncident,
        investigation: InvestigationResult | None,
        evidence_bundle: EvidenceBundle | None,
    ) -> list[str]:
        if investigation is not None and investigation.supporting_evidence:
            return [e.evidence_id for e in investigation.supporting_evidence[:8]]
        if evidence_bundle is not None and evidence_bundle.items:
            return [e.evidence_id for e in evidence_bundle.items[:8]]
        return [f"EVID-{ev.id}" for ev in incident.triggering_evidence[:8]]

    @staticmethod
    def _build_rationale(
        *,
        action_id: str,
        target_service: str,
        incident: DetectedIncident,
        investigation: InvestigationResult | None,
        evidence_refs: list[str],
    ) -> str:
        if investigation is not None:
            return (
                f"Selected '{action_id}' targeting '{target_service}' based on investigation "
                f"{investigation.id} (probable root cause: {investigation.probable_root_cause_service}, "
                f"confidence: {investigation.confidence.score:.2f}) supported by "
                f"{len(evidence_refs)} traceable evidence reference(s)."
            )
        return (
            f"Selected '{action_id}' targeting '{target_service}' based on deterministic "
            f"incident {incident.id} (candidate: {incident.root_cause_candidate}) supported by "
            f"{len(evidence_refs)} traceable evidence reference(s)."
        )

    @staticmethod
    def _build_risks(risk_classification: str, target_service: str) -> list[str]:
        if risk_classification == "HIGH":
            return [
                f"High-risk capacity change on critical service '{target_service}'; requires human authorization.",
                "If underlying contention is not pool-bound, latency recovery may be incomplete and fail verification.",
            ]
        if risk_classification == "MEDIUM":
            return [
                f"Circuit breaker on '{target_service}' may temporarily shed degraded upstream requests while stabilizing.",
                "Does not directly remediate an underlying database bottleneck on its own.",
            ]
        return [
            f"Scaling consumers on '{target_service}' increases downstream database write concurrency while draining backlog.",
        ]

