import type { DashboardData } from "./types";

const emptyDashboard: DashboardData = {
  channels: [],
  recent_videos: [],
  idea_cards: [],
  jobs: [],
  comment_collector_status: "unknown"
};

export async function fetchDashboard(): Promise<DashboardData> {
  const response = await fetch("/api/dashboard");

  if (!response.ok) {
    return emptyDashboard;
  }

  const data = (await response.json()) as Partial<DashboardData>;

  return {
    channels: data.channels ?? [],
    recent_videos: data.recent_videos ?? [],
    idea_cards: data.idea_cards ?? [],
    jobs: data.jobs ?? [],
    comment_collector_status: data.comment_collector_status ?? "unknown"
  };
}
