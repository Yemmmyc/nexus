import { Bot, ShieldAlert } from "lucide-react";
import { Panel } from "../components/common/Panel";

const AGENT_PIPELINE = [
  { name: "Observer", role: "Correlate telemetry & alerts into unified incidents", mode: "Deterministic" },
  { name: "Investigator", role: "Evidence-grounded root cause analysis & limitations", mode: "LLM + Fallback" },
  { name: "Risk", role: "Dependency blast radius & 0–100 composite risk score", mode: "Deterministic" },
  { name: "Recovery", role: "Propose ordered allowlisted simulated actions", mode: "Allowlist Only" },
  { name: "Trust", role: "Enforce safety & approval policies before execution", mode: "Policy Gate" },
  { name: "Verification", role: "Validate post-remediation SLO recovery window", mode: "SLO Check" },
];

export function IncidentsView() {
  return (
    <div className="space-y-6">
      <Panel
        title="Active Incident Queue"
        subtitle="Correlated incidents and policy-gated recovery workflows"
        rightSlot={
          <span className="inline-flex items-center gap-1.5 rounded-md border border-obsidian-700 bg-obsidian-950 px-2.5 py-1 font-mono text-[11px] text-slate-300">
            <ShieldAlert className="h-3.5 w-3.5 text-nexus-teal" />
            0 ACTIVE INCIDENTS
          </span>
        }
      >
        <div className="rounded-lg border border-obsidian-700/70 bg-obsidian-950/75 p-6 text-center">
          <p className="text-sm font-medium text-slate-200">No active incidents detected.</p>
          <p className="mt-1 text-xs text-slate-400">
            Fault injection controls and live incident correlation will be wired in Phase 1 and
            Phase 2.
          </p>
        </div>
      </Panel>

      <Panel
        title="6-Agent Resilience Pipeline Architecture"
        subtitle="Lightweight logical agents with strict Pydantic contracts and visible evidence"
        rightSlot={<Bot className="h-4 w-4 text-nexus-cyan" />}
      >
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {AGENT_PIPELINE.map((agent, index) => (
            <div
              key={agent.name}
              className="rounded-lg border border-obsidian-700/70 bg-obsidian-950/80 p-4"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-semibold text-slate-100">
                  0{index + 1}. {agent.name}
                </span>
                <span className="rounded bg-obsidian-800 px-2 py-0.5 font-mono text-[10px] text-nexus-cyan">
                  {agent.mode}
                </span>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-slate-400">{agent.role}</p>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

