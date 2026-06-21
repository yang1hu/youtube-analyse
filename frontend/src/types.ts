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
  source_report_ids?: string[];
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

export interface ImitationReportOption {
  id: string;
  video_title: string;
  video_url: string;
  created_at: string;
}

export interface ImitationIdeaOption {
  id: string;
  title: string;
  source_report_id: string;
}

export interface ImitationQualityCheck {
  key: string;
  label: string;
  target: string;
}

export interface ImitationSimilarityReport {
  text_overlap_percent: number;
  repeated_phrases: string[];
  reused_entities?: string[];
  structure_similarity: number;
  style_similarity: number;
  plot_similarity?: number;
  pacing_similarity?: number;
  semantic_similarity?: number;
  risk_level: "low" | "medium" | "high" | string;
  risk_segments?: ImitationRiskSegment[];
  quality_gate?: ImitationQualityGate;
  recommendations: string[];
}

export interface ImitationQualityGate {
  status: "pass" | "needs_revision" | "blocked" | string;
  passed: boolean;
  summary: string;
  target_similarity_level: string;
  checks: ImitationQualityGateCheck[];
  failed_checks: string[];
  next_action: string;
}

export interface ImitationQualityGateCheck {
  key: string;
  label: string;
  passed: boolean;
  value: number | string;
  target: string;
}

export interface ImitationRiskSegment {
  risk_type: string;
  severity: "low" | "medium" | "high" | string;
  action_level?: "must_fix" | "should_fix" | "acceptable" | string;
  action_label?: string;
  draft_excerpt: string;
  source_excerpt: string;
  matched_text?: string;
  draft_index?: number;
  recommendation: string;
  similarity_reason?: string;
  suggested_rewrite_mode?: string;
  rewrite_goal?: string;
  must_replace?: string[];
  can_keep?: string[];
}

export interface ImitationDraft {
  id: string;
  title: string;
  draft_text: string;
  source?: "manual" | "inkos" | string;
  status?: "publishable" | "needs_review" | "needs_revision" | string;
  similarity_report: ImitationSimilarityReport;
  inkos_result?: Record<string, unknown> & {
    parent_draft_id?: string;
    rewrite_strategy?: string;
    rewrite_comparison?: ImitationRewriteComparison;
  };
  created_at: string;
}

export interface ImitationRewriteComparison {
  mode: string;
  parent_draft_id: string;
  before: ImitationRewriteComparisonSnapshot;
  after: ImitationRewriteComparisonSnapshot;
  delta: {
    text_overlap_percent: number;
    semantic_similarity?: number;
    risk_segment_count: number;
  };
}

export interface ImitationRewriteComparisonSnapshot {
  risk_level: string;
  quality_gate_status: string;
  text_overlap_percent: number;
  semantic_similarity?: number;
  risk_segment_count: number;
}

export interface ImitationSimilarityHistoryItem {
  id: string;
  draft_id: string;
  draft_title: string;
  draft_source: string;
  risk_level: string;
  text_overlap_percent: number;
  structure_similarity: number;
  style_similarity: number;
  repeated_phrase_count: number;
  reused_entity_count: number;
  risk_segment_count: number;
  created_at: string;
}

export interface InkosRunRecord {
  id?: string;
  status: "complete" | "failed" | string;
  command?: string[];
  run_dir?: string;
  request?: {
    project_id?: string;
    source_report_id?: string;
    source_video_title?: string;
    direction?: string;
    output_type?: string;
    similarity_level?: string;
    target_length?: string;
    keep_narration?: boolean;
    reference_path?: string;
    reference_length?: number;
    reference_preview?: string;
    reference_markdown?: string;
    reference_run_id?: string;
    generation_preview?: InkosGenerationPreview;
  };
  result?: Record<string, unknown>;
  error_message?: string;
  draft_preview?: string;
  stdout?: string;
  stderr?: string;
  started_at?: string;
  completed_at?: string;
  ran_at?: string;
  elapsed_ms?: number;
}

export interface InkosGenerationPreview {
  reference_length: number;
  estimated_input_tokens: number;
  estimated_output_tokens: number;
  estimated_total_tokens: number;
  target_length: string;
  similarity_level: string;
  keep_narration: boolean;
  risk_notes: string[];
  checklist: string[];
}

