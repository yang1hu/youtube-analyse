import {
  BarChart3,
  CheckCircle2,
  Clapperboard,
  Lightbulb,
  MessageSquareText,
  PlayCircle,
  RadioTower,
  type LucideIcon
} from "lucide-react";

import type { DashboardData } from "../types";

interface DashboardProps {
  data: DashboardData;
  isLoading: boolean;
}

interface Metric {
  label: string;
  value: string;
  detail: string;
  tone: "green" | "neutral" | "amber" | "slate";
  icon: LucideIcon;
}

function formatStatus(status: string) {
  return status
    .replace(/_/g, " ")
    .replace(/\b\w/g, letter => letter.toUpperCase());
}

export default function Dashboard({ data, isLoading }: DashboardProps) {
  const metrics: Metric[] = [
    {
      label: "Channels",
      value: String(data.channels.length),
      detail: data.channels.length === 1 ? "Tracked source" : "Tracked sources",
      tone: "green",
      icon: RadioTower
    },
    {
      label: "Recent Videos",
      value: String(data.recent_videos.length),
      detail: "Ready for analysis",
      tone: "neutral",
      icon: Clapperboard
    },
    {
      label: "Idea Cards",
      value: String(data.idea_cards.length),
      detail: "Growth prompts",
      tone: "amber",
      icon: Lightbulb
    },
    {
      label: "Comments",
      value: formatStatus(data.comment_collector_status),
      detail: "Collector status",
      tone: "slate",
      icon: MessageSquareText
    }
  ];

  const latestVideo = data.recent_videos[0];
  const activeJobs = data.jobs.filter(job => job.status && job.status !== "complete").length;

  return (
    <main className="app-shell">
      <section className="dashboard-hero" aria-labelledby="page-title">
        <div className="hero-copy">
          <p className="eyebrow">Creator intelligence</p>
          <h1 id="page-title">YouTube Creator Growth Agent</h1>
          <p className="hero-summary">
            Monitor channels, collect ideas, and queue focused video analysis from one calm
            workspace.
          </p>
        </div>
        <button className="primary-action" type="button">
          <PlayCircle aria-hidden="true" size={20} />
          <span>Analyze Video</span>
        </button>
      </section>

      <section className="metrics-grid" aria-label="Dashboard metrics">
        {metrics.map(metric => {
          const Icon = metric.icon;

          return (
            <article className={`metric-card metric-card-${metric.tone}`} key={metric.label}>
              <div className="metric-icon">
                <Icon aria-hidden="true" size={20} />
              </div>
              <div>
                <p className="metric-label">{metric.label}</p>
                <p className="metric-value">{isLoading ? "..." : metric.value}</p>
                <p className="metric-detail">{metric.detail}</p>
              </div>
            </article>
          );
        })}
      </section>

      <section className="content-grid">
        <article className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Pipeline</p>
              <h2>Analysis Queue</h2>
            </div>
            <BarChart3 aria-hidden="true" size={22} />
          </div>
          <div className="queue-state">
            <p className="queue-number">{isLoading ? "..." : activeJobs}</p>
            <p>Active jobs</p>
          </div>
          <p className="panel-note">
            New video analysis requests will appear here as the backend pipeline comes online.
          </p>
        </article>

        <article className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Latest signal</p>
              <h2>Recent Video</h2>
            </div>
            <CheckCircle2 aria-hidden="true" size={22} />
          </div>
          {latestVideo ? (
            <div className="video-card">
              <p className="video-title">{latestVideo.title ?? "Untitled video"}</p>
              <p className="video-meta">{latestVideo.channel_title ?? "Unknown channel"}</p>
            </div>
          ) : (
            <div className="empty-state">
              <p>No recent videos yet.</p>
              <span>Connect channel history to populate this view.</span>
            </div>
          )}
        </article>
      </section>
    </main>
  );
}
