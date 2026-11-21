import {
  Activity,
  FileClock,
  LayoutDashboard,
  Network,
  ShieldCheck,
  Siren,
} from "lucide-react";
import type { NavSection } from "../../types/health";

interface SidebarProps {
  activeSection: NavSection;
  onSelectSection: (section: NavSection) => void;
  aiMode: string;
}

const NAV_ITEMS: Array<{
  id: NavSection;
  label: string;
  caption: string;
  icon: typeof LayoutDashboard;
}> = [
  { id: "overview", label: "Overview", caption: "Resilience & KPIs", icon: LayoutDashboard },
  { id: "topology", label: "Topology", caption: "Dependency Graph", icon: Network },
  { id: "incidents", label: "Incidents", caption: "AI RCA & Recovery", icon: Siren },
  { id: "audit", label: "Audit Trail", caption: "Immutable Ledger", icon: FileClock },
];

export function Sidebar({ activeSection, onSelectSection, aiMode }: SidebarProps) {
  return (
    <aside className="flex w-full flex-col border-b border-obsidian-700/80 bg-obsidian-900/95 lg:w-64 lg:shrink-0 lg:border-b-0 lg:border-r">
      <div className="flex items-center gap-3 border-b border-obsidian-700/70 px-5 py-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-nexus-cyan/40 bg-nexus-cyan/10 text-nexus-cyan shadow-cyan-subtle">
          <ShieldCheck className="h-5 w-5" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-bold tracking-[0.18em] text-slate-50">
              NEXUS
            </span>
            <span className="rounded bg-obsidian-800 px-1.5 py-0.5 font-mono text-[10px] font-medium text-nexus-cyan">
              v0.1
            </span>
          </div>
          <p className="text-[11px] text-slate-400">Resilience &amp; Trust Engine</p>
        </div>
      </div>

      <nav className="flex gap-1 overflow-x-auto p-3 lg:flex-1 lg:flex-col lg:overflow-visible">
        <div className="hidden px-2.5 pb-1.5 pt-1 font-mono text-[10px] uppercase tracking-[0.16em] text-slate-500 lg:block">
          Command Center
        </div>
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeSection === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelectSection(item.id)}
              className={`group flex shrink-0 items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-all lg:w-full ${
                isActive
                  ? "border-nexus-cyan/40 bg-nexus-cyan/10 text-slate-50 shadow-cyan-subtle"
                  : "border-transparent text-slate-400 hover:border-obsidian-700 hover:bg-obsidian-850 hover:text-slate-200"
              }`}
            >
              <Icon
                className={`h-4 w-4 shrink-0 ${
                  isActive ? "text-nexus-cyan" : "text-slate-500 group-hover:text-slate-300"
                }`}
              />
              <div className="min-w-0">
                <div className="text-sm font-medium leading-none">{item.label}</div>
                <div className="mt-1 hidden text-[11px] text-slate-500 lg:block">
                  {item.caption}
                </div>
              </div>
            </button>
          );
        })}
      </nav>

      <div className="hidden border-t border-obsidian-700/70 p-4 lg:block">
        <div className="rounded-lg border border-obsidian-700/70 bg-obsidian-950/80 p-3">
          <div className="flex items-center justify-between text-[11px]">
            <span className="font-mono uppercase tracking-wider text-slate-400">Safety Gate</span>
            <span className="inline-flex items-center gap-1 font-mono text-nexus-emerald">
              <Activity className="h-3 w-3" />
              ENFORCED
            </span>
          </div>
          <div className="mt-2 flex items-center justify-between text-[11px]">
            <span className="text-slate-500">Inference Mode</span>
            <span className="font-mono uppercase text-nexus-cyan">{aiMode}</span>
          </div>
          <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
            Local simulation only. All remediation actions are allowlisted and audited.
          </p>
        </div>
      </div>
    </aside>
  );
}

