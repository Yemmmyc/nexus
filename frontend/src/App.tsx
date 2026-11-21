import { useCallback, useEffect, useState } from "react";
import { fetchHealth } from "./api/client";
import { Sidebar } from "./components/layout/Sidebar";
import { TopBar } from "./components/layout/TopBar";
import type { HealthResponse, NavSection } from "./types/health";
import { AuditView } from "./views/AuditView";
import { DashboardView } from "./views/DashboardView";
import { IncidentsView } from "./views/IncidentsView";
import { TopologyView } from "./views/TopologyView";

export function App() {
  const [activeSection, setActiveSection] = useState<NavSection>("overview");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);

  const loadHealth = useCallback(async () => {
    setIsCheckingHealth(true);
    try {
      const data = await fetchHealth();
      setHealth(data);
      setHealthError(null);
    } catch (err) {
      setHealthError(err instanceof Error ? err.message : "Backend unreachable");
    } finally {
      setIsCheckingHealth(false);
    }
  }, []);

  useEffect(() => {
    void loadHealth();
  }, [loadHealth]);

  return (
    <div className="flex min-h-screen flex-col bg-obsidian-950 text-slate-100 lg:flex-row">
      <Sidebar
        activeSection={activeSection}
        onSelectSection={setActiveSection}
        aiMode={health?.ai_mode ?? "deterministic"}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          activeSection={activeSection}
          health={health}
          healthError={healthError}
          isCheckingHealth={isCheckingHealth}
          onRefreshHealth={() => void loadHealth()}
        />

        <main className="flex-1 p-6">
          {activeSection === "overview" && <DashboardView health={health} />}
          {activeSection === "topology" && <TopologyView />}
          {activeSection === "incidents" && <IncidentsView />}
          {activeSection === "audit" && <AuditView />}
        </main>
      </div>
    </div>
  );
}

export default App;

