import { Cpu, Database, RefreshCw } from "lucide-react";
import type { HealthResponse, NavSection } from "../../types/health";

interface TopBarProps {
  activeSection: NavSection;
  health: HealthResponse | null;
  healthError: string | null;
  isCheckingHealth: boolean;
  onRefreshHealth: () => void;
}

const SECTION_META: Record<NavSection, { title: string; subtitle: string }> = {
  overview: {
    title: "Executive Resilience Overview",
    subtitle: "Predict. Investigate. Recover. Verify.",
  },
  topology: {
    title: "Infrastructure Topology",
    subtitle: "7-service checkout & payments dependency map",
  },
  incidents: {
    title: "Incidents & AI Investigation",
    subtitle: "Correlated events, evidence-based RCA, and policy-gated recovery",
  },
  audit: {
    title: "Governance & Audit Trail",
    subtitle: "Immutable chronological record of system, agent, policy, and operator actions",
  },
};

export function TopBar({
  activeSection,
  health,
  healthError,
  isCheckingHealth,
  onRefreshHealth,
}: TopBarProps) {
  const meta = SECTION_META[activeSection];
  const isHealthy = health?.status === "ok" && !healthError;

  return (
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-obsidian-700/80 bg-obsidian-900/80 px-6 py-4 backdrop-blur-md">
      <div>
        <h1 className="text-lg font-semibold tracking-tight text-slate-50">{meta.title}</h1>
        <p className="text-xs text-slate-400">{meta.subtitle}</p>
      </div>

      <div className="flex flex-wrap items-center gap-2.5">
        <div className="flex items-center gap-2 rounded-lg border border-obsidian-700/80 bg-obsidian-950/90 px-3 py-1.5 text-xs">
          <span
            className={`h-2 w-2 rounded-full ${
              isHealthy
                ? "bg-nexus-emerald shadow-[0_0_8px_rgba(16,185,129,0.75)]"
                : "bg-nexus-amber"
            }`}
          />
          <span className="font-mono text-slate-300">
            API: {isHealthy ? "ONLINE" : healthError ? "OFFLINE" : "CHECKING"}
          </span>
        </div>

        <div className="hidden items-center gap-1.5 rounded-lg border border-obsidian-700/80 bg-obsidian-950/90 px-3 py-1.5 font-mono text-xs text-slate-300 sm:flex">
          <Database className="h-3.5 w-3.5 text-nexus-teal" />
          <span>SQLite: {health?.db_connected ? "READY" : "—"}</span>
        </div>

        <div className="hidden items-center gap-1.5 rounded-lg border border-obsidian-700/80 bg-obsidian-950/90 px-3 py-1.5 font-mono text-xs text-slate-300 md:flex">
          <Cpu className="h-3.5 w-3.5 text-nexus-cyan" />
          <span>AI: {(health?.ai_mode ?? "deterministic").toUpperCase()}</span>
        </div>

        <button
          type="button"
          onClick={onRefreshHealth}
          disabled={isCheckingHealth}
          className="inline-flex items-center gap-1.5 rounded-lg border border-obsidian-700 bg-obsidian-850 px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:border-nexus-cyan/50 hover:text-nexus-cyan disabled:opacity-50"
          title="Re-check backend health"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isCheckingHealth ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>
    </header>
  );
}