export interface ImitationProject {
  id: string;
  name: string;
  source_report_id: string;
  source_idea_id: string;
  source_video_title: string;
  source_video_url: string;
  source_channel_title?: string;
  source_topic_type?: string;
  source_style_id?: string;
  source_style_name?: string;
  direction: string;
  output_type: "short_fiction" | "story_recap" | "short_drama" | "interactive" | string;
  similarity_level: "low" | "medium" | "high" | string;
  target_length: string;
  keep_narration: boolean;
  reference_markdown: string;
  inkos_preview?: InkosGenerationPreview;
  inkos_command: string;
  inkos_args?: string[];
  structure_template: string[];
  emotional_curve: string[];
  style_fingerprint: {
    average_sentence_length: number;
    paragraph_count: number;
    narration_person: string;
    pacing_rule: string;
    transition_style: string;
    opening_formula?: string;
    structure_density?: number;
  };
  reuse_constraints: string[];
  anti_copy_rules: string[];
  source_script_excerpt: string;
  story_workbench_source?: string;
  story_workbench_analysis?: Partial<StoryWorkbenchAnalysis>;
  source_style_profile?: Partial<StyleProfile>;
  quality_checks: ImitationQualityCheck[];
  risk_level: "low" | "medium" | "needs_review" | string;
  inkos_status: string;
  generated_drafts?: ImitationDraft[];
  latest_similarity_report?: ImitationSimilarityReport;
  similarity_report_history?: ImitationSimilarityHistoryItem[];
  last_inkos_run?: InkosRunRecord;
  inkos_run_history?: InkosRunRecord[];
  created_at: string;
}

export interface ImitationFactoryResponse {
  projects: ImitationProject[];
  reports: ImitationReportOption[];
  ideas: ImitationIdeaOption[];
  templates?: FavoriteStructureTemplate[];
  styles?: StyleProfile[];
  inkos_status?: InkosStatus;
}

export interface InkosStatus {
  configured: boolean;
  command: string;
  executable: string;
  resolved_path: string;
  project_dir: string;
  timeout_seconds: number;
  message: string;
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
  topic_candidates?: TopicCandidate[];
  idea_cards: IdeaCard[];
  jobs: DashboardJob[];
  comment_collector_status: string;
  reports_count?: number;
  imitation_projects_count?: number;
  pending_drafts_count?: number;
  publishable_drafts_count?: number;
  imitation_project_summaries?: ImitationProjectSummary[];
  favorite_structure_templates?: FavoriteStructureTemplate[];
  creation_pipeline?: CreationPipeline;
  creation_quality_metrics?: CreationQualityMetrics;
  creation_funnel?: CreationFunnel;
  weekly_production_metrics?: WeeklyProductionMetrics;
}

export interface CreationQualityMetrics {
  draft_count: number;
  quality_gate_pass_rate: number;
  average_text_overlap_percent: number;
  average_rewrite_count: number;
  high_risk_rate: number;
  failed_gate_reasons?: FailedGateReason[];
}

export interface FailedGateReason {
  key: string;
  label: string;
  count: number;
  draft_percent: number;
  next_action: string;
}

export interface WeeklyProductionMetrics {
  window_days: number;
  window_start: string;
  window_end: string;
  analyzed_report_count: number;
  created_project_count: number;
  generated_draft_count: number;
  publishable_draft_count: number;
}

export interface CreationFunnel {
  steps: CreationFunnelStep[];
  bottleneck?: CreationFunnelBottleneck | null;
}

export interface CreationFunnelStep {
  key: string;
  label: string;
  count: number;
  conversion_percent: number;
}

export interface CreationFunnelBottleneck {
  from: string;
  to: string;
  conversion_percent: number;
  summary?: string;
  next_action?: string;
}

export interface TopicCandidate extends RecentVideo {
  score: number;
  reasons: string[];
  viral_potential?: number;
  story_fit?: number;
  structure_reuse_value?: number;
  risk_flags?: string[];
  topic_group?: string;
  freshness_bucket?: string;
  view_bucket?: string;
  recommendation_summary?: string;
  recommended_action?: string;
  recommendation_level?: "priority" | "trial" | "watch" | "low" | string;
}

export interface CreationPipeline {
  steps: CreationPipelineStep[];
  next_step: string;
  next_action?: CreationPipelineNextAction;
  pending_video_count: number;
  active_job_count: number;
  ready_report_count: number;
  cleaned_story_count?: number;
  structured_story_count?: number;
  project_count: number;
  pending_draft_count: number;
  publishable_draft_count: number;
}

export interface CreationPipelineNextAction {
  label: string;
  description: string;
  target_view: "tasks" | "video-report" | "imitation-factory" | "project-library" | "settings" | "dashboard" | string;
  action_type: "open_view" | "sync_channel" | string;
}

export interface CreationPipelineStep {
  key: string;
  status: "complete" | "pending" | string;
  count: number;
  action?: "settings" | "sync" | "video-report" | "imitation-factory" | "project-library" | string;
}

