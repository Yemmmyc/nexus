import { useCallback, useEffect, useState } from "react";
import {
  CheckCircle2,
  FastForward,
  Play,
  ShieldAlert,
  ShieldCheck,
  Wrench,
  XCircle,
} from "lucide-react";
import {
  advanceSimulation,
  approveRemediationPlan,
  createRemediationPlan,
  executeRemediationPlan,
  fetchRemediationPlans,
  fetchRemediationVerification,
  rejectRemediationPlan,
} from "../../api/client";
import { Panel } from "../common/Panel";
import type { DetectedIncident } from "../../types/incidents";
import type {
  PolicyDecision,
  RemediationPlan,
  VerificationResult,
} from "../../types/remediation";

interface RecoveryOperationsPanelProps {
  incident: DetectedIncident;
  onStateChanged: () => void;
}

function policyBadgeStyle(decision: PolicyDecision): string {
  if (decision === "AUTO_APPROVE") {
    return "border-nexus-emerald/40 bg-nexus-emerald/15 text-emerald-200";
  }
  if (decision === "DENY") {
    return "border-nexus-crimson/50 bg-nexus-crimson/15 text-rose-200";
  }
  return "border-nexus-amber/50 bg-nexus-amber/15 text-amber-200";
}

export function RecoveryOperationsPanel({
  incident,
  onStateChanged,
}: RecoveryOperationsPanelProps) {
  const [plans, setPlans] = useState<RemediationPlan[]>([]);
  const [verification, setVerification] = useState<VerificationResult | null>(null);
  const [comment, setComment] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadPlans = useCallback(async () => {
    try {
      const list = await fetchRemediationPlans(incident.id);
      setPlans(list);
      const active = list[0] ?? null;
      if (active?.verification_result) {
        setVerification(active.verification_result);
      } else {
        setVerification(null);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load remediation plans");
    }
  }, [incident.id]);

  useEffect(() => {
    void loadPlans();
  }, [loadPlans]);

  const activePlan = plans[0] ?? null;

  const runAction = async (fn: () => Promise<void>) => {
    setIsBusy(true);
    setError(null);
    try {
      await fn();
      await loadPlans();
      onStateChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Recovery operation failed");
    } finally {
      setIsBusy(false);
    }
  };

  const canApproveOrReject =
    activePlan !== null &&
    activePlan.policy_decision === "REQUIRE_HUMAN_APPROVAL" &&
    activePlan.approval_status === "PENDING";

  const canExecute =
    activePlan !== null &&
    activePlan.execution_status === "NOT_STARTED" &&
    (activePlan.policy_decision === "AUTO_APPROVE" ||
      (activePlan.policy_decision === "REQUIRE_HUMAN_APPROVAL" &&
        activePlan.approval_status === "APPROVED"));

  const canVerify =
    activePlan !== null &&
    activePlan.execution_status === "COMPLETED" &&
    activePlan.verification_status !== "VERIFIED" &&
    activePlan.verification_status !== "FAILED";

  return (
    <Panel
      title="Policy-Gated Recovery Operations"
      subtitle="Allowlisted simulated remediation, Trust Agent policy enforcement, human approval, and SLO verification"
      rightSlot={
        !activePlan && incident.status !== "RESOLVED" ? (
          <button
            type="button"
            disabled={isBusy}
            onClick={() =>
              void runAction(async () => {
                await createRemediationPlan(incident.id);
              })
            }
            className="inline-flex items-center gap-1.5 rounded-lg border border-nexus-teal/50 bg-nexus-teal/15 px-3.5 py-2 text-xs font-medium text-teal-100 transition hover:bg-nexus-teal/25 disabled:opacity-50"
          >
            <Wrench className="h-3.5 w-3.5" />
            Propose Recovery Plan
          </button>
        ) : activePlan ? (
          <span
            className={`rounded border px-2.5 py-1 font-mono text-[10px] font-semibold ${policyBadgeStyle(
              activePlan.policy_decision
            )}`}
          >
            POLICY: {activePlan.policy_decision}
          </span>
        ) : null
      }
    >
      {error ? (
        <div className="mb-4 rounded-lg border border-nexus-crimson/40 bg-nexus-crimson/10 px-3.5 py-2.5 text-xs text-rose-200">
          {error}
        </div>
      ) : null}

      {!activePlan ? (
        <div className="rounded-lg border border-dashed border-obsidian-700 bg-obsidian-950/75 p-5 text-center">
          <ShieldCheck className="mx-auto h-6 w-6 text-nexus-teal" />
          <p className="mt-2 text-sm font-medium text-slate-200">
            No recovery plan proposed yet for {incident.id}.
          </p>
          <p className="mt-1 text-xs text-slate-400">
            Click <span className="font-semibold text-nexus-teal">Propose Recovery Plan</span> to
            invoke the Recovery Agent and evaluate the Trust Agent policy gate.
          </p>
        </div>
      ) : (
        <div className="space-y-5">
          {/* Plan Header & Rationale */}
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="space-y-2.5 rounded-lg border border-obsidian-700/80 bg-obsidian-950/80 p-4 lg:col-span-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs font-semibold text-nexus-cyan">
                  {activePlan.id}
                </span>
                <span className="rounded bg-obsidian-800 px-2 py-0.5 font-mono text-[11px] text-slate-100">
                  {activePlan.action_id}
                </span>
                <span className="font-mono text-[11px] text-slate-400">
                  target: <span className="text-slate-200">{activePlan.target_service}</span>
                </span>
              </div>
              <p className="text-sm font-semibold text-slate-100">{activePlan.action_name}</p>
              <p className="text-xs leading-relaxed text-slate-300">{activePlan.rationale}</p>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {activePlan.evidence_refs.map((ref) => (
                  <span
                    key={ref}
                    className="rounded border border-obsidian-700 bg-obsidian-900 px-2 py-0.5 font-mono text-[10px] text-nexus-cyan"
                  >
                    {ref}
                  </span>
                ))}
              </div>
            </div>

            {/* Trust Policy Gate Verdict */}
            <div className="rounded-lg border border-obsidian-700/80 bg-obsidian-950/80 p-4">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] uppercase tracking-wider text-slate-400">
                  Trust Policy Gate
                </span>
                <ShieldAlert className="h-4 w-4 text-nexus-amber" />
              </div>
              <div className="mt-2.5 space-y-1.5 text-xs">
                <div className="flex justify-between font-mono">
                  <span className="text-slate-400">Approval:</span>
                  <span className="text-slate-100">{activePlan.approval_status}</span>
                </div>
                <div className="flex justify-between font-mono">
                  <span className="text-slate-400">Execution:</span>
                  <span className="text-slate-100">{activePlan.execution_status}</span>
                </div>
                <div className="flex justify-between font-mono">
                  <span className="text-slate-400">Verification:</span>
                  <span className="text-nexus-cyan">{activePlan.verification_status}</span>
                </div>
              </div>
              <ul className="mt-3 space-y-1.5 border-t border-obsidian-700/60 pt-2.5 text-[11px] text-slate-400">
                {activePlan.policy_evaluation.reasons.map((r, idx) => (
                  <li key={idx} className="leading-relaxed">
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Expected Effects, Risks & Preconditions */}
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="rounded-lg border border-obsidian-700/70 bg-obsidian-950/75 p-3.5 text-xs">
              <div className="font-mono text-[10px] uppercase tracking-wider text-nexus-emerald">
                Expected Simulated Effect
              </div>
              <ul className="mt-2 space-y-1.5 text-slate-300">
                {activePlan.expected_effects.map((e, i) => (
                  <li key={i}>• {e}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-lg border border-obsidian-700/70 bg-obsidian-950/75 p-3.5 text-xs">
              <div className="font-mono text-[10px] uppercase tracking-wider text-amber-300">
                Risks
              </div>
              <ul className="mt-2 space-y-1.5 text-slate-300">
                {activePlan.risks.map((r, i) => (
                  <li key={i}>• {r}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-lg border border-obsidian-700/70 bg-obsidian-950/75 p-3.5 text-xs">
              <div className="font-mono text-[10px] uppercase tracking-wider text-slate-400">
                Preconditions
              </div>
              <ul className="mt-2 space-y-1.5 text-slate-300">
                {activePlan.preconditions.map((p, i) => (
                  <li key={i}>• {p}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* Human Approval Controls */}
          {canApproveOrReject ? (
            <div className="rounded-lg border border-nexus-amber/40 bg-nexus-amber/10 p-4">
              <div className="text-xs font-semibold text-amber-200">
                Human Authorization Required (Demo Operator Identity: sre-operator)
              </div>
              <div className="mt-2.5 flex flex-wrap items-center gap-2.5">
                <input
                  type="text"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="Optional operator justification note..."
                  className="min-w-[240px] flex-1 rounded-lg border border-obsidian-700 bg-obsidian-950 px-3 py-2 text-xs text-slate-100 placeholder:text-slate-500 focus:border-nexus-cyan focus:outline-none"
                />
                <button
                  type="button"
                  disabled={isBusy}
                  onClick={() =>
                    void runAction(async () => {
                      await approveRemediationPlan(
                        activePlan.id,
                        "sre-operator",
                        comment || "Approved based on verified telemetry evidence."
                      );
                    })
                  }
                  className="inline-flex items-center gap-1.5 rounded-lg border border-nexus-emerald/50 bg-nexus-emerald/20 px-3.5 py-2 text-xs font-medium text-emerald-100 transition hover:bg-nexus-emerald/30 disabled:opacity-50"
                >
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Approve Plan
                </button>
                <button
                  type="button"
                  disabled={isBusy}
                  onClick={() =>
                    void runAction(async () => {
                      await rejectRemediationPlan(
                        activePlan.id,
                        "sre-operator",
                        comment || "Rejected by operator."
                      );
                    })
                  }
                  className="inline-flex items-center gap-1.5 rounded-lg border border-nexus-crimson/50 bg-nexus-crimson/15 px-3.5 py-2 text-xs font-medium text-rose-200 transition hover:bg-nexus-crimson/25 disabled:opacity-50"
                >
                  <XCircle className="h-3.5 w-3.5" />
                  Reject
                </button>
              </div>
            </div>
          ) : null}

          {/* Execution & Verification Actions */}
          <div className="flex flex-wrap items-center gap-2.5">
            {canExecute ? (
              <button
                type="button"
                disabled={isBusy}
                onClick={() =>
                  void runAction(async () => {
                    await executeRemediationPlan(activePlan.id);
                  })
                }
                className="inline-flex items-center gap-1.5 rounded-lg border border-nexus-cyan/50 bg-nexus-cyan/20 px-4 py-2 text-xs font-medium text-cyan-100 transition hover:bg-nexus-cyan/30 disabled:opacity-50"
              >
                <Play className="h-3.5 w-3.5" />
                Execute Simulated Recovery
              </button>
            ) : null}

            {canVerify ? (
              <>
                <button
                  type="button"
                  disabled={isBusy}
                  onClick={() =>
                    void runAction(async () => {
                      await advanceSimulation(2);
                      const res = await fetchRemediationVerification(activePlan.id);
                      setVerification(res);
                    })
                  }
                  className="inline-flex items-center gap-1.5 rounded-lg border border-nexus-teal/50 bg-nexus-teal/15 px-3.5 py-2 text-xs font-medium text-teal-100 transition hover:bg-nexus-teal/25 disabled:opacity-50"
                >
                  <FastForward className="h-3.5 w-3.5" />
                  Advance +2 Ticks &amp; Verify
                </button>
                <button
                  type="button"
                  disabled={isBusy}
                  onClick={() =>
                    void runAction(async () => {
                      const res = await fetchRemediationVerification(activePlan.id);
                      setVerification(res);
                    })
                  }
                  className="inline-flex items-center gap-1.5 rounded-lg border border-obsidian-700 bg-obsidian-850 px-3.5 py-2 text-xs font-medium text-slate-200 transition hover:border-nexus-cyan/50 hover:text-nexus-cyan disabled:opacity-50"
                >
                  <ShieldCheck className="h-3.5 w-3.5" />
                  Check Verification
                </button>
              </>
            ) : null}
          </div>

          {/* Execution Record & Verification Telemetry */}
          {activePlan.execution_record ? (
            <div className="rounded-lg border border-obsidian-700/80 bg-obsidian-950/80 p-4 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono text-[11px] uppercase tracking-wider text-nexus-cyan">
                  Simulated Execution Record ({activePlan.execution_record.execution_id})
                </span>
                <span className="font-mono text-[11px] text-slate-400">
                  applied_tick={activePlan.execution_record.applied_tick} ·{" "}
                  {activePlan.execution_record.execution_identifier}
                </span>
              </div>
              <p className="mt-1.5 text-slate-300">
                {activePlan.execution_record.modeled_effect_summary}
              </p>
            </div>
          ) : null}

          {verification ? (
            <div className="rounded-lg border border-obsidian-700/80 bg-obsidian-950/80 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono text-[11px] uppercase tracking-wider text-slate-300">
                  Verification Agent — SLO Recovery Check
                </span>
                <span
                  className={`rounded border px-2 py-0.5 font-mono text-[10px] font-semibold ${
                    verification.status === "VERIFIED"
                      ? "border-nexus-emerald/50 bg-nexus-emerald/15 text-emerald-200"
                      : verification.status === "FAILED"
                        ? "border-nexus-crimson/50 bg-nexus-crimson/15 text-rose-200"
                        : "border-nexus-cyan/40 bg-nexus-cyan/10 text-cyan-200"
                  }`}
                >
                  {verification.status} · {verification.consecutive_healthy_ticks}/
                  {verification.required_consecutive_healthy_ticks} HEALTHY TICKS
                </span>
              </div>
              <p className="mt-2 text-xs text-slate-300">{verification.summary}</p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {verification.checks.map((c) => (
                  <div
                    key={c.service_id}
                    className="rounded border border-obsidian-700/70 bg-obsidian-900/80 p-2.5 font-mono text-[11px]"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-slate-100">{c.service_id}</span>
                      <span
                        className={c.passed ? "text-nexus-emerald" : "text-nexus-amber"}
                      >
                        {c.passed ? "PASS" : c.status.toUpperCase()}
                      </span>
                    </div>
                    <div className="mt-1 text-[10px] text-slate-400">
                      lat={c.latency_ms.toFixed(0)}ms · err={(c.error_rate * 100).toFixed(1)}% · q=
                      {c.queue_depth}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      )}
    </Panel>
  );
}

