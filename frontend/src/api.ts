import type {
  CacheInfo,
  CopyDraft,
  DashboardData,
  DashboardJob,
  HealthCheckResponse,
  ImitationFactoryResponse,
  ImitationProject,
  IdeaCard,
  MonitorRunResult,
  MonitorStatus,
  SampleAnalysis,
  ScriptDraft,
  StyleProfile,
  TaskCenterResponse,
  TranscriptBundle,
  TranslationRecord,
  TranslationStatus,
  VideoReportData,
  WorkspaceSettings
} from "./types";

const emptyDashboard: DashboardData = {
  channels: [],
  recent_videos: [],
  idea_cards: [],
  jobs: [],
  comment_collector_status: "unknown"
};

async function errorFromResponse(response: Response, fallback: string): Promise<Error> {
  try {
    const data = (await response.json()) as { detail?: string };
    return new Error(data.detail ?? fallback);
  } catch {
    return new Error(fallback);
  }
}

async function requireOk(response: Response, fallback: string): Promise<void> {
  if (!response.ok) {
    throw await errorFromResponse(response, fallback);
  }
}

export async function fetchDashboard(): Promise<DashboardData> {
  const response = await fetch("/api/dashboard");

  await requireOk(response, "Unable to load dashboard.");

  const data = (await response.json()) as Partial<DashboardData>;

  return {
    channels: data.channels ?? [],
    recent_videos: data.recent_videos ?? [],
    idea_cards: data.idea_cards ?? [],
    jobs: data.jobs ?? [],
    comment_collector_status: data.comment_collector_status ?? "unknown"
  };
}

export const defaultWorkspaceSettings: WorkspaceSettings = {
  channel_url: "",
  channel_urls: [],
  browser_engine: "playwright",
  browser_headless: true,
  browser_path: "",
  browser_debug_port: null,
  browser_cdp_url: "http://127.0.0.1:9222",
  openai_base_url: "http://localhost:53881/v1",
  openai_translation_model: "gpt-5.5",
  openai_analysis_model: "gpt-5.5",
  openai_api_key: "",
  openai_api_key_set: false,
  monitor_enabled: false,
  monitor_interval_minutes: 180,
  monitor_auto_analyze: false,
  monitor_auto_translate: false,
  monitor_min_views: 0
};

export async function fetchSettings(): Promise<WorkspaceSettings> {
  const response = await fetch("/api/settings");

  if (!response.ok) {
    return defaultWorkspaceSettings;
  }

  const data = (await response.json()) as Partial<WorkspaceSettings>;

  return {
    channel_url: data.channel_url ?? "",
    channel_urls: data.channel_urls ?? (data.channel_url ? [data.channel_url] : []),
    browser_engine: data.browser_engine ?? "playwright",
    browser_headless: data.browser_headless ?? true,
    browser_path: data.browser_path ?? "",
    browser_debug_port: data.browser_debug_port ?? null,
    browser_cdp_url: data.browser_cdp_url ?? "http://127.0.0.1:9222",
    openai_base_url: data.openai_base_url ?? "http://localhost:53881/v1",
    openai_translation_model: data.openai_translation_model ?? "gpt-5.5",
    openai_analysis_model: data.openai_analysis_model ?? "gpt-5.5",
    openai_api_key: "",
    openai_api_key_set: data.openai_api_key_set ?? false,
    monitor_enabled: data.monitor_enabled ?? false,
    monitor_interval_minutes: data.monitor_interval_minutes ?? 180,
    monitor_auto_analyze: data.monitor_auto_analyze ?? false,
    monitor_auto_translate: data.monitor_auto_translate ?? false,
    monitor_min_views: data.monitor_min_views ?? 0
  };
}

export async function saveSettings(settings: WorkspaceSettings): Promise<WorkspaceSettings> {
  const response = await fetch("/api/settings", {
    body: JSON.stringify(settings),
    headers: {
      "Content-Type": "application/json"
    },
    method: "PUT"
  });

  if (!response.ok) {
    throw new Error("Unable to save workspace settings.");
  }

  return (await response.json()) as WorkspaceSettings;
}

