import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  FastForward,
  Flame,
  Layers,
  Play,
  RotateCcw,
  Shield,
  Square,
} from "lucide-react";
import { Panel } from "../components/common/Panel";
import type { HealthResponse, SimulationStatusResponse } from "../types/health";

interface DashboardViewProps {
  health: HealthResponse | null;
  simStatus: SimulationStatusResponse | null;
  isSimBusy: boolean;
  onStartSim: () => void;
  onStopSim: () => void;
  onAdvanceTick: () => void;
  onInjectDbCascade: () => void;
  onResetSim: () => void;
}

export function DashboardView({
  health,
  simStatus,
  isSimBusy,
  onStartSim,
  onStopSim,
  onAdvanceTick,
  onInjectDbCascade,
  onResetSim,
}: DashboardViewProps) {
  const resilience = simStatus ? simStatus.resilience_score.toFixed(1) : "100.0";
  const activeIncidents = simStatus?.active_incidents_count ?? 0;
  const healthyCount = simStatus?.healthy_services ?? 7;
  const degradedCount = simStatus?.degraded_services ?? 0;
  const criticalCount = simStatus?.critical_services ?? 0;

  const kpiCards = [
    {
      label: "Resilience Score",
      value: resilience,
      unit: "/ 100",
      detail: simStatus
        ? `Tick ${simStatus.tick} · Sim time ${simStatus.sim_time_s.toFixed(0)}s`
        : "Connecting to simulator...",
      accent:
        (simStatus?.resilience_score ?? 100) < 70
          ? "text-nexus-crimson"
          : (simStatus?.resilience_score ?? 100) < 90
            ? "text-nexus-amber"
            : "text-nexus-cyan",
      icon: Shield,
    },
    {
      label: "Active Incidents",
      value: String(activeIncidents),
      unit: "open",
      detail:
        simStatus?.active_scenario
          ? `Scenario: ${simStatus.active_scenario}`
          : "No active fault scenario",
      accent: activeIncidents > 0 ? "text-nexus-crimson" : "text-nexus-emerald",
      icon: AlertTriangle,
    },
    {
      label: "Service Health",
      value: `${healthyCount}/${simStatus?.total_services ?? 7}`,
      unit: "healthy",
      detail: `${degradedCount} degraded · ${criticalCount} critical`,
      accent:
        criticalCount > 0
          ? "text-nexus-crimson"
          : degradedCount > 0
            ? "text-nexus-amber"
            : "text-nexus-teal",
      icon: Layers,
    },
    {
      label: "Simulator Engine",
      value: simStatus?.running ? "RUNNING" : "IDLE",
      unit: `${simStatus?.tick_interval_seconds ?? 2}s`,
      detail: "Deterministic local propagation engine",
      accent: simStatus?.running ? "text-nexus-emerald" : "text-slate-100",
      icon: CheckCircle2,
    },
  ];

  return (
    <div className="space-y-6">
      <Panel
        title="Simulation Controls"
        subtitle="Phase 1 deterministic infrastructure simulator — control tick loop and inject cascading failures"
        rightSlot={
          <span
            className={`rounded-md border px-2.5 py-1 font-mono text-[11px] ${
              simStatus?.running
                ? "border-nexus-emerald/40 bg-nexus-emerald/10 text-nexus-emerald"
                : "border-obsidian-700 bg-obsidian-950 text-slate-400"
            }`}
          >
            {simStatus?.running ? "LOOP ACTIVE" : "STEP / STANDBY"}
          </span>
        }
      >
        <div className="flex flex-wrap items-center gap-2.5">
          {!simStatus?.running ? (
            <button
              type="button"
              disabled={isSimBusy}
              onClick={onStartSim}
              className="inline-flex items-center gap-1.5 rounded-lg border border-nexus-emerald/40 bg-nexus-emerald/15 px-3.5 py-2 text-xs font-medium text-emerald-200 transition hover:bg-nexus-emerald/25 disabled:opacity-50"
            >
              <Play className="h-3.5 w-3.5" />
              Start Simulation
            </button>
          ) : (
            <button
              type="button"
              disabled={isSimBusy}
              onClick={onStopSim}
              className="inline-flex items-center gap-1.5 rounded-lg border border-nexus-amber/40 bg-nexus-amber/15 px-3.5 py-2 text-xs font-medium text-amber-200 transition hover:bg-nexus-amber/25 disabled:opacity-50"
            >
              <Square className="h-3.5 w-3.5" />
              Stop Simulation
            </button>
          )}

          <button
            type="button"
            disabled={isSimBusy}
            onClick={onAdvanceTick}
            className="inline-flex items-center gap-1.5 rounded-lg border border-obsidian-700 bg-obsidian-850 px-3.5 py-2 text-xs font-medium text-slate-200 transition hover:border-nexus-cyan/50 hover:text-nexus-cyan disabled:opacity-50"
          >
            <FastForward className="h-3.5 w-3.5" />
            Advance +1 Tick
          </button>

          <button
            type="button"
            disabled={isSimBusy}
            onClick={onInjectDbCascade}
            className="inline-flex items-center gap-1.5 rounded-lg border border-nexus-crimson/40 bg-nexus-crimson/15 px-3.5 py-2 text-xs font-medium text-rose-200 transition hover:bg-nexus-crimson/25 disabled:opacity-50"
          >
            <Flame className="h-3.5 w-3.5" />
            Inject db_latency_cascade
          </button>

          <button
            type="button"
            disabled={isSimBusy}
            onClick={onResetSim}
            className="inline-flex items-center gap-1.5 rounded-lg border border-obsidian-700 bg-obsidian-950 px-3.5 py-2 text-xs font-medium text-slate-300 transition hover:border-slate-500 hover:text-slate-100 disabled:opacity-50"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Reset Baseline
          </button>
        </div>
      </Panel>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {kpiCards.map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.label}
              className="rounded-xl border border-obsidian-700/80 bg-obsidian-900/90 p-5 shadow-panel"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-slate-400">
                  {card.label}
                </span>
                <Icon className="h-4 w-4 text-slate-500" />
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className={`font-mono text-2xl font-semibold ${card.accent}`}>
                  {card.value}
                </span>
                <span className="font-mono text-xs text-slate-500">{card.unit}</span>
              </div>
              <p className="mt-2 text-xs text-slate-400">{card.detail}</p>
            </div>
          );
        })}
      </div>

      <Panel
        title="Platform Readiness"
        subtitle="Live backend & deterministic simulator status"
        rightSlot={<Activity className="h-4 w-4 text-nexus-cyan" />}
      >
        <dl className="grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg border border-obsidian-700/60 bg-obsidian-950/75 p-3">
            <dt className="text-slate-400">API Version</dt>
            <dd className="mt-1 font-mono text-slate-100">/api/v1 ({health?.version ?? "0.1.0"})</dd>
          </div>
          <div className="rounded-lg border border-obsidian-700/60 bg-obsidian-950/75 p-3">
            <dt className="text-slate-400">Database Engine</dt>
            <dd className="mt-1 font-mono text-nexus-emerald">
              {health?.db_connected ? "SQLite Connected" : "Awaiting API"}
            </dd>
          </div>
          <div className="rounded-lg border border-obsidian-700/60 bg-obsidian-950/75 p-3">
            <dt className="text-slate-400">AI Mode</dt>
            <dd className="mt-1 font-mono uppercase text-nexus-cyan">
              {health?.ai_mode ?? "deterministic"}
            </dd>
          </div>
          <div className="rounded-lg border border-obsidian-700/60 bg-obsidian-950/75 p-3">
            <dt className="text-slate-400">Execution Boundary</dt>
            <dd className="mt-1 font-mono text-nexus-teal">Simulated Only</dd>
          </div>
        </dl>
      </Panel>
    </div>
  );
}
