import type { ReactNode } from "react";

interface PanelProps {
  title: string;
  subtitle?: string;
  rightSlot?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Panel({ title, subtitle, rightSlot, children, className = "" }: PanelProps) {
  return (
    <section
      className={`rounded-xl border border-obsidian-700/80 bg-obsidian-900/90 shadow-panel backdrop-blur-sm ${className}`}
    >
      <header className="flex items-center justify-between gap-4 border-b border-obsidian-700/70 px-5 py-3.5">
        <div>
          <h2 className="text-sm font-semibold tracking-wide text-slate-100">{title}</h2>
          {subtitle ? <p className="mt-0.5 text-xs text-slate-400">{subtitle}</p> : null}
        </div>
        {rightSlot ? <div className="shrink-0">{rightSlot}</div> : null}
      </header>
      <div className="p-5">{children}</div>
    </section>
  );
}

