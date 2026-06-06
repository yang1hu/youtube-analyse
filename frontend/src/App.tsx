import { useEffect, useState } from "react";

import { fetchDashboard } from "./api";
import Dashboard from "./components/Dashboard";
import IdeaLab from "./components/IdeaLab";
import Settings from "./components/Settings";
import VideoReport from "./components/VideoReport";
import type { DashboardData } from "./types";

type View = "dashboard" | "video-report" | "idea-lab" | "settings";

const emptyDashboard: DashboardData = {
  channels: [],
  recent_videos: [],
  idea_cards: [],
  jobs: [],
  comment_collector_status: "unknown"
};

export default function App() {
  const [dashboard, setDashboard] = useState<DashboardData>(emptyDashboard);
  const [isLoading, setIsLoading] = useState(true);
  const [activeView, setActiveView] = useState<View>("dashboard");

  useEffect(() => {
    let isMounted = true;

    fetchDashboard()
      .then(data => {
        if (isMounted) {
          setDashboard(data);
        }
      })
      .catch(() => {
        if (isMounted) {
          setDashboard(emptyDashboard);
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const navItems: { label: string; view: View }[] = [
    { label: "Dashboard", view: "dashboard" },
    { label: "Video Report", view: "video-report" },
    { label: "Idea Lab", view: "idea-lab" },
    { label: "Settings", view: "settings" }
  ];

  return (
    <>
      <header className="workspace-nav" aria-label="Creator workspace navigation">
        <div className="workspace-nav-inner">
          <p className="workspace-brand">Creator Agent</p>
          <nav className="workspace-tabs" aria-label="Primary views">
            {navItems.map(item => (
              <button
                aria-current={activeView === item.view ? "page" : undefined}
                className="workspace-tab"
                key={item.view}
                onClick={() => setActiveView(item.view)}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {activeView === "dashboard" && <Dashboard data={dashboard} isLoading={isLoading} />}
      {activeView === "video-report" && <VideoReport />}
      {activeView === "idea-lab" && <IdeaLab />}
      {activeView === "settings" && <Settings />}
    </>
  );
}