export async function syncChannel(): Promise<void> {
  const response = await fetch("/api/tasks/channel-sync/start", { method: "POST" });

  if (!response.ok) {
    throw new Error("Unable to sync channel.");
  }
}

export async function analyzeVideo(videoUrl: string): Promise<void> {
  const response = await fetch("/api/tasks/video-analysis/start", {
    body: JSON.stringify({ video_url: videoUrl }),
    headers: {
      "Content-Type": "application/json"
    },
    method: "POST"
  });

  if (!response.ok) {
    throw new Error("Unable to analyze video.");
  }
}

export async function analyzeSample(videoUrl: string, videoTitle = "", videoId = ""): Promise<DashboardJob> {
  const response = await fetch("/api/tasks/sample-analysis/start", {
    body: JSON.stringify({ video_url: videoUrl, video_title: videoTitle, video_id: videoId }),
    headers: {
      "Content-Type": "application/json"
    },
    method: "POST"
  });

  if (!response.ok) {
    let message = "Unable to analyze sample.";
    try {
      const data = (await response.json()) as { detail?: string };
      message = data.detail ?? message;
    } catch {
      // Keep the default message when the response is not JSON.
    }
    throw new Error(message);
  }

  const data = (await response.json()) as { task?: DashboardJob };
  if (!data.task) {
    throw new Error("Sample task was not returned by the backend.");
  }
  return data.task;
}

export async function fetchSampleAnalyses(): Promise<SampleAnalysis[]> {
  const response = await fetch("/api/samples");

  await requireOk(response, "Unable to load sample analyses.");

  const data = (await response.json()) as { sample_analyses?: SampleAnalysis[] };
  return data.sample_analyses ?? [];
}

export async function fetchSampleLibrary(): Promise<{ samples: SampleAnalysis[]; tag_suggestions: string[] }> {
  const response = await fetch("/api/samples/library");

  await requireOk(response, "Unable to load sample library.");

  const data = (await response.json()) as { samples?: SampleAnalysis[]; tag_suggestions?: string[] };
  return {
    samples: data.samples ?? [],
    tag_suggestions: data.tag_suggestions ?? []
  };
}

export async function updateSampleLibraryItem(
  sampleId: string,
  patch: { favorite?: boolean; tags?: string[]; notes?: string }
): Promise<SampleAnalysis> {
  const response = await fetch(`/api/samples/${encodeURIComponent(sampleId)}`, {
    body: JSON.stringify(patch),
    headers: {
      "Content-Type": "application/json"
    },
    method: "PATCH"
  });

  if (!response.ok) {
    throw new Error("Unable to update sample.");
  }

  const data = (await response.json()) as { sample: SampleAnalysis };
  return data.sample;
}

export async function mergeSampleStyle(sampleIds: string[], name: string): Promise<StyleProfile> {
  const response = await fetch("/api/samples/merge-style", {
    body: JSON.stringify({ sample_ids: sampleIds, name }),
    headers: {
      "Content-Type": "application/json"
    },
    method: "POST"
  });

  if (!response.ok) {
    throw new Error("Unable to merge selected samples.");
  }

  const data = (await response.json()) as { style_profile: StyleProfile };
  return data.style_profile;
}

export async function fetchTasks(): Promise<TaskCenterResponse> {
  const response = await fetch("/api/tasks");

  if (!response.ok) {
    return { tasks: [], redis: { configured: false, status: "failed", message: "Unable to load tasks." } };
  }

  return (await response.json()) as TaskCenterResponse;
}

export async function retryTask(taskId: string): Promise<TaskCenterResponse> {
  const response = await fetch(`/api/tasks/${encodeURIComponent(taskId)}/retry`, { method: "POST" });

  if (!response.ok) {
    throw new Error("Unable to retry task.");
  }

  const data = (await response.json()) as { task?: DashboardData["jobs"][number]; redis?: TaskCenterResponse["redis"] };
  return {
    tasks: data.task ? [data.task] : [],
    redis: data.redis ?? { configured: false, status: "skipped", message: "" }
  };
}

