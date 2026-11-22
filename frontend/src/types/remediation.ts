import type { ServiceHealthStatus } from "./incidents";

export type RiskClassification = "LOW" | "MEDIUM" | "HIGH";
export type PolicyDecision = "AUTO_APPROVE" | "REQUIRE_HUMAN_APPROVAL" | "DENY";
export type ApprovalStatus = "NOT_REQUIRED" | "PENDING" | "APPROVED" | "REJECTED" | "DENIED";
export type ExecutionStatus = "NOT_STARTED" | "RUNNING" | "COMPLETED" | "FAILED";
export type VerificationStatus = "NOT_STARTED" | "IN_PROGRESS" | "VERIFIED" | "FAILED";

export interface PolicyRuleMatch {
  rule_id: string;
  outcome: PolicyDecision;
  reason: string;
}

export interface PolicyEvaluationResult {
  decision: PolicyDecision;
  matched_rules: PolicyRuleMatch[];
  reasons: string[];
  evaluated_at: string;
}

export interface ExecutionRecord {
  execution_id: string;
  plan_id: string;
  incident_id: string;
  action_id: string;
  execution_identifier: string;
  target_service: string;
  parameters: Record<string, number | string | boolean>;
  status: ExecutionStatus;
  applied_tick: number;
  applied_sim_time_s: number;
  modeled_effect_summary: string;
  started_at: string;
  completed_at: string | null;
  error: string | null;
}

export interface ServiceVerificationCheck {
  service_id: string;
  status: ServiceHealthStatus;
  latency_ms: number;
  slo_latency_ms: number;
  error_rate: number;
  slo_error_rate: number;
  saturation_pct: number;
  queue_depth: number;
  passed: boolean;
  note: string;
}

export interface VerificationResult {
  plan_id: string;
  incident_id: string;
  status: VerificationStatus;
  evaluated_tick: number;
  evaluated_sim_time_s: number;
  applied_tick: number;
  elapsed_ticks_since_execution: number;
  consecutive_healthy_ticks: number;
  required_consecutive_healthy_ticks: number;
  max_verification_ticks: number;
  resilience_score: number;
  checks: ServiceVerificationCheck[];
  summary: string;
  evaluated_at: string;
}

export interface RemediationPlan {
  id: string;
  incident_id: string;
  action_id: string;
  action_name: string;
  target_service: string;
  parameters: Record<string, number | string | boolean>;
  evidence_refs: string[];
  rationale: string;
  expected_effects: string[];
  limitations: string[];
  risks: string[];
  preconditions: string[];
  policy_decision: PolicyDecision;
  policy_evaluation: PolicyEvaluationResult;
  approval_status: ApprovalStatus;
  approved_by: string | null;
  approval_comment: string | null;
  approved_at: string | null;
  execution_status: ExecutionStatus;
  execution_record: ExecutionRecord | null;
  verification_status: VerificationStatus;
  verification_result: VerificationResult | null;
  created_at: string;
  updated_at: string;
}

