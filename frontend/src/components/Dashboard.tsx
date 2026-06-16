import {
  BarChart3,
  Clapperboard,
  DownloadCloud,
  Lightbulb,
  MessageSquareText,
  PlayCircle,
  RadioTower,
  type LucideIcon
} from "lucide-react";

import type { DashboardData, Language, RecentVideo } from "../types";

interface DashboardProps {
  data: DashboardData;
  isLoading: boolean;
  language: Language;
  onAnalyzeVideo: (videoUrl: string) => void;
  onAnalyzeSample: (video: RecentVideo) => void;
  onSyncChannel: () => void;
  isWorking: boolean;
  message?: string;
  messageTone?: "saved" | "error";
}

interface Metric {
  label: string;
  value: string;
  detail: string;
  tone: "green" | "neutral" | "amber" | "slate";
  icon: LucideIcon;
}

const copy = {
  zh: {
    activeJobs: "\u8fdb\u884c\u4e2d\u7684\u4efb\u52a1",
    analyze: "\u5206\u6790",
    analyzeVideo: "\u5206\u6790\u6700\u65b0\u89c6\u9891",
    channels: "\u9891\u9053",
    comments: "\u8bc4\u8bba",
    commentsDetail: "\u91c7\u96c6\u5668\u72b6\u6001",
    configuredChannel: "\u5df2\u914d\u7f6e\u9891\u9053",
    configuredChannels: "\u5df2\u914d\u7f6e\u9891\u9053列表",
    creatorIntelligence: "\u521b\u4f5c\u8005\u60c5\u62a5",
    growthPrompts: "\u589e\u957f\u9009\u9898",
    heroSummary: "\u76d1\u63a7\u9891\u9053\u3001\u540c\u6b65\u6700\u65b0\u89c6\u9891\uff0c\u5e76\u5c06\u89c6\u9891\u8f6c\u6210\u62a5\u544a\u548c\u9009\u9898\u5361\u3002",
    ideaCards: "\u9009\u9898\u5361",
    noChannel: "\u8bf7\u5148\u5728\u8bbe\u7f6e\u4e2d\u4fdd\u5b58\u9891\u9053\u5730\u5740\u3002",
    noVideos: "\u8fd8\u6ca1\u6709\u89c6\u9891\uff0c\u5148\u540c\u6b65\u9891\u9053\u3002",
    pipeline: "\u6d41\u6c34\u7ebf",
    recentVideos: "\u6700\u8fd1\u89c6\u9891",
    sample: "\u7cbe\u54c1\u6837\u672c",
    syncError: "\u540c\u6b65\u9519\u8bef",
    syncStatus: "\u540c\u6b65\u72b6\u6001",
    syncChannel: "\u540c\u6b65\u9891\u9053",
    title: "YouTube \u521b\u4f5c\u8005\u589e\u957f\u667a\u80fd\u4f53",
    trackedSources: "\u76d1\u63a7\u6765\u6e90",
    videosReady: "\u53ef\u5206\u6790"
  },
  en: {
    activeJobs: "Active jobs",
    analyze: "Analyze",
    analyzeVideo: "Analyze Latest Video",
    channels: "Channels",
    comments: "Comments",
    commentsDetail: "Collector status",
    configuredChannel: "Configured channel",
    configuredChannels: "Configured channels",
    creatorIntelligence: "Creator intelligence",
    growthPrompts: "Growth prompts",
    heroSummary: "Monitor a channel, sync recent uploads, and turn videos into reports and idea cards.",
    ideaCards: "Idea Cards",
    noChannel: "Save a channel URL in Settings first.",
    noVideos: "No videos yet. Sync the channel first.",
    pipeline: "Pipeline",
    recentVideos: "Recent Videos",
    sample: "Sample",
    syncError: "Sync error",
    syncStatus: "Sync status",
    syncChannel: "Sync Channel",
    title: "YouTube Creator Growth Agent",
    trackedSources: "Tracked sources",
    videosReady: "Ready for analysis"
  }
} satisfies Record<Language, Record<string, string>>;

function formatStatus(status: string) {
  return status.replace(/_/g, " ").replace(/\b\w/g, letter => letter.toUpperCase());
}

function channelTone(index: number) {
  return ["green", "amber", "slate", "neutral"][index % 4];
}

function channelVideos(data: DashboardData, channelUrl?: string, channelTitle?: string) {
  if (!channelUrl && !channelTitle) {
    return [];
  }
  return data.recent_videos.filter(video => {
    const matchesUrl = channelUrl && video.channel_url === channelUrl;
    const matchesTitle = channelTitle && video.channel_title === channelTitle;
    return Boolean(matchesUrl || matchesTitle);
  });
}