export async function runTask(taskId: string): Promise<TaskCenterResponse> {
  const response = await fetch(`/api/tasks/${encodeURIComponent(taskId)}/run`, { method: "POST" });

  if (!response.ok) {
    throw new Error("Unable to run task.");
  }

  const data = (await response.json()) as { task?: DashboardData["jobs"][number]; redis?: TaskCenterResponse["redis"] };
  return {
    tasks: data.task ? [data.task] : [],
    redis: data.redis ?? { configured: false, status: "skipped", message: "" }
  };
}

export async function runNextQueuedTask(): Promise<TaskCenterResponse> {
  const response = await fetch("/api/tasks/worker/run-next", { method: "POST" });

  if (!response.ok) {
    throw new Error("Unable to run next queued task.");
  }

  const data = (await response.json()) as { task?: DashboardData["jobs"][number] | null; redis?: TaskCenterResponse["redis"]; queue?: TaskCenterResponse["queue"] };
  return {
    tasks: data.task ? [data.task] : [],
    redis: data.redis ?? { configured: false, status: "skipped", message: "" },
    queue: data.queue
  };
}

export async function fetchHealthChecks(): Promise<HealthCheckResponse> {
  const response = await fetch("/api/health/checks");

  if (!response.ok) {
    return { summary: { status: "failed", failed: 1, warnings: 0 }, checks: [] };
  }

  return (await response.json()) as HealthCheckResponse;
}

export async function fetchMonitorStatus(): Promise<MonitorStatus | null> {
  const response = await fetch("/api/monitor");

  if (!response.ok) {
    return null;
  }

  return (await response.json()) as MonitorStatus;
}

export async function runMonitorOnce(): Promise<MonitorRunResult> {
  const response = await fetch("/api/monitor/run", { method: "POST" });

  if (!response.ok) {
    throw new Error("Unable to run auto monitor.");
  }

  return (await response.json()) as MonitorRunResult;
}

export async function fetchCacheInfo(): Promise<CacheInfo | null> {
  const response = await fetch("/api/cache");

  if (!response.ok) {
    return null;
  }

  return (await response.json()) as CacheInfo;
}

export async function clearCache(target: "samples" | "transcripts" | "translations" | "all"): Promise<CacheInfo | null> {
  const response = await fetch("/api/cache/clear", {
    body: JSON.stringify({ target }),
    headers: {
      "Content-Type": "application/json"
    },
    method: "POST"
  });

  if (!response.ok) {
    throw new Error("Unable to clear cache.");
  }

  const data = (await response.json()) as { paths?: CacheInfo["paths"] };
  const current = await fetchCacheInfo();
  return current ?? (data.paths ? { policy: { usage: "manual_research", low_frequency: true, retains_full_video: false, sample_scope: "first_five_minutes" }, paths: data.paths } : null);
}

export async function reanalyzeLatestReport(): Promise<void> {
  const response = await fetch("/api/reports/latest/reanalyze", { method: "POST" });

  if (!response.ok) {
    throw new Error("Unable to reanalyze latest report.");
  }
}

export async function fetchLatestReport(): Promise<VideoReportData | null> {
  const response = await fetch("/api/reports/latest");

  if (!response.ok) {
    return null;
  }

  const data = (await response.json()) as { report?: VideoReportData | null };
  return data.report ?? null;
}

export async function fetchReports(): Promise<VideoReportData[]> {
  const response = await fetch("/api/reports");

  await requireOk(response, "Unable to load reports.");

  const data = (await response.json()) as { reports?: VideoReportData[] };
  return data.reports ?? [];
}

export async function fetchReport(reportId: string): Promise<VideoReportData | null> {
  const response = await fetch(`/api/reports/${encodeURIComponent(reportId)}`);

  if (!response.ok) {
    return null;
  }

  const data = (await response.json()) as { report?: VideoReportData | null };
  return data.report ?? null;
}

export async function fetchIdeas(): Promise<IdeaCard[]> {
  const response = await fetch("/api/ideas");

  await requireOk(response, "Unable to load idea cards.");

  const data = (await response.json()) as { idea_cards?: IdeaCard[] };
  return data.idea_cards ?? [];
}

