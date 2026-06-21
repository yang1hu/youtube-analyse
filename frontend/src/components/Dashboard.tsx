import {
  BarChart3,
  Clapperboard,
  DownloadCloud,
  FileText,
  ListChecks,
  Lightbulb,
  PlayCircle,
  RadioTower,
  ShieldCheck,
  type LucideIcon
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { DashboardData, Language, RecentVideo, TopicCandidate } from "../types";

interface DashboardProps {
  data: DashboardData;
  isLoading: boolean;
  language: Language;
  onAnalyzeVideo: (videoUrl: string) => void;
  onBatchAnalyzeVideos: (videoUrls?: string[]) => void;
  onOpenView: (view: "tasks" | "video-report" | "imitation-factory" | "project-library" | "settings") => void;
  onAnalyzeSample: (video: RecentVideo) => void;
  onSyncChannel: () => void;
  onLoadDemoWorkspace: () => void;
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

type CandidateSort = "score" | "views" | "freshness";

const freshnessRank: Record<string, number> = { fresh: 3, recent: 2, older: 1 };

function uniqueOptions(values: string[]) {
  return Array.from(new Set(values.filter(Boolean))).sort((left, right) => left.localeCompare(right));
}

function candidateMatches(candidate: TopicCandidate, filters: { channel: string; topic: string; freshness: string; views: string }) {
  if (filters.channel && candidate.channel_title !== filters.channel) return false;
  if (filters.topic && candidate.topic_group !== filters.topic) return false;
  if (filters.freshness && candidate.freshness_bucket !== filters.freshness) return false;
  if (filters.views && candidate.view_bucket !== filters.views) return false;
  return true;
}

function sortedCandidates(candidates: TopicCandidate[], sort: CandidateSort) {
  return [...candidates].sort((left, right) => {
    if (sort === "views") return Number(right.view_count || 0) - Number(left.view_count || 0);
    if (sort === "freshness") {
      return (
        (freshnessRank[right.freshness_bucket || ""] || 0) - (freshnessRank[left.freshness_bucket || ""] || 0) ||
        Number(right.score || 0) - Number(left.score || 0)
      );
    }
    return Number(right.score || 0) - Number(left.score || 0) || Number(right.view_count || 0) - Number(left.view_count || 0);
  });
}

const copy = {
  zh: {
    activeJobs: "\u8fdb\u884c\u4e2d\u7684\u4efb\u52a1",
    analyze: "\u5206\u6790",
    batchAnalyze: "批量分析待处理视频",
    batchSelected: "分析选中",
    loadDemo: "载入演示工作区",
    analyzeVideo: "\u5206\u6790\u6700\u65b0\u89c6\u9891",
    channels: "\u9891\u9053",
    configuredChannel: "\u5df2\u914d\u7f6e\u9891\u9053",
    configuredChannels: "\u5df2\u914d\u7f6e\u9891\u9053列表",
    creatorIntelligence: "\u521b\u4f5c\u8005\u60c5\u62a5",
    growthPrompts: "\u589e\u957f\u9009\u9898",
    heroSummary: "\u76d1\u63a7\u9891\u9053\u3001\u540c\u6b65\u6700\u65b0\u89c6\u9891\uff0c\u5e76\u5c06\u89c6\u9891\u8f6c\u6210\u62a5\u544a\u548c\u9009\u9898\u5361\u3002",
    ideaCards: "\u9009\u9898\u5361",
    imitationProjects: "创作项目",
    nextAction: "下一步",
    stepAction: "执行",
    stepDone: "完成",
    stepPending: "待处理",
    qualityMetrics: "质量指标",
    qualityFailureReasons: "质检失败原因",
    qualityFailureIntro: "优先处理出现次数最多的失败项，能最快提高门禁通过率。",
    affectedDrafts: "影响草稿",
    weeklyProduction: "本周生产",
    weeklyWindow: "最近 7 天",
    weeklyAnalyzed: "本周分析",
    weeklyProjects: "本周项目",
    weeklyDrafts: "本周草稿",
    weeklyPublishable: "本周可发布",
    creationFunnel: "创作转化漏斗",
    conversionRate: "转化率",
    bottleneck: "瓶颈",
    noBottleneck: "暂无瓶颈数据",
    gatePassRate: "门禁通过率",
    avgOverlap: "平均重合",
    avgRewrite: "平均改写",
    highRiskRate: "高风险占比",
    totalDrafts: "草稿总数",
    candidates: "选题候选",
    candidateIntro: "按播放、近期和故事关键词排序，优先分析最可能产出爆款结构的视频。",
    candidateChannel: "频道",
    candidateFreshness: "新鲜度",
    candidateSort: "候选排序",
    candidateTopic: "题材",
    candidateViews: "播放表现",
    candidateMatched: "命中候选",
    candidateSelected: "已选",
    selectFiltered: "全选当前结果",
    clearSelected: "清空选择",
    viralPotential: "爆款潜力",
    storyFit: "故事适配",
    structureReuse: "结构价值",
    candidateRisks: "风险提示",
    candidateRecommendation: "推荐判断",
    candidateNextAction: "处理动作",
    all: "全部",
    sortScore: "综合分",
    sortViews: "播放量",
    sortFreshness: "新鲜优先",
    noChannel: "\u8bf7\u5148\u5728\u8bbe\u7f6e\u4e2d\u4fdd\u5b58\u9891\u9053\u5730\u5740\u3002",
    noVideos: "\u8fd8\u6ca1\u6709\u89c6\u9891\uff0c\u5148\u540c\u6b65\u9891\u9053\u3002",
    pipeline: "\u6d41\u6c34\u7ebf",
    publishableDrafts: "可发布稿件",
    recentVideos: "\u6700\u8fd1\u89c6\u9891",
    reports: "分析报告",
    reportsReady: "可进入故事工坊",
    sample: "\u7cbe\u54c1\u6837\u672c",
    stepAnalyze: "分析视频",
    stepClean: "清洗文案",
    stepExport: "导出发布",
    stepImitation: "创作转化",
    stepQa: "质检改写",
    stepSettings: "配置频道",
    stepStory: "拆解结构",
    stepSync: "同步视频",
    stepSettingsDetail: "保存频道地址后才能同步素材。",
    stepSyncDetail: "同步频道里的最新视频，形成候选素材池。",
    stepAnalyzeDetail: "把候选视频转成报告和字幕证据。",
    stepCleanDetail: "校对字幕并保存可分析的故事原文。",
    stepStoryDetail: "提取钩子、爽点、反转和不可复用内容。",
    stepImitationDetail: "生成 InkOS 创作包或原创草稿。",
    stepQaDetail: "检测风险并改写到可发布状态。",
    stepExportDetail: "导出可发布文案或沉淀结构模板。",
    funnelSyncedVideos: "同步视频",
    funnelAnalyzedReports: "分析报告",
    funnelCreationProjects: "创作项目",
    funnelGeneratedDrafts: "生成草稿",
    funnelPublishableDrafts: "可发布稿件",
    syncError: "\u540c\u6b65\u9519\u8bef",
    syncStatus: "\u540c\u6b65\u72b6\u6001",
    syncChannel: "\u540c\u6b65\u9891\u9053",
    title: "YouTube \u521b\u4f5c\u8005\u589e\u957f\u667a\u80fd\u4f53",
    trackedSources: "\u76d1\u63a7\u6765\u6e90",
    videosReady: "\u53ef\u5206\u6790",
    waitingQa: "待检查/待修改"
  },
  en: {
    activeJobs: "Active jobs",
    analyze: "Analyze",
    batchAnalyze: "Batch Analyze Pending",
    batchSelected: "Analyze Selected",
    loadDemo: "Load Demo Workspace",
    analyzeVideo: "Analyze Latest Video",
    channels: "Channels",
    configuredChannel: "Configured channel",
    configuredChannels: "Configured channels",
    creatorIntelligence: "Creator intelligence",
    growthPrompts: "Growth prompts",
    heroSummary: "Monitor a channel, sync recent uploads, and turn videos into reports and idea cards.",
    ideaCards: "Idea Cards",
    imitationProjects: "Creation Projects",
    nextAction: "Next Action",
    stepAction: "Open",
    stepDone: "Done",
    stepPending: "Pending",
    qualityMetrics: "Quality Metrics",
    qualityFailureReasons: "Gate Failure Reasons",
    qualityFailureIntro: "Start with the most common failed checks to lift the pass rate fastest.",
    affectedDrafts: "Affected drafts",
    weeklyProduction: "Weekly Production",
    weeklyWindow: "Last 7 days",
    weeklyAnalyzed: "Analyzed",
    weeklyProjects: "Projects",
    weeklyDrafts: "Drafts",
    weeklyPublishable: "Publishable",
    creationFunnel: "Creation Funnel",
    conversionRate: "Conversion",
    bottleneck: "Bottleneck",
    noBottleneck: "No bottleneck data",
    gatePassRate: "Gate Pass Rate",
    avgOverlap: "Avg Overlap",
    avgRewrite: "Avg Rewrites",
    highRiskRate: "High Risk Rate",
    totalDrafts: "Total Drafts",
    candidates: "Topic Candidates",
    candidateIntro: "Ranked by views, freshness, and story keywords so the strongest videos enter analysis first.",
    candidateChannel: "Channel",
    candidateFreshness: "Freshness",
    candidateSort: "Candidate Sort",
    candidateTopic: "Topic",
    candidateViews: "Views",
    candidateMatched: "Matched",
    candidateSelected: "Selected",
    selectFiltered: "Select Filtered",
    clearSelected: "Clear Selection",
    viralPotential: "Viral Potential",
    storyFit: "Story Fit",
    structureReuse: "Structure Value",
    candidateRisks: "Risk Notes",
    candidateRecommendation: "Recommendation",
    candidateNextAction: "Next Action",
    all: "All",
    sortScore: "Score",
    sortViews: "Views",
    sortFreshness: "Freshness",
    noChannel: "Save a channel URL in Settings first.",
    noVideos: "No videos yet. Sync the channel first.",
    pipeline: "Pipeline",
    publishableDrafts: "Publishable Drafts",
    recentVideos: "Recent Videos",
    reports: "Reports",
    reportsReady: "Ready for story workbench",
    sample: "Sample",
    stepAnalyze: "Analyze Videos",
    stepClean: "Clean Script",
    stepExport: "Export",
    stepImitation: "Story Remix Lab",
    stepQa: "QA & Rewrite",
    stepSettings: "Configure Channels",
    stepStory: "Story Structure",
    stepSync: "Sync Videos",
    stepSettingsDetail: "Save channel URLs before syncing source material.",
    stepSyncDetail: "Sync recent channel uploads into the candidate pool.",
    stepAnalyzeDetail: "Turn candidate videos into reports and transcript evidence.",
    stepCleanDetail: "Review captions and save a clean story script.",
    stepStoryDetail: "Extract hooks, payoffs, reversals, and non-reusable details.",
    stepImitationDetail: "Create an InkOS brief or original draft.",
    stepQaDetail: "Check risk and rewrite until the draft can publish.",
    stepExportDetail: "Export publishable copy or save a reusable structure.",
    funnelSyncedVideos: "Synced Videos",
    funnelAnalyzedReports: "Analyzed Reports",
    funnelCreationProjects: "Creation Projects",
    funnelGeneratedDrafts: "Generated Drafts",
    funnelPublishableDrafts: "Publishable Drafts",
    syncError: "Sync error",
    syncStatus: "Sync status",
    syncChannel: "Sync Channel",
    title: "YouTube Creator Growth Agent",
    trackedSources: "Tracked sources",
    videosReady: "Ready for analysis",
    waitingQa: "Needs QA / revision"
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
  onBatchAnalyzeVideos,
  onOpenView,
  onAnalyzeSample,
  onSyncChannel,
  onLoadDemoWorkspace,
  isWorking,
  message = "",
  messageTone = "saved"
}: DashboardProps) {
  const t = copy[language];
  const [selectedCandidateUrls, setSelectedCandidateUrls] = useState<string[]>([]);
  const [candidateChannelFilter, setCandidateChannelFilter] = useState("");
  const [candidateTopicFilter, setCandidateTopicFilter] = useState("");
  const [candidateFreshnessFilter, setCandidateFreshnessFilter] = useState("");
  const [candidateViewFilter, setCandidateViewFilter] = useState("");
  const [candidateSort, setCandidateSort] = useState<CandidateSort>("score");
  const activeJobs = data.jobs.filter(job => job.status && job.status !== "complete").length;
  const firstVideo = data.recent_videos[0];
  const isEmptyWorkspace =
    !isLoading &&
    data.channels.length === 0 &&
    data.recent_videos.length === 0 &&
    (data.reports_count ?? 0) === 0 &&
    (data.imitation_projects_count ?? 0) === 0;
  const channels = data.channels;
  const pipeline = data.creation_pipeline;
  const qualityMetrics = data.creation_quality_metrics;
  const creationFunnel = data.creation_funnel;
  const weeklyProduction = data.weekly_production_metrics;
  const candidateFilters = {
    channel: candidateChannelFilter,
    freshness: candidateFreshnessFilter,
    topic: candidateTopicFilter,
    views: candidateViewFilter
  };
  const filteredCandidates = useMemo(
    () => sortedCandidates((data.topic_candidates ?? []).filter(candidate => candidateMatches(candidate, candidateFilters)), candidateSort),
    [candidateChannelFilter, candidateFreshnessFilter, candidateSort, candidateTopicFilter, candidateViewFilter, data.topic_candidates]
  );
  const candidateUrls = useMemo(() => filteredCandidates.map(candidate => candidate.url || "").filter(Boolean), [filteredCandidates]);
  const candidateChannelOptions = useMemo(
    () => uniqueOptions((data.topic_candidates ?? []).map(candidate => candidate.channel_title || "")),
    [data.topic_candidates]
  );
  const candidateTopicOptions = useMemo(
    () => uniqueOptions((data.topic_candidates ?? []).map(candidate => candidate.topic_group || "")),
    [data.topic_candidates]
  );
  const candidateFreshnessOptions = useMemo(
    () => uniqueOptions((data.topic_candidates ?? []).map(candidate => candidate.freshness_bucket || "")),
    [data.topic_candidates]
  );
  const candidateViewOptions = useMemo(
    () => uniqueOptions((data.topic_candidates ?? []).map(candidate => candidate.view_bucket || "")),
    [data.topic_candidates]
  );
  useEffect(() => {
    setSelectedCandidateUrls(current => current.filter(url => candidateUrls.includes(url)));
  }, [candidateUrls]);
  const selectFilteredCandidates = () => {
    setSelectedCandidateUrls(candidateUrls);
  };
  const clearSelectedCandidates = () => {
    setSelectedCandidateUrls([]);
  };
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
      label: t.reports,
      value: String(data.reports_count ?? 0),
      detail: t.reportsReady,
      tone: "green",
      icon: FileText
    },
    {
      label: t.imitationProjects,
      value: String(data.imitation_projects_count ?? 0),
      detail: t.growthPrompts,
      tone: "neutral",
      icon: Lightbulb
    },
    {
      label: t.activeJobs,
      value: String(data.pending_drafts_count ?? 0),
      detail: t.waitingQa,
      tone: "amber",
      icon: BarChart3
    },
    {
      label: t.publishableDrafts,
      value: String(data.publishable_drafts_count ?? 0),
      detail: t.pipeline,
      tone: "slate",
      icon: ShieldCheck
    }
  ];
  const qualityMetricCards = [
    {
      label: t.gatePassRate,
      value: `${Number(qualityMetrics?.quality_gate_pass_rate || 0).toFixed(1)}%`,
      detail: t.qualityMetrics
    },
    {
      label: t.avgOverlap,
      value: `${Number(qualityMetrics?.average_text_overlap_percent || 0).toFixed(1)}%`,
      detail: t.totalDrafts + ` ${qualityMetrics?.draft_count ?? 0}`
    },
    {
      label: t.avgRewrite,
      value: Number(qualityMetrics?.average_rewrite_count || 0).toFixed(2),
      detail: language === "zh" ? "每个项目" : "per project"
    },
    {
      label: t.highRiskRate,
      value: `${Number(qualityMetrics?.high_risk_rate || 0).toFixed(1)}%`,
      detail: t.waitingQa
    }
  ];
  const failedGateReasons = qualityMetrics?.failed_gate_reasons ?? [];
  const weeklyProductionCards = [
    {
      label: t.weeklyAnalyzed,
      value: String(weeklyProduction?.analyzed_report_count ?? 0),
      detail: t.reports
    },
    {
      label: t.weeklyProjects,
      value: String(weeklyProduction?.created_project_count ?? 0),
      detail: t.imitationProjects
    },
    {
      label: t.weeklyDrafts,
      value: String(weeklyProduction?.generated_draft_count ?? 0),
      detail: t.totalDrafts
    },
    {
      label: t.weeklyPublishable,
      value: String(weeklyProduction?.publishable_draft_count ?? 0),
      detail: t.publishableDrafts
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

  const toggleCandidate = (videoUrl: string) => {
    setSelectedCandidateUrls(current =>
      current.includes(videoUrl) ? current.filter(url => url !== videoUrl) : [...current, videoUrl]
    );
  };

  const stepLabels: Record<string, string> = {
    settings: t.stepSettings,
    sync: t.stepSync,
    analyze: t.stepAnalyze,
    clean_script: t.stepClean,
    story_workbench: t.stepStory,
    story_structure: t.stepStory,
    imitation_factory: t.stepImitation,
    quality_check: t.stepQa,
    export_publish: t.stepExport,
    project_library: language === "zh" ? "项目库" : "Project Library"
  };
  const stepDetails: Record<string, string> = {
    settings: t.stepSettingsDetail,
    sync: t.stepSyncDetail,
    analyze: t.stepAnalyzeDetail,
    clean_script: t.stepCleanDetail,
    story_workbench: t.stepStoryDetail,
    story_structure: t.stepStoryDetail,
    imitation_factory: t.stepImitationDetail,
    quality_check: t.stepQaDetail,
    export_publish: t.stepExportDetail,
    project_library: t.stepExportDetail
  };
  const funnelLabels: Record<string, string> = {
    synced_videos: t.funnelSyncedVideos,
    analyzed_reports: t.funnelAnalyzedReports,
    creation_projects: t.funnelCreationProjects,
    generated_drafts: t.funnelGeneratedDrafts,
    publishable_drafts: t.funnelPublishableDrafts
  };
  const bottleneckLabel = creationFunnel?.bottleneck
    ? `${funnelLabels[creationFunnel.bottleneck.from] ?? creationFunnel.bottleneck.from} -> ${
        funnelLabels[creationFunnel.bottleneck.to] ?? creationFunnel.bottleneck.to
      }`
    : "";
  const nextAction = pipeline?.next_action;
  const nextStepLabel = nextAction?.label || stepLabels[pipeline?.next_step ?? ""] || (language === "zh" ? "查看项目库" : "Open Project Library");
  const openPipelineStep = (stepKey: string) => {
    if (stepKey === "settings") onOpenView("settings");
    else if (stepKey === "sync") onSyncChannel();
    else if (stepKey === "analyze") onOpenView("video-report");
    else if (stepKey === "clean_script") onOpenView("video-report");
    else if (stepKey === "story_workbench") onOpenView("video-report");
    else if (stepKey === "story_structure") onOpenView("video-report");
    else if (stepKey === "imitation_factory") onOpenView("imitation-factory");
    else if (stepKey === "quality_check") onOpenView("imitation-factory");
    else if (stepKey === "export_publish") onOpenView("project-library");
    else if (stepKey === "project_library") onOpenView("project-library");
    else onOpenView("project-library");
  };
  const openNextStep = () => {
    if (nextAction?.action_type === "sync_channel") {
      onSyncChannel();
      return;
    }
    if (nextAction?.target_view && nextAction.target_view !== "dashboard") {
      onOpenView(nextAction.target_view as "tasks" | "video-report" | "imitation-factory" | "project-library" | "settings");
      return;
    }
    openPipelineStep(pipeline?.next_step ?? "project_library");
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
          <button
            className="secondary-action"
            disabled={isWorking || !data.recent_videos.some(video => video.url && video.analysis_status !== "complete")}
            onClick={() => onBatchAnalyzeVideos()}
            type="button"
          >
            <Clapperboard aria-hidden="true" size={20} />
            <span>{t.batchAnalyze}</span>
          </button>
          {isEmptyWorkspace && (
            <button className="secondary-action" disabled={isWorking} onClick={onLoadDemoWorkspace} type="button">
              <ListChecks aria-hidden="true" size={20} />
              <span>{t.loadDemo}</span>
            </button>
          )}
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

      <section className="quality-metrics-grid" aria-label={t.qualityMetrics}>
        {qualityMetricCards.map(metric => (
          <article className="quality-metric-card" key={metric.label}>
            <p className="metric-label">{metric.label}</p>
            <p className="metric-value">{isLoading ? "..." : metric.value}</p>
            <p className="metric-detail">{metric.detail}</p>
          </article>
        ))}
      </section>

      {failedGateReasons.length > 0 && (
        <section className="panel quality-failure-panel" aria-label={t.qualityFailureReasons}>
          <div className="panel-heading">
            <div>
              <p className="eyebrow">{t.qualityMetrics}</p>
              <h2>{t.qualityFailureReasons}</h2>
            </div>
            <ShieldCheck aria-hidden="true" size={22} />
          </div>
          <p className="panel-note">{t.qualityFailureIntro}</p>
          <div className="quality-failure-list">
            {failedGateReasons.map(reason => (
              <article className="quality-failure-item" key={reason.key}>
                <div>
                  <strong>{reason.label || reason.key}</strong>
                  <small>{reason.next_action}</small>
                </div>
                <span>
                  {reason.count} / {Number(reason.draft_percent || 0).toFixed(1)}%
                  <small>{t.affectedDrafts}</small>
                </span>
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="panel weekly-production-panel" aria-label={t.weeklyProduction}>
        <div className="panel-heading">
          <div>
            <p className="eyebrow">{t.weeklyWindow}</p>
            <h2>{t.weeklyProduction}</h2>
          </div>
          <ListChecks aria-hidden="true" size={22} />
        </div>
        <div className="weekly-production-grid">
          {weeklyProductionCards.map(metric => (
            <article className="quality-metric-card" key={metric.label}>
              <p className="metric-label">{metric.label}</p>
              <p className="metric-value">{isLoading ? "..." : metric.value}</p>
              <p className="metric-detail">{metric.detail}</p>
            </article>
          ))}
        </div>
      </section>

      {(creationFunnel?.steps?.length ?? 0) > 0 && (
        <section className="panel creation-funnel-panel" aria-label={t.creationFunnel}>
          <div className="panel-heading">
            <div>
              <p className="eyebrow">{t.qualityMetrics}</p>
              <h2>{t.creationFunnel}</h2>
            </div>
            <BarChart3 aria-hidden="true" size={22} />
          </div>
          <div className="creation-funnel-list">
            {creationFunnel?.steps.map(step => (
              <article className="creation-funnel-step" key={step.key}>
                <p>{funnelLabels[step.key] ?? step.label ?? step.key}</p>
                <strong>{isLoading ? "..." : step.count}</strong>
                <small>{t.conversionRate}: {Number(step.conversion_percent || 0).toFixed(1)}%</small>
              </article>
            ))}
          </div>
          <div className="creation-funnel-bottleneck">
            <strong>
              {t.bottleneck}:{" "}
              {creationFunnel?.bottleneck
                ? `${bottleneckLabel} / ${Number(creationFunnel.bottleneck.conversion_percent || 0).toFixed(1)}%`
                : t.noBottleneck}
            </strong>
            {creationFunnel?.bottleneck?.summary && <p>{creationFunnel.bottleneck.summary}</p>}
            {creationFunnel?.bottleneck?.next_action && <small>{creationFunnel.bottleneck.next_action}</small>}
          </div>
        </section>
      )}

      {(data.topic_candidates?.length ?? 0) > 0 && (
        <section className="panel topic-candidate-panel" aria-label={t.candidates}>
          <div className="panel-heading">
            <div>
              <p className="eyebrow">{t.candidates}</p>
              <h2>{t.candidates}</h2>
            </div>
            <Lightbulb aria-hidden="true" size={22} />
          </div>
          <p className="panel-note">{t.candidateIntro}</p>
          <div className="topic-candidate-controls">
            <label>
              <span>{t.candidateChannel}</span>
              <select onChange={event => setCandidateChannelFilter(event.target.value)} value={candidateChannelFilter}>
                <option value="">{t.all}</option>
                {candidateChannelOptions.map(option => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </label>
            <label>
              <span>{t.candidateTopic}</span>
              <select onChange={event => setCandidateTopicFilter(event.target.value)} value={candidateTopicFilter}>
                <option value="">{t.all}</option>
                {candidateTopicOptions.map(option => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </label>
            <label>
              <span>{t.candidateFreshness}</span>
              <select onChange={event => setCandidateFreshnessFilter(event.target.value)} value={candidateFreshnessFilter}>
                <option value="">{t.all}</option>
                {candidateFreshnessOptions.map(option => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </label>
            <label>
              <span>{t.candidateViews}</span>
              <select onChange={event => setCandidateViewFilter(event.target.value)} value={candidateViewFilter}>
                <option value="">{t.all}</option>
                {candidateViewOptions.map(option => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </label>
            <label>
              <span>{t.candidateSort}</span>
              <select onChange={event => setCandidateSort(event.target.value as CandidateSort)} value={candidateSort}>
                <option value="score">{t.sortScore}</option>
                <option value="views">{t.sortViews}</option>
                <option value="freshness">{t.sortFreshness}</option>
              </select>
            </label>
          </div>
          <div className="topic-candidate-bulkbar">
            <div>
              <strong>{t.candidateMatched}: {filteredCandidates.length}</strong>
              <span>{t.candidateSelected}: {selectedCandidateUrls.length}</span>
            </div>
            <div className="topic-candidate-bulk-actions">
              <button
                className="secondary-action compact-action"
                disabled={!candidateUrls.length}
                onClick={selectFilteredCandidates}
                type="button"
              >
                {t.selectFiltered}
              </button>
              <button
                className="secondary-action compact-action"
                disabled={!selectedCandidateUrls.length}
                onClick={clearSelectedCandidates}
                type="button"
              >
                {t.clearSelected}
              </button>
              <button
                className="primary-action compact-action"
                disabled={isWorking || !selectedCandidateUrls.length}
                onClick={() => onBatchAnalyzeVideos(selectedCandidateUrls)}
                type="button"
              >
                <Clapperboard aria-hidden="true" size={18} />
                {t.batchSelected} ({selectedCandidateUrls.length})
              </button>
            </div>
          </div>
          <div className="topic-candidate-list">
            {filteredCandidates.map(candidate => (
              <article className="topic-candidate-item" key={candidate.id ?? candidate.url}>
                <label className="topic-candidate-checkbox">
                  <input
                    checked={Boolean(candidate.url && selectedCandidateUrls.includes(candidate.url))}
                    disabled={!candidate.url}
                    onChange={() => candidate.url && toggleCandidate(candidate.url)}
                    type="checkbox"
                  />
                </label>
                <div>
                  <p className="video-title">{candidate.title}</p>
                  <p className="video-meta">{candidate.published_at || "-"} / {candidate.view_count ?? 0} views</p>
                  <div className="topic-candidate-reasons">
                    {candidate.topic_group && <span className="status-pill status-pill-muted">{candidate.topic_group}</span>}
                    {candidate.freshness_bucket && <span className="status-pill status-pill-muted">{candidate.freshness_bucket}</span>}
                    {candidate.view_bucket && <span className="status-pill status-pill-muted">{candidate.view_bucket}</span>}
                    {candidate.reasons.map(reason => (
                      <span className="status-pill status-pill-muted" key={reason}>{reason}</span>
                    ))}
                  </div>
                  <div className="topic-candidate-dimensions">
                    <span>{t.viralPotential}: {candidate.viral_potential ?? 0}</span>
                    <span>{t.storyFit}: {candidate.story_fit ?? 0}</span>
                    <span>{t.structureReuse}: {candidate.structure_reuse_value ?? 0}</span>
                  </div>
                  {(candidate.risk_flags?.length ?? 0) > 0 && (
                    <p className="topic-candidate-risk">
                      {t.candidateRisks}: {candidate.risk_flags?.join(" / ")}
                    </p>
                  )}
                  {(candidate.recommendation_summary || candidate.recommended_action) && (
                    <div className={`topic-candidate-recommendation recommendation-${candidate.recommendation_level || "low"}`}>
                      {candidate.recommendation_summary && (
                        <p>
                          <strong>{t.candidateRecommendation}: </strong>
                          {candidate.recommendation_summary}
                        </p>
                      )}
                      {candidate.recommended_action && (
                        <p>
                          <strong>{t.candidateNextAction}: </strong>
                          {candidate.recommended_action}
                        </p>
                      )}
                    </div>
                  )}
                </div>
                <strong className="topic-candidate-score">{candidate.score}</strong>
                <button className="secondary-action compact-action" disabled={isWorking || !candidate.url} onClick={() => analyze(candidate)} type="button">
                  {t.analyze}
                </button>
              </article>
            ))}
          </div>
        </section>
      )}

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
              <h2>{nextStepLabel}</h2>
            </div>
            <ListChecks aria-hidden="true" size={22} />
          </div>
          <div className="pipeline-status-list">
            {(pipeline?.steps ?? []).map(step => (
              <div className="pipeline-status-item" key={step.key}>
                <div className="pipeline-step-main">
                  <span className={`status-pill status-pill-${step.status === "complete" ? "ok" : "muted"}`}>
                    {step.status === "complete" ? t.stepDone : t.stepPending}
                  </span>
                  <div>
                    <strong>{stepLabels[step.key] ?? step.key}</strong>
                    <p>{stepDetails[step.key] ?? ""}</p>
                  </div>
                </div>
                <small>{step.count}</small>
                <button
                  className="secondary-action compact-action pipeline-step-action"
                  disabled={isWorking || isLoading}
                  onClick={() => openPipelineStep(step.key)}
                  type="button"
                >
                  {t.stepAction}
                </button>
              </div>
            ))}
          </div>
          <div className="pipeline-next-action">
            <div>
              <button className="primary-action compact-action" disabled={isWorking || isLoading} onClick={openNextStep} type="button">
                <PlayCircle aria-hidden="true" size={18} />
                {t.nextAction}: {nextStepLabel}
              </button>
              {nextAction?.description && <small>{nextAction.description}</small>}
            </div>
            <p>{t.activeJobs}: {isLoading ? "..." : activeJobs}</p>
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