export default function Dashboard({
  data,
  isLoading,
  language,
  onAnalyzeVideo,
  onAnalyzeSample,
  onSyncChannel,
  isWorking,
  message = "",
  messageTone = "saved"
}: DashboardProps) {
  const t = copy[language];
  const activeJobs = data.jobs.filter(job => job.status && job.status !== "complete").length;
  const firstVideo = data.recent_videos[0];
  const channels = data.channels;
  const groupedChannels = channels.length
    ? channels
    : [
        {
          id: "all",
          title: t.noChannel,
          url: "",
          collection_status: "configured",
          collection_error: ""
        }
      ];

  const metrics: Metric[] = [
    {
      label: t.channels,
      value: String(data.channels.length),
      detail: t.trackedSources,
      tone: "green",
      icon: RadioTower
    },
    {
      label: t.recentVideos,
      value: String(data.recent_videos.length),
      detail: t.videosReady,
      tone: "neutral",
      icon: Clapperboard
    },
    {
      label: t.ideaCards,
      value: String(data.idea_cards.length),
      detail: t.growthPrompts,
      tone: "amber",
      icon: Lightbulb
    },
    {
      label: t.comments,
      value: formatStatus(data.comment_collector_status),
      detail: t.commentsDetail,
      tone: "slate",
      icon: MessageSquareText
    }
  ];

  const analyze = (video: RecentVideo) => {
    if (video.url) {
      onAnalyzeVideo(video.url);
    }
  };

  const analyzeSample = (video: RecentVideo) => {
    if (video.url) {
      onAnalyzeSample(video);
    }
  };

  return (
    <main className="app-shell">
      <section className="dashboard-hero" aria-labelledby="page-title">
        <div className="hero-copy">
          <p className="eyebrow">{t.creatorIntelligence}</p>
          <h1 id="page-title">{t.title}</h1>
          <p className="hero-summary">{t.heroSummary}</p>
        </div>
        <div className="hero-actions">
          <button className="primary-action" disabled={isWorking} onClick={onSyncChannel} type="button">
            <DownloadCloud aria-hidden="true" size={20} />
            <span>{t.syncChannel}</span>
          </button>
          <button
            className="secondary-action"
            disabled={isWorking || !firstVideo?.url}
            onClick={() => firstVideo && analyze(firstVideo)}
            type="button"
          >
            <PlayCircle aria-hidden="true" size={20} />
            <span>{t.analyzeVideo}</span>
          </button>
        </div>
        {message && <p className={`form-message form-message-${messageTone}`}>{message}</p>}
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
              <p className="eyebrow">{t.configuredChannels}</p>
              <h2>{channels.length ? String(channels.length) : t.noChannel}</h2>
            </div>
            <RadioTower aria-hidden="true" size={22} />
          </div>
          {channels.length ? (
            <div className="channel-summary-list">
              {channels.map(channel => (
                <div className="channel-summary-item" key={channel.url ?? channel.id}>
                  <div>
                    <strong>{channel.title ?? t.configuredChannel}</strong>
                    {channel.url && <p className="panel-note">{channel.url}</p>}
                  </div>
                  <div>
                    {channel.collection_status && (
                      <p className={`sync-status sync-status-${channel.collection_status}`}>
                        {t.syncStatus}: {formatStatus(channel.collection_status)}
                      </p>
                    )}
                    {channel.collection_error && <p className="sync-error">{t.syncError}: {channel.collection_error}</p>}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="panel-note">{t.noChannel}</p>
          )}
        </article>

        <article className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">{t.pipeline}</p>
              <h2>{t.activeJobs}</h2>
            </div>
            <BarChart3 aria-hidden="true" size={22} />
          </div>
          <div className="queue-state">
            <p className="queue-number">{isLoading ? "..." : activeJobs}</p>
            <p>{t.activeJobs}</p>
          </div>
        </article>
      </section>

      <section className="channel-gallery" aria-label={t.recentVideos}>
        {groupedChannels.map((channel, index) => {
          const tone = channelTone(index);
          const videos = channelVideos(data, channel.url, channel.title);
          return (
            <article className={`channel-panel channel-panel-${tone}`} key={channel.url ?? channel.id ?? channel.title ?? index}>
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">{channel.title ?? t.configuredChannel}</p>
                  <h2>{videos.length ? `${videos.length} ${t.videosReady}` : t.noVideos}</h2>
                </div>
                <Clapperboard aria-hidden="true" size={22} />
              </div>
              {channel.url && <p className="panel-note">{channel.url}</p>}
              {channel.collection_status && (
                <p className={`sync-status sync-status-${channel.collection_status}`}>
                  {t.syncStatus}: {formatStatus(channel.collection_status)}
                </p>
              )}
              {channel.collection_error && <p className="sync-error">{t.syncError}: {channel.collection_error}</p>}
              {videos.length ? (
                <div className="video-list">
                  {videos.map(video => (
                    <div className="video-row" key={video.id ?? video.url ?? video.title}>
                      <div>
                        <p className="video-title">{video.title}</p>
                        <p className="video-meta">
                          {video.published_at || "-"} / {video.view_count ?? 0} views /{" "}
                          {formatStatus(video.analysis_status ?? "pending")}
                        </p>
                      </div>
                      <div className="video-row-actions">
                        <button
                          className="secondary-action compact-action"
                          disabled={isWorking || !video.url}
                          onClick={() => analyze(video)}
                          type="button"
                        >
                          {t.analyze}
                        </button>
                        <button
                          className="secondary-action compact-action"
                          disabled={isWorking || !video.url}
                          onClick={() => analyzeSample(video)}
                          type="button"
                        >
                          {t.sample}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state">
                  <p>{t.noVideos}</p>
                </div>
              )}
            </article>
          );
        })}
      </section>
    </main>
  );
}
