import { useEffect, useState } from "react";

import { fetchDashboard } from "./api";
import Dashboard from "./components/Dashboard";
import type { DashboardData } from "./types";

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

  return <Dashboard data={dashboard} isLoading={isLoading} />;
}