export async function pruneStaleIdeas(): Promise<{ removed_count: number; idea_cards: IdeaCard[] }> {
  const response = await fetch("/api/ideas/prune-stale", { method: "POST" });

  if (!response.ok) {
    throw new Error("Unable to clean stale idea cards.");
  }

  const data = (await response.json()) as { removed_count?: number; idea_cards?: IdeaCard[] };
  return {
    removed_count: data.removed_count ?? 0,
    idea_cards: data.idea_cards ?? []
  };
}

export async function fetchLatestTranscript(): Promise<TranscriptBundle> {
  const response = await fetch("/api/reports/latest/transcript");

  if (!response.ok) {
    return { transcript: null, translation: null };
  }

  return (await response.json()) as TranscriptBundle;
}

export async function fetchReportTranscript(reportId: string): Promise<TranscriptBundle> {
  const response = await fetch(`/api/reports/${encodeURIComponent(reportId)}/transcript`);

  if (!response.ok) {
    return { transcript: null, translation: null };
  }

  return (await response.json()) as TranscriptBundle;
}

export async function fetchStyles(): Promise<{ style_profiles: StyleProfile[]; copy_drafts: CopyDraft[] }> {
  const response = await fetch("/api/styles");

  await requireOk(response, "Unable to load styles.");

  const data = (await response.json()) as { style_profiles?: StyleProfile[]; copy_drafts?: CopyDraft[] };
  return {
    style_profiles: data.style_profiles ?? [],
    copy_drafts: data.copy_drafts ?? []
  };
}

export async function fetchScripts(): Promise<ScriptDraft[]> {
  const response = await fetch("/api/scripts");

  await requireOk(response, "Unable to load scripts.");

  const data = (await response.json()) as { script_drafts?: ScriptDraft[] };
  return data.script_drafts ?? [];
}

export async function generateScript(ideaId: string, styleId?: string): Promise<ScriptDraft> {
  const response = await fetch("/api/scripts/generate", {
    body: JSON.stringify({ idea_id: ideaId, style_id: styleId || null }),
    headers: {
      "Content-Type": "application/json"
    },
    method: "POST"
  });

  if (!response.ok) {
    throw new Error("Unable to generate script.");
  }

  const data = (await response.json()) as { script_draft: ScriptDraft };
  return data.script_draft;
}

export async function rewriteScript(scriptId: string, styleId?: string): Promise<ScriptDraft> {
  const response = await fetch(`/api/scripts/${encodeURIComponent(scriptId)}/rewrite`, {
    body: JSON.stringify({ style_id: styleId || null }),
    headers: {
      "Content-Type": "application/json"
    },
    method: "POST"
  });

  if (!response.ok) {
    throw new Error("Unable to rewrite script.");
  }

  const data = (await response.json()) as { script_draft: ScriptDraft };
  return data.script_draft;
}

export async function updateScript(scriptId: string, patch: { selected_title?: string; opening_30s?: string; full_script?: string }): Promise<ScriptDraft> {
  const response = await fetch(`/api/scripts/${encodeURIComponent(scriptId)}`, {
    body: JSON.stringify(patch),
    headers: {
      "Content-Type": "application/json"
    },
    method: "PATCH"
  });

  if (!response.ok) {
    throw new Error("Unable to update script.");
  }

  const data = (await response.json()) as { script_draft: ScriptDraft };
  return data.script_draft;
}

export async function exportScriptMarkdown(scriptId: string): Promise<{ filename: string; markdown: string }> {
  const response = await fetch(`/api/scripts/${encodeURIComponent(scriptId)}/markdown`);

  if (!response.ok) {
    throw new Error("Unable to export script markdown.");
  }

  return (await response.json()) as { filename: string; markdown: string };
}

export async function fetchImitationFactory(): Promise<ImitationFactoryResponse> {
  const response = await fetch("/api/imitation-factory");

  await requireOk(response, "Unable to load imitation factory.");

  const data = (await response.json()) as Partial<ImitationFactoryResponse>;
  return {
    projects: data.projects ?? [],
    reports: data.reports ?? [],
    ideas: data.ideas ?? []
  };
}

