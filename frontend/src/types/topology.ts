import type { ServiceHealthStatus } from "./incidents";

export interface ServiceMetrics {
  latency_ms: number;
  error_rate: number;
  throughput_rps: number;
  cpu_pct: number;
  saturation_pct: number;
  queue_depth: number;
}

export interface ServiceNodeState {
  id: string;
  name: string;
  tier: string;
  status: ServiceHealthStatus;
  criticality: number;
  baseline_latency_ms: number;
  slo_latency_ms: number;
  slo_error_rate: number;
  metrics: ServiceMetrics;
  in_blast_radius: boolean;
  is_root_cause_candidate: boolean;
}

export interface DependencyEdgeState {
  id: string;
  source: string;
  target: string;
  protocol: string;
  impact_weight: number;
  status: ServiceHealthStatus;
  latency_ms: number;
}

export interface TopologyResponse {
  tick: number;
  sim_time_s: number;
  active_scenario: string | null;
  nodes: ServiceNodeState[];
  edges: DependencyEdgeState[];
}

