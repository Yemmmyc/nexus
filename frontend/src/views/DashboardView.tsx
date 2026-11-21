import { Activity, AlertTriangle, CheckCircle2, Layers, Shield } from "lucide-react";
import { Panel } from "../components/common/Panel";
import type { HealthResponse } from "../types/health";

interface DashboardViewProps {
  health: HealthResponse | null;
}

const KPI_CARDS = [
  {
    label: "Resilience Score",
    value: "98.0",
    unit: "/ 100",
    detail: "Baseline standby — simulator activates in Phase 1",
    accent: "text-nexus-cyan",
    icon: Shield,
  },
  {
    label: "Active Incidents",
    value: "0",
    unit: "open",
    detail: "0 critical · 0 high · 0 medium",
    accent: "text-nexus-emerald",
    icon: AlertTriangle,
  },
  {
    label: "Monitored Services",
    value: "7",
    unit: "nodes",
    detail: "8 dependency edges seeded in SQLite",
    accent: "text-nexus-teal",
    icon: Layers,
  },
  {
    label: "Policy Gate Status",
    value: "ACTIVE",
    unit: "safe",
    detail: "Allowlisted simulated remediation only",
    accent: "text-slate-100",
    icon: CheckCircle2,
  },
];

export function DashboardView({ health }: DashboardViewProps) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {KPI_CARDS.map((card) => {
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

      <div className="grid gap-6 xl:grid-cols-3">
        <Panel
          title="Infrastructure Health Matrix"
          subtitle="Seeded 7-service fintech topology (Phase 0 baseline)"
          className="xl:col-span-2"
          rightSlot={
            <span className="rounded-md border border-nexus-emerald/30 bg-nexus-emerald/10 px-2.5 py-1 font-mono text-[11px] text-nexus-emerald">
              ALL SYSTEMS STANDBY
            </span>
          }
        >
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {[
              { id: "api-gateway", tier: "edge", slo: "300ms" },
              { id: "auth-service", tier: "application", slo: "200ms" },
              { id: "checkout-api", tier: "application", slo: "350ms" },
              { id: "payment-service", tier: "application", slo: "400ms" },
              { id: "order-queue", tier: "messaging", slo: "150ms" },
              { id: "worker-fulfillment", tier: "worker", slo: "500ms" },
              { id: "postgres-primary", tier: "database", slo: "100ms" },
            ].map((svc) => (
              <div
                key={svc.id}
                className="flex items-center justify-between rounded-lg border border-obsidian-700/70 bg-obsidian-950/75 px-3.5 py-3"
              >
                <div>
                  <div className="font-mono text-xs font-medium text-slate-100">{svc.id}</div>
                  <div className="mt-0.5 text-[11px] uppercase tracking-wider text-slate-500">
                    {svc.tier} · SLO {svc.slo}
                  </div>
                </div>
                <span className="h-2.5 w-2.5 rounded-full bg-nexus-emerald/80 shadow-[0_0_8px_rgba(16,185,129,0.55)]" />
              </div>
            ))}
          </div>
        </Panel>

        <Panel
          title="Platform Readiness"
          subtitle="Live backend telemetry & scaffold status"
          rightSlot={<Activity className="h-4 w-4 text-nexus-cyan" />}
        >
          <dl className="space-y-3 text-xs">
            <div className="flex items-center justify-between border-b border-obsidian-700/60 pb-2.5">
              <dt className="text-slate-400">API Version</dt>
              <dd className="font-mono text-slate-100">/api/v1 ({health?.version ?? "0.1.0"})</dd>
            </div>
            <div className="flex items-center justify-between border-b border-obsidian-700/60 pb-2.5">
              <dt className="text-slate-400">Database Engine</dt>
              <dd className="font-mono text-nexus-emerald">
                {health?.db_connected ? "SQLite Connected" : "Awaiting API"}
              </dd>
            </div>
            <div className="flex items-center justify-between border-b border-obsidian-700/60 pb-2.5">
              <dt className="text-slate-400">AI Investigator Mode</dt>
              <dd className="font-mono uppercase text-nexus-cyan">
                {health?.ai_mode ?? "deterministic"}
              </dd>
            </div>
            <div className="flex items-center justify-between border-b border-obsidian-700/60 pb-2.5">
              <dt className="text-slate-400">Simulator Loop</dt>
              <dd className="font-mono text-slate-300">
                {health?.simulator_running ? "Running" : "Phase 1 Pending"}
              </dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-slate-400">Execution Boundary</dt>
              <dd className="font-mono text-nexus-teal">Simulated Only</dd>
            </div>
          </dl>
        </Panel>
      </div>
    </div>
  );
}

