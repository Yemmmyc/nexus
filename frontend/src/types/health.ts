export type NavSection = "overview" | "topology" | "incidents" | "audit";

export interface HealthResponse {
  status: "ok" | "degraded";
  service: string;
  version: string;
  environment: string;
  ai_mode: "auto" | "llm" | "deterministic";
  llm_configured: boolean;
  simulator_running: boolean;
  db_connected: boolean;
  timestamp: string;
}

export interface SimulationStatusResponse {
  running: boolean;
  tick: number;
  sim_time_s: number;
  tick_interval_seconds: number;
  active_scenario: string | null;
  resilience_score: number;
  total_services: number;
  healthy_services: number;
  degraded_services: number;
  critical_services: number;
  active_incidents_count: number;
}