export interface ImitationProjectSummary {
  id: string;
  name: string;
  source_video_title: string;
  source_video_url: string;
  source_channel_title: string;
  source_topic_type: string;
  direction: string;
  output_type: string;
  similarity_level: string;
  inkos_status: string;
  draft_count: number;
  latest_draft_status: string;
  latest_risk_level: string;
  latest_quality_gate_status?: string;
  latest_quality_gate_summary?: string;
  text_overlap_percent: number;
  production_stage?: "reference" | "needs_review" | "needs_revision" | "publishable" | "discarded" | string;
  production_priority?: "urgent" | "high" | "medium" | "low" | string;
  production_priority_reason?: string;
  recommended_next_action?: string;
  template_favorited?: boolean;
  updated_at?: string;
  created_at: string;
}

export interface BulkProjectStatusResult {
  status: string;
  updated_count: number;
  skipped_count: number;
  updated: { project_id: string; draft_id: string; status: string }[];
  skipped: { project_id: string; reason: string }[];
}

export interface BulkProjectMarkdownExport {
  filename: string;
  markdown: string;
  exported_count: number;
  skipped_count: number;
  exported: { project_id: string; name: string }[];
  skipped: { project_id: string; reason: string }[];
}

export interface BulkProjectCheckResult {
  checked_count: number;
  skipped_count: number;
  checked: {
    project_id: string;
    draft_id: string;
    status: string;
    risk_level: string;
    quality_gate_status: string;
    text_overlap_percent: number;
  }[];
  skipped: { project_id: string; reason: string }[];
}

export interface BulkProjectInkosResult {
  generated_count: number;
  skipped_count: number;
  failed_count: number;
  generated: { project_id: string; draft_id: string; status: string; title: string }[];
  skipped: { project_id: string; reason: string }[];
  failed: { project_id: string; reason: string; message?: string }[];
}

export interface FavoriteStructureTemplate {
  id: string;
  source_project_id: string;
  name: string;
  source_video_title: string;
  source_channel_title: string;
  source_topic_type: string;
  output_type: string;
  structure_template: string[];
  reuse_constraints: string[];
  anti_copy_rules: string[];
  tags?: string[];
  notes?: string;
  applicable_topics?: string[];
  success_cases?: string[];
  reuse_count?: number;
  publishable_rate?: number;
  average_risk_level?: string;
  average_text_overlap_percent?: number;
  recommendation_summary?: string;
  recommended_usage?: string;
  created_at: string;
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

export interface StoryWorkbenchSegment {
  index: number;
  label_key: string;
  label: string;
  text: string;
  length: number;
}

export interface StoryWorkbenchAnalysis {
  opening_5s_hook: string;
  first_30s_retention: string;
  protagonist_position: string;
  status_gap: string;
  first_payoff: string;
  middle_escalation: string;
  opposition_design: string;
  public_reversal: string;
  ending_suspense: string;
  reusable_template: string[];
  non_reusable_content: string[];
  structure_confidence: "low" | "medium" | "high" | string;
  analysis_basis: "cleaned_transcript" | "report_only" | string;
  manual_override?: boolean;
  manual_updated_at?: string;
  evidence?: Record<string, StoryWorkbenchEvidence>;
}

export interface StoryWorkbenchEvidence {
  segment_indexes: number[];
  excerpts: string[];
}

export interface StoryWorkbenchVersion {
  id: string;
  version: number;
  source: string;
  cleaned_text: string;
  cleaned_length: number;
  segment_count: number;
  structure_confidence: string;
  quality_score?: number;
  quality_status?: "ready" | "needs_review" | "poor" | string;
  created_at: string;
}

export interface StoryWorkbenchCleanupStats {
  raw_length: number;
  cleaned_length: number;
  removed_characters: number;
  compression_percent: number;
  noise_marker_count: number;
  duplicate_sentence_count: number;
  paragraph_count: number;
  segment_count: number;
  quality_score?: number;
  quality_status?: "ready" | "needs_review" | "poor" | string;
  manual_review_reasons?: string[];
}

export interface StoryWorkbenchCleanupChange {
  text: string;
  reason: string;
}

export interface StoryWorkbenchCleanupChanges {
  removed_noise?: StoryWorkbenchCleanupChange[];
  removed_duplicates?: StoryWorkbenchCleanupChange[];
  paragraph_changes?: string[];
  sentence_break_changes?: string[];
}

export interface StoryWorkbenchItem {
  report_id: string;
  video_id: string;
  video_title: string;
  video_url: string;
  raw_text: string;
  raw_length: number;
  cleaned_text: string;
  cleaned_length: number;
  cleanup_stats?: StoryWorkbenchCleanupStats;
  cleanup_changes?: StoryWorkbenchCleanupChanges;
  segments: StoryWorkbenchSegment[];
  analysis: StoryWorkbenchAnalysis;
  cleaned_versions?: StoryWorkbenchVersion[];
  created_at: string;
  updated_at?: string;
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
