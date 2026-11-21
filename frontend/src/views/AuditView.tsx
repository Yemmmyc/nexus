import { FileClock, Lock } from "lucide-react";
import { Panel } from "../components/common/Panel";

export function AuditView() {
  return (
    <div className="space-y-6">
      <Panel
        title="Immutable Audit Ledger"
        subtitle="Append-only SQLite record of all detections, AI evidence, policy verdicts, approvals, and simulated executions"
        rightSlot={
          <span className="inline-flex items-center gap-1.5 rounded-md border border-nexus-teal/30 bg-nexus-teal/10 px-2.5 py-1 font-mono text-[11px] text-nexus-teal">
            <Lock className="h-3 w-3" />
            APPEND-ONLY
          </span>
        }
      >
        <div className="flex flex-wrap gap-2 pb-4">
          {["ALL", "SYSTEM", "AGENT", "POLICY", "HUMAN"].map((actor, idx) => (
            <span
              key={actor}
              className={`rounded-md border px-2.5 py-1 font-mono text-[11px] ${
                idx === 0
                  ? "border-nexus-cyan/40 bg-nexus-cyan/10 text-nexus-cyan"
                  : "border-obsidian-700 bg-obsidian-950 text-slate-400"
              }`}
            >
              {actor}
            </span>
          ))}
        </div>

        <div className="rounded-lg border border-obsidian-700/70 bg-obsidian-950/75 p-6 text-center">
          <FileClock className="mx-auto h-6 w-6 text-slate-500" />
          <p className="mt-2 text-sm font-medium text-slate-200">
            Audit ledger initialized and awaiting operational events.
          </p>
          <p className="mt-1 text-xs text-slate-400">
            Every fault injection, agent trace, policy evaluation, human approval, and verification
            result will stream here automatically.
          </p>
        </div>
      </Panel>
    </div>
  );
}

