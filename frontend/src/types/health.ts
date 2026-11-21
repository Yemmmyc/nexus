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

