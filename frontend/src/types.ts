export interface Channel {
  id?: string;
  title?: string;
  url?: string;
  subscriber_count?: number;
  video_count?: number;
  collection_status?: string;
  collection_error?: string;
  synced_at?: string;
}

export interface RecentVideo {
  id?: string;
  youtube_video_id?: string;
  title?: string;
  channel_title?: string;
  channel_url?: string;
  published_at?: string;
  view_count?: number;
  url?: string;
  analysis_status?: string;
}

export interface SampleFrame {
  timestamp_seconds: number;
  path: string;
}

export interface SampleAnalysis {
  id: string;
  video_id?: string;
  video_url: string;
  video_title: string;
  status: "complete" | "failed";
  analyzed_seconds: number;
  analysis_basis?: string;
  transcript_source?: string;
  transcript_language?: string;
  opening_transcript?: string;
  opening_transcript_length?: number;
  frame_interval_seconds?: number;
  frame_count: number;
  frames: SampleFrame[];
  visual_summary: string;
  opening_hook: string;
  story_setup?: string;
  protagonist_position?: string;
  first_conflict?: string;
  first_turning_point?: string;
  retention_drivers?: string[];
  hook_sequence?: string[];
  pacing_notes: string[];
  reuse_template: string[];
  risk_notes: string[];
  favorite?: boolean;
  tags?: string[];
  notes?: string;
  created_at: string;
}

export interface IdeaCard {
  id?: string;
  title?: string;
  angle?: string;
  why_it_works?: string;
  outline?: string[];
  risk_notes?: string;
  score?: number;
  source?: string;
  source_video_url?: string;
  source_report_id?: string;
  analysis_source?: string;
  analysis_status?: string;
}

export interface StyleProfile {
  id: string;
  name: string;
  source_report_id?: string;
  source_sample_ids?: string[];
  source_video_title?: string;
  source_video_url?: string;
  topic_type?: string;
  opening_formula?: string;
  title_formula?: string;
  rhythm_formula?: string[];
  emotional_engine?: string[];
  hook_patterns?: string[];
  sentence_style?: string;
  reusable_rules?: string[];
  avoid_copying?: string[];
  created_at?: string;
}

export interface CopyDraft {
  id: string;
  style_id: string;
  idea_id: string;
  draft_type: string;
  title: string;
  provider: string;
  model: string;
  copy: string;
  created_at?: string;
}

export interface ScriptDraft {
  id: string;
  idea_id: string;
  style_id: string;
  parent_id: string;
  version: number;
  title_options: string[];
  selected_title: string;
  opening_30s: string;
  full_script: string;
  markdown: string;
  created_at: string;
}

export interface DashboardJob {
  id?: string;
  status?: string;
  kind?: string;
  current_step?: string;
  current_step_label?: string;
  target_url?: string;
  queue_status?: string;
  queue_message?: string;
  error_message?: string;
  retry_of?: string;
  payload?: Record<string, unknown>;
  result_json?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
  steps?: TaskStep[];
}

export interface DashboardData {
  channels: Channel[];
  recent_videos: RecentVideo[];
  idea_cards: IdeaCard[];
  jobs: DashboardJob[];
  comment_collector_status: string;
}

export interface VideoReportData {
  id: string;
  youtube_video_id?: string;
  video_url: string;
  video_title: string;
  channel_title?: string;
  summary: string;
  creative_breakdown: {
    topic_type: string;
    title_hook: string;
    opening_hook: string;
    structure: string[];
    emotional_curve: string[];
    monetization_intent?: string | null;
  };
  growth_judgement: {
    score: number;
    reasons: string[];
    channel_history_links?: string[];
  };
  idea_cards?: IdeaCard[];
  comment_insights: {
    status: "ok" | "not_configured" | "failed";
    pain_points?: string[];
    objections?: string[];
    praise_points?: string[];
    controversy_signals?: string[];
  };
  collection_evidence?: {
    metadata_source?: string;
    metadata_status?: string;
    transcript_source?: string;
    transcript_status?: string;
    transcript_language?: string;
    transcript_length?: number;
    is_auto_caption?: boolean;
    transcript_error?: string;
    comments_status?: string;
    analysis_source?: string;
    analysis_status?: string;
    analysis_error?: string;
    llm_participated?: boolean;
    used_rule_fallback?: boolean;
    frame_status?: string;
    frame_count?: number;
  };
  created_at: string;
}

export interface TranscriptRecord {
  video_id: string;
  video_url: string;
  title: string;
  transcript_source: string;
  language: string;
  raw_text: string;
  raw_length: number;
  fetched_at: string;
}

export interface TranslationRecord {
  video_id: string;
  target_language: string;
  source_language: string;
  translated_text: string;
  translated_length: number;
  provider: string;
  model: string;
  translated_at: string;
}

export interface TranslationStatus {
  video_id: string;
  target_language: string;
  status: "running" | "complete" | "failed";
  translated_text?: string;
  completed_chunks?: number;
  total_chunks?: number;
  provider?: string;
  model?: string;
  error_message?: string;
  updated_at?: string;
}

export interface TranscriptBundle {
  transcript: TranscriptRecord | null;
  translation: TranslationRecord | null;
  translation_status?: TranslationStatus | null;
}

export interface TaskStep {
  key: string;
  label: string;
  status: "queued" | "running" | "complete" | "failed" | "pending" | string;
}

export interface TaskCenterResponse {
  tasks: DashboardJob[];
  redis: {
    configured: boolean;
    status: "ok" | "failed" | "skipped" | string;
    message: string;
    queued_count?: number;
  };
  queue?: {
    configured: boolean;
    status: "ok" | "failed" | "skipped" | string;
    message: string;
    queued_count: number;
  };
}

export interface HealthCheckItem {
  key: string;
  label: string;
  status: "ok" | "warning" | "failed" | "skipped" | string;
  message: string;
}

export interface HealthCheckResponse {
  summary: {
    status: "ok" | "degraded" | "failed" | string;
    failed: number;
    warnings: number;
  };
  checks: HealthCheckItem[];
}

export interface MonitorStatus {
  enabled: boolean;
  auto_analyze: boolean;
  channel_count?: number;
  interval_minutes: number;
  min_views: number;
  last_run_at: string;
  next_run_at: string;
  redis: TaskCenterResponse["redis"];
}

export interface MonitorRunResult {
  status: "complete" | "skipped" | string;
  reason?: string;
  new_video_count: number;
  queued_analysis_count: number;
  skipped_analysis_count: number;
  ran_at?: string;
  next_run_at?: string;
}

export interface CachePathInfo {
  path: string;
  file_count: number;
  size_bytes: number;
}

export interface CacheInfo {
  policy: {
    usage: string;
    low_frequency: boolean;
    retains_full_video: boolean;
    sample_scope: string;
  };
  paths: {
    samples: CachePathInfo;
    transcripts: CachePathInfo;
    translations: CachePathInfo;
  };
}

export interface WorkspaceSettings {
  channel_url: string;
  channel_urls: string[];
  browser_engine: "playwright" | "drission" | "cdp";
  browser_headless: boolean;
  browser_path: string;
  browser_debug_port: number | null;
  browser_cdp_url: string;
  openai_base_url: string;
  openai_translation_model: string;
  openai_analysis_model: string;
  openai_api_key: string;
  openai_api_key_set: boolean;
  monitor_enabled: boolean;
  monitor_interval_minutes: number;
  monitor_auto_analyze: boolean;
  monitor_auto_translate: boolean;
  monitor_min_views: number;
}

export type Language = "zh" | "en";