export async function createImitationProject(payload: {
  report_id: string;
  idea_id?: string | null;
  direction: string;
  output_type: "short_fiction" | "story_recap" | "short_drama" | "interactive";
  similarity_level: "low" | "medium" | "high";
  target_length: string;
  keep_narration: boolean;
}): Promise<ImitationProject> {
  const response = await fetch("/api/imitation-factory/projects", {
    body: JSON.stringify(payload),
    headers: {
      "Content-Type": "application/json"
    },
    method: "POST"
  });

  await requireOk(response, "Unable to create imitation project.");

  const data = (await response.json()) as { project: ImitationProject };
  return data.project;
}

export async function exportImitationMarkdown(projectId: string): Promise<{ filename: string; markdown: string }> {
  const response = await fetch(`/api/imitation-factory/projects/${encodeURIComponent(projectId)}/markdown`);

  await requireOk(response, "Unable to export imitation reference.");

  return (await response.json()) as { filename: string; markdown: string };
}

export async function learnLatestStyle(name?: string): Promise<StyleProfile> {
  const response = await fetch("/api/styles/learn-latest", {
    body: JSON.stringify({ name: name?.trim() || null }),
    headers: {
      "Content-Type": "application/json"
    },
    method: "POST"
  });

  if (!response.ok) {
    throw new Error("Unable to learn style from latest report.");
  }

  const data = (await response.json()) as { style_profile: StyleProfile };
  return data.style_profile;
}

export async function applyStyle(styleId: string, ideaId: string): Promise<CopyDraft> {
  const response = await fetch("/api/styles/apply", {
    body: JSON.stringify({ style_id: styleId, idea_id: ideaId, draft_type: "opening_script" }),
    headers: {
      "Content-Type": "application/json"
    },
    method: "POST"
  });

  if (!response.ok) {
    throw new Error("Unable to apply style to idea.");
  }

  const data = (await response.json()) as { copy_draft: CopyDraft };
  return data.copy_draft;
}

export async function translateLatestReport(force = false): Promise<{ status: string; translation?: TranslationRecord; translation_status?: TranslationStatus }> {
  const response = await fetch("/api/reports/latest/translate", {
    body: JSON.stringify({ force }),
    headers: {
      "Content-Type": "application/json"
    },
    method: "POST"
  });

  if (!response.ok) {
    let message = "Unable to translate transcript.";
    try {
      const data = (await response.json()) as { detail?: string };
      message = data.detail ?? message;
    } catch {
      // Keep the default message when the response is not JSON.
    }
    throw new Error(message);
  }

  return (await response.json()) as { status: string; translation?: TranslationRecord; translation_status?: TranslationStatus };
}

export async function translateReport(reportId: string, force = false): Promise<{ status: string; translation?: TranslationRecord; translation_status?: TranslationStatus }> {
  const response = await fetch(`/api/reports/${encodeURIComponent(reportId)}/translate`, {
    body: JSON.stringify({ force }),
    headers: {
      "Content-Type": "application/json"
    },
    method: "POST"
  });

  if (!response.ok) {
    let message = "Unable to translate transcript.";
    try {
      const data = (await response.json()) as { detail?: string };
      message = data.detail ?? message;
    } catch {
      // Keep the default message when the response is not JSON.
    }
    throw new Error(message);
  }

  return (await response.json()) as { status: string; translation?: TranslationRecord; translation_status?: TranslationStatus };
}

export async function queueReportTranslation(reportId: string, force = false): Promise<DashboardJob> {
  const response = await fetch(`/api/tasks/reports/${encodeURIComponent(reportId)}/translation/start`, {
    body: JSON.stringify({ force }),
    headers: {
      "Content-Type": "application/json"
    },
    method: "POST"
  });

  if (!response.ok) {
    let message = "Unable to queue translation task.";
    try {
      const data = (await response.json()) as { detail?: string };
      message = data.detail ?? message;
    } catch {
      // Keep the default message when the response is not JSON.
    }
    throw new Error(message);
  }

  const data = (await response.json()) as { task: DashboardJob };
  return data.task;
}
