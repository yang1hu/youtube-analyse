import { ChartNoAxesCombined, ListChecks, MessageSquareText, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import {
  analyzeSample,
  fetchSampleAnalyses,
  fetchReportTranscript,
  fetchReports,
  fetchStoryWorkbench,
  queueReportTranslation,
  reanalyzeLatestReport,
  restoreStoryWorkbenchVersion,
  saveStoryWorkbench,
  updateStoryWorkbenchAnalysis,
} from "../api";
import type { CreationPipelineNextAction, Language, SampleAnalysis, StoryWorkbenchAnalysis, StoryWorkbenchItem, TranscriptBundle, VideoReportData } from "../types";

interface VideoReportProps {
  language: Language;
  nextAction?: CreationPipelineNextAction;
  onOpenDashboard?: () => void;
  onRunNextAction?: (action?: CreationPipelineNextAction) => void;
}

function formatReportTime(value: string | undefined, language: Language) {
  if (!value) {
    return "-";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(language === "zh" ? "zh-CN" : "en-US", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit"
  }).format(date);
}

function joinList(items?: string[]) {
  return (items ?? []).join("\n");
}

function splitList(value: string) {
  return value
    .split(/\r?\n/)
    .map(item => item.trim())
    .filter(Boolean);
}

function analysisDraft(analysis?: Partial<StoryWorkbenchAnalysis>) {
  return {
    ending_suspense: analysis?.ending_suspense ?? "",
    first_30s_retention: analysis?.first_30s_retention ?? "",
    first_payoff: analysis?.first_payoff ?? "",
    middle_escalation: analysis?.middle_escalation ?? "",
    non_reusable_content: joinList(analysis?.non_reusable_content),
    opening_5s_hook: analysis?.opening_5s_hook ?? "",
    opposition_design: analysis?.opposition_design ?? "",
    protagonist_position: analysis?.protagonist_position ?? "",
    public_reversal: analysis?.public_reversal ?? "",
    reusable_template: joinList(analysis?.reusable_template),
    status_gap: analysis?.status_gap ?? "",
    structure_confidence: analysis?.structure_confidence ?? "medium"
  };
}

export default function VideoReport({ language, nextAction, onOpenDashboard, onRunNextAction }: VideoReportProps) {
  const [report, setReport] = useState<VideoReportData | null>(null);
  const [reports, setReports] = useState<VideoReportData[]>([]);
  const [selectedReportId, setSelectedReportId] = useState("");
  const [bundle, setBundle] = useState<TranscriptBundle>({ transcript: null, translation: null });
  const [storyWorkbench, setStoryWorkbench] = useState<StoryWorkbenchItem | null>(null);
  const [cleanedDraft, setCleanedDraft] = useState("");
  const [activeTab, setActiveTab] = useState<"analysis" | "story" | "raw" | "translation">("analysis");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isTranslating, setIsTranslating] = useState(false);
  const [isSavingStory, setIsSavingStory] = useState(false);
  const [isSavingStoryAnalysis, setIsSavingStoryAnalysis] = useState(false);
  const [restoringStoryVersionId, setRestoringStoryVersionId] = useState("");
  const [storyAnalysisDraft, setStoryAnalysisDraft] = useState(() => analysisDraft());
  const [translationError, setTranslationError] = useState("");
  const [analysisError, setAnalysisError] = useState("");
  const [storyMessage, setStoryMessage] = useState("");
  const [sampleAnalyses, setSampleAnalyses] = useState<SampleAnalysis[]>([]);
  const [sampleError, setSampleError] = useState("");
  const [isAnalyzingSample, setIsAnalyzingSample] = useState(false);

  useEffect(() => {
    void refreshReport();
    void refreshSamples();
  }, []);

  const refreshReport = async (preferredReportId = selectedReportId) => {
    const nextReports = await fetchReports();
    const nextReport =
      nextReports.find(item => item.id === preferredReportId) ??
      nextReports[0] ??
      null;

    setReports(nextReports);
    setReport(nextReport);
    setSelectedReportId(nextReport?.id ?? "");
    if (nextReport?.id) {
      setBundle(await fetchReportTranscript(nextReport.id));
      const workbench = await fetchStoryWorkbench(nextReport.id);
      setStoryWorkbench(workbench);
      setCleanedDraft(workbench?.cleaned_text ?? "");
      setStoryAnalysisDraft(analysisDraft(workbench?.analysis));
    } else {
      setBundle({ transcript: null, translation: null });
      setStoryWorkbench(null);
      setCleanedDraft("");
      setStoryAnalysisDraft(analysisDraft());
    }
  };

  const refreshSamples = async () => {
    setSampleAnalyses(await fetchSampleAnalyses());
  };

  useEffect(() => {
    if (bundle.translation_status?.status !== "running") {
      return;
    }

    const timer = window.setInterval(() => {
      if (selectedReportId) {
        void fetchReportTranscript(selectedReportId).then(setBundle);
      }
    }, 4000);
    return () => window.clearInterval(timer);
  }, [bundle.translation_status?.status, selectedReportId]);

  const isZh = language === "zh";
  const rawText = bundle.transcript?.raw_text ?? "";
  const translatedText = bundle.translation?.translated_text ?? "";
  const cleanedVersions = storyWorkbench?.cleaned_versions ?? [];
  const cleanupStats = storyWorkbench?.cleanup_stats;
  const cleanupChanges = storyWorkbench?.cleanup_changes;
  const hasCleanupChanges = Boolean(
    cleanupChanges?.removed_noise?.length ||
      cleanupChanges?.removed_duplicates?.length ||
      cleanupChanges?.paragraph_changes?.length ||
      cleanupChanges?.sentence_break_changes?.length
  );
  const cleanupQualityTone =
    cleanupStats?.quality_status === "ready"
      ? "ok"
      : cleanupStats?.quality_status === "poor"
        ? "failed"
        : "warning";
  const cleanupQualityLabel = cleanupStats?.quality_status
    ? isZh
      ? cleanupStats.quality_status === "ready"
        ? "可进入创作转化"
        : cleanupStats.quality_status === "poor"
          ? "需要先修正文案"
          : "建议人工复核"
      : cleanupStats.quality_status === "ready"
        ? "Ready for remix"
        : cleanupStats.quality_status === "poor"
          ? "Fix script first"
        : "Review suggested"
    : "";
  const storyQualityTone = (status?: string) => {
    if (status === "ready") return "ok";
    if (status === "poor") return "failed";
    return "warning";
  };
  const storyQualityLabel = (status?: string) => {
    if (!status) return "-";
    if (isZh) {
      if (status === "ready") return "可用";
      if (status === "poor") return "需修正";
      if (status === "needs_review") return "待复核";
    }
    if (status === "ready") return "Ready";
    if (status === "poor") return "Fix first";
    if (status === "needs_review") return "Review";
    return status;
  };
  const latestReportId = reports[0]?.id ?? "";
  const isLatestReport = Boolean(report?.id && report.id === latestReportId);
  const evidence = report?.collection_evidence ?? {};
  const reportSampleAnalyses = report
    ? sampleAnalyses.filter(sample => {
        const sameUrl = sample.video_url && sample.video_url === report.video_url;
        const sameVideoId = sample.video_id && report.youtube_video_id && sample.video_id === report.youtube_video_id;
        return sameUrl || sameVideoId;
      })
    : sampleAnalyses;

  const renderStoryEvidence = (field: string) => {
    const storyEvidence = storyWorkbench?.analysis?.evidence?.[field];
    const excerpts = storyEvidence?.excerpts?.filter(Boolean) ?? [];
    if (!excerpts.length) {
      return null;
    }
    return (
      <div className="story-evidence">
        <span>
          {isZh ? "原文证据" : "Source Evidence"}
          {storyEvidence?.segment_indexes?.length ? ` #${storyEvidence.segment_indexes.join(", #")}` : ""}
        </span>
        {excerpts.slice(0, 2).map(excerpt => (
          <small key={excerpt}>{excerpt}</small>
        ))}
      </div>
    );
  };

  const selectReport = async (reportId: string) => {
    const selected = reports.find(item => item.id === reportId);
    setSelectedReportId(reportId);
    setReport(selected ?? null);
    setBundle(await fetchReportTranscript(reportId));
    const workbench = await fetchStoryWorkbench(reportId);
    setStoryWorkbench(workbench);
    setCleanedDraft(workbench?.cleaned_text ?? "");
    setStoryAnalysisDraft(analysisDraft(workbench?.analysis));
    setActiveTab("analysis");
    setAnalysisError("");
    setTranslationError("");
    setStoryMessage("");
  };

  const translate = async (force = false) => {
    if (!selectedReportId) {
      return;
    }
    setIsTranslating(true);
    setTranslationError("");
    try {
      await queueReportTranslation(selectedReportId, force);
      setBundle(await fetchReportTranscript(selectedReportId));
      setTranslationError(isZh ? "\u7ffb\u8bd1\u4efb\u52a1\u5df2\u52a0\u5165\u4efb\u52a1\u4e2d\u5fc3\u3002" : "Translation task queued in Task Center.");
      setActiveTab("translation");
    } catch (error) {
      setTranslationError(error instanceof Error ? error.message : "Translation failed.");
    } finally {
      setIsTranslating(false);
    }
  };

  const reanalyze = async () => {
    setIsAnalyzing(true);
    setAnalysisError("");
    try {
      await reanalyzeLatestReport();
      await refreshReport();
      setActiveTab("analysis");
    } catch (error) {
      setAnalysisError(error instanceof Error ? error.message : "Analysis failed.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const analyzeCurrentSample = async () => {
    if (!report?.video_url) {
      return;
    }
    setIsAnalyzingSample(true);
    setSampleError("");
    try {
      const task = await analyzeSample(report.video_url, report.video_title, report.youtube_video_id ?? "");
      setSampleError(
        task.queue_message ||
          (isZh ? "\u6837\u672c\u5206\u6790\u4efb\u52a1\u5df2\u52a0\u5165\u4efb\u52a1\u4e2d\u5fc3\u3002" : "Sample analysis task queued in Task Center.")
      );
    } catch (error) {
      setSampleError(error instanceof Error ? error.message : "Sample analysis failed.");
    } finally {
      setIsAnalyzingSample(false);
    }
  };

  const saveCleanedStory = async () => {
    if (!selectedReportId) {
      return;
    }
    setIsSavingStory(true);
    setStoryMessage("");
    try {
      const next = await saveStoryWorkbench(selectedReportId, cleanedDraft);
      setStoryWorkbench(next);
      setCleanedDraft(next.cleaned_text);
      setStoryAnalysisDraft(analysisDraft(next.analysis));
      setStoryMessage(isZh ? "清洗文案已保存，结构分析已更新。" : "Cleaned script saved and story analysis refreshed.");
    } catch (error) {
      setStoryMessage(error instanceof Error ? error.message : "Story workbench save failed.");
    } finally {
      setIsSavingStory(false);
    }
  };

  const restoreCleanedVersion = async (versionId: string) => {
    if (!selectedReportId) {
      return;
    }
    setRestoringStoryVersionId(versionId);
    setStoryMessage("");
    try {
      const next = await restoreStoryWorkbenchVersion(selectedReportId, versionId);
      setStoryWorkbench(next);
      setCleanedDraft(next.cleaned_text);
      setStoryAnalysisDraft(analysisDraft(next.analysis));
      setStoryMessage(isZh ? "已恢复历史清洗版本，并重新生成结构分析。" : "Cleaned version restored and story analysis refreshed.");
    } catch (error) {
      setStoryMessage(error instanceof Error ? error.message : "Story workbench restore failed.");
    } finally {
      setRestoringStoryVersionId("");
    }
  };

  const updateStoryAnalysisDraft = (patch: Partial<ReturnType<typeof analysisDraft>>) => {
    setStoryAnalysisDraft(current => ({ ...current, ...patch }));
  };

  const saveStoryAnalysis = async () => {
    if (!selectedReportId) {
      return;
    }
    setIsSavingStoryAnalysis(true);
    setStoryMessage("");
    try {
      const next = await updateStoryWorkbenchAnalysis(selectedReportId, {
        ending_suspense: storyAnalysisDraft.ending_suspense,
        first_30s_retention: storyAnalysisDraft.first_30s_retention,
        first_payoff: storyAnalysisDraft.first_payoff,
        middle_escalation: storyAnalysisDraft.middle_escalation,
        non_reusable_content: splitList(storyAnalysisDraft.non_reusable_content),
        opening_5s_hook: storyAnalysisDraft.opening_5s_hook,
        opposition_design: storyAnalysisDraft.opposition_design,
        protagonist_position: storyAnalysisDraft.protagonist_position,
        public_reversal: storyAnalysisDraft.public_reversal,
        reusable_template: splitList(storyAnalysisDraft.reusable_template),
        status_gap: storyAnalysisDraft.status_gap,
        structure_confidence: storyAnalysisDraft.structure_confidence
      });
      setStoryWorkbench(next);
      setStoryAnalysisDraft(analysisDraft(next.analysis));
      setStoryMessage(isZh ? "结构拆解已保存，后续创作包会优先使用这版人工结构。" : "Story structure saved; future creation briefs will use this edited structure first.");
    } catch (error) {
      setStoryMessage(error instanceof Error ? error.message : "Story structure save failed.");
    } finally {
      setIsSavingStoryAnalysis(false);
    }
  };

  return (
    <main className="app-shell workspace-page">
      <section className="page-intro" aria-labelledby="video-report-title">
        <p className="eyebrow">{isZh ? "\u89c6\u9891\u5de5\u4f5c\u53f0" : "Video workbench"}</p>
        <h1 id="video-report-title">{isZh ? "\u89c6\u9891\u62a5\u544a" : "Video Report"}</h1>
        <p className="hero-summary">
          {isZh
            ? "\u8fd9\u91cc\u663e\u793a\u89c6\u9891\u5206\u6790\u62a5\u544a\uff0c\u53ef\u4ee5\u5207\u6362\u5386\u53f2\u7248\u672c\u3002"
            : "View video analysis reports and switch between historical versions."}
        </p>
        <div className="hero-actions report-actions">
          <button className="secondary-action compact-action" disabled={isAnalyzing} onClick={() => void refreshReport()} type="button">
            {isZh ? "\u5237\u65b0" : "Refresh"}
          </button>
          <button className="primary-action compact-action" disabled={isAnalyzing || !report || !isLatestReport} onClick={() => void reanalyze()} type="button">
            {isAnalyzing ? (isZh ? "\u5206\u6790\u4e2d..." : "Analyzing...") : isZh ? "\u91cd\u65b0 LLM \u5206\u6790" : "Reanalyze with LLM"}
          </button>
          <button className="secondary-action compact-action" disabled={isAnalyzingSample || !report} onClick={() => void analyzeCurrentSample()} type="button">
            {isAnalyzingSample ? (isZh ? "\u6837\u672c\u5206\u6790\u4e2d..." : "Sampling...") : isZh ? "\u524d 5 \u5206\u949f\u6837\u672c\u5206\u6790" : "Analyze First 5 Min"}
          </button>
        </div>
        {analysisError && <p className="form-message form-message-error">{analysisError}</p>}
        {sampleError && <p className="form-message form-message-error">{sampleError}</p>}
      </section>

      {report ? (
        <section className="report-layout" aria-label="Report">
          <div className="report-sidebar">
            <article className="panel report-summary">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">{report.channel_title || "Channel"}</p>
                  <h2>{report.video_title}</h2>
                </div>
                <ChartNoAxesCombined aria-hidden="true" size={22} />
              </div>
              <p className="panel-note">{report.summary}</p>
              <div className="score-strip" aria-label="Report scores">
                <span>{isZh ? "\u6210\u957f" : "Growth"} {report.growth_judgement.score}</span>
                <span>{report.creative_breakdown.topic_type}</span>
                <span>
                  {isZh ? "\u5206\u6790\u6765\u6e90" : "Analysis"}:{" "}
                  {report.collection_evidence?.analysis_source === "llm"
                    ? "LLM"
                    : report.collection_evidence?.analysis_source || (isZh ? "\u672a\u77e5" : "unknown")}
                </span>
              </div>
              {report.collection_evidence?.analysis_status === "failed" && (
                <p className="form-message-error">
                  {isZh ? "\u4e0a\u6b21 LLM \u5206\u6790\u5931\u8d25\uff0c\u5df2\u56de\u9000\u5230\u89c4\u5219\u5206\u6790\uff1a" : "LLM analysis failed and fell back to rules: "}
                  {report.collection_evidence.analysis_error}
                </p>
              )}
            </article>

            <article className="panel report-history">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">{isZh ? "\u5386\u53f2" : "History"}</p>
                  <h2>{isZh ? "\u5206\u6790\u7248\u672c" : "Report Versions"}</h2>
                </div>
                <ListChecks aria-hidden="true" size={22} />
              </div>
              <div className="report-history-list">
                {reports.map(item => (
                  <button
                    className={item.id === selectedReportId ? "report-history-item report-history-item-active" : "report-history-item"}
                    key={item.id}
                    onClick={() => void selectReport(item.id)}
                    type="button"
                  >
                    <span>{item.video_title}</span>
                    <small>
                      {formatReportTime(item.created_at, language)} ·{" "}
                      {item.collection_evidence?.analysis_source === "llm" ? "LLM" : item.collection_evidence?.analysis_source || "rule"}
                    </small>
                  </button>
                ))}
              </div>
            </article>
          </div>

          <div className="report-section-list">
            <article className="panel report-section trust-section">
              <div className="section-icon">
                <ListChecks aria-hidden="true" size={20} />
              </div>
              <div>
                <p className="eyebrow">{isZh ? "\u6570\u636e\u6765\u6e90\u8bf4\u660e" : "Data provenance"}</p>
                <h2>{isZh ? "\u5206\u6790\u53ef\u4fe1\u5ea6" : "Analysis Trust"}</h2>
                <dl className="trust-fields">
                  <div>
                    <dt>{isZh ? "\u5b57\u5e55" : "Transcript"}</dt>
                    <dd>
                      {evidence.transcript_status ?? "missing"} · {evidence.transcript_language || "-"} ·{" "}
                      {evidence.transcript_length ?? bundle.transcript?.raw_length ?? 0} chars
                    </dd>
                  </div>
                  <div>
                    <dt>{isZh ? "\u81ea\u52a8\u5b57\u5e55" : "Auto captions"}</dt>
                    <dd>{evidence.is_auto_caption ? (isZh ? "\u662f" : "Yes") : (isZh ? "\u5426/\u672a\u77e5" : "No/unknown")}</dd>
                  </div>
                  <div>
                    <dt>{isZh ? "\u753b\u9762\u5e27" : "Frames"}</dt>
                    <dd>
                      {evidence.frame_status ?? "missing"} · {evidence.frame_count ?? 0}
                    </dd>
                  </div>
                  <div>
                    <dt>LLM</dt>
                    <dd>
                      {evidence.llm_participated ? (isZh ? "\u5df2\u53c2\u4e0e" : "Used") : (isZh ? "\u672a\u5b8c\u6210" : "Not completed")} ·{" "}
                      {evidence.used_rule_fallback ? (isZh ? "\u5df2\u89c4\u5219\u515c\u5e95" : "Rule fallback") : (isZh ? "\u65e0\u515c\u5e95" : "No fallback")}
                    </dd>
                  </div>
                </dl>
              </div>
            </article>

            <article className="panel report-section">
              <div className="section-icon">
                <Sparkles aria-hidden="true" size={20} />
              </div>
              <div>
                <p className="eyebrow">{isZh ? "\u5f00\u573a\u7559\u5b58" : "Opening retention"}</p>
                <h2>{isZh ? "\u5f00\u573a\u94a9\u5b50" : "Opening Hook"}</h2>
                <p>{report.creative_breakdown.opening_hook}</p>
              </div>
            </article>

            <article className="panel report-section">
              <div className="section-icon">
                <ListChecks aria-hidden="true" size={20} />
              </div>
              <div>
                <p className="eyebrow">{isZh ? "\u6807\u9898\u70b9\u51fb" : "Title click"}</p>
                <h2>{isZh ? "\u6807\u9898\u94a9\u5b50" : "Title Hook"}</h2>
                <p>{report.creative_breakdown.title_hook}</p>
              </div>
            </article>

            <article className="panel report-section">
              <div className="section-icon">
                <ChartNoAxesCombined aria-hidden="true" size={20} />
              </div>
              <div>
                <p className="eyebrow">{isZh ? "\u589e\u957f\u5224\u65ad" : "Growth judgement"}</p>
                <h2>{report.growth_judgement.score}/100</h2>
                <ul className="compact-list">
                  {report.growth_judgement.reasons.map(item => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </article>

            <article className="panel report-section">
              <div className="section-icon">
                <MessageSquareText aria-hidden="true" size={20} />
              </div>
              <div>
                <p className="eyebrow">{isZh ? "\u8bc4\u8bba" : "Comments"}</p>
                <h2>{report.comment_insights.status}</h2>
                <p>{isZh ? "\u8bc4\u8bba\u91c7\u96c6\u4ecd\u4e3a\u9884\u7559\u529f\u80fd\u3002" : "Comment collection remains reserved."}</p>
              </div>
            </article>
          </div>

          <article className="panel transcript-panel">
            <div className="transcript-tabs" role="tablist" aria-label={isZh ? "\u62a5\u544a\u5185\u5bb9" : "Report content"}>
              <button
                aria-selected={activeTab === "analysis"}
                className={activeTab === "analysis" ? "tab-button tab-button-active" : "tab-button"}
                onClick={() => setActiveTab("analysis")}
                type="button"
              >
                {isZh ? "\u5206\u6790" : "Analysis"}
              </button>
              <button
                aria-selected={activeTab === "story"}
                className={activeTab === "story" ? "tab-button tab-button-active" : "tab-button"}
                onClick={() => setActiveTab("story")}
                type="button"
              >
                {isZh ? "故事工坊" : "Story Workbench"}
              </button>
              <button
                aria-selected={activeTab === "raw"}
                className={activeTab === "raw" ? "tab-button tab-button-active" : "tab-button"}
                onClick={() => setActiveTab("raw")}
                type="button"
              >
                {isZh ? "\u539f\u59cb\u811a\u672c" : "Raw Script"}
              </button>
              <button
                aria-selected={activeTab === "translation"}
                className={activeTab === "translation" ? "tab-button tab-button-active" : "tab-button"}
                onClick={() => setActiveTab("translation")}
                type="button"
              >
                {isZh ? "\u4e2d\u6587\u7ffb\u8bd1" : "Chinese Translation"}
              </button>
            </div>

            {activeTab === "analysis" && (
              <div className="transcript-content">
                <p className="eyebrow">{isZh ? "\u8be6\u7ec6\u62c6\u89e3" : "Detailed breakdown"}</p>
                <h2>{report.creative_breakdown.topic_type}</h2>
                <h3>{isZh ? "\u5185\u5bb9\u8282\u62cd" : "Content Beats"}</h3>
                <ul className="report-list">
                  {report.creative_breakdown.structure.map(item => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
                <h3>{isZh ? "\u60c5\u7eea\u66f2\u7ebf" : "Emotional Curve"}</h3>
                <ul className="report-list">
                  {report.creative_breakdown.emotional_curve.map(item => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
                <h3>{isZh ? "\u53ef\u590d\u7528\u9009\u9898" : "Reusable Ideas"}</h3>
                <ul className="report-list">
                  {(report.idea_cards ?? []).map(item => (
                    <li key={item.title}>
                      <strong>{item.title}</strong>
                      <span>{item.why_it_works}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {activeTab === "story" && (
              <div className="transcript-content story-workbench">
                <div className="story-workbench-header">
                  <div>
                    <p className="eyebrow">{isZh ? "短片小说结构" : "Short fiction structure"}</p>
                    <h2>{isZh ? "原文清洗与故事拆解" : "Cleaned Script & Story Breakdown"}</h2>
                  </div>
                  <div className="hero-actions report-actions">
                    <button className="primary-action compact-action" disabled={isSavingStory || !report} onClick={() => void saveCleanedStory()} type="button">
                      {isSavingStory ? (isZh ? "保存中..." : "Saving...") : isZh ? "保存并重新分析" : "Save & Reanalyze"}
                    </button>
                  </div>
                </div>
                {storyMessage && <p className="form-message form-message-idle">{storyMessage}</p>}
                {cleanupStats && (
                  <div className="story-cleanup-stats" aria-label={isZh ? "清洗统计" : "Cleanup stats"}>
                    {typeof cleanupStats.quality_score === "number" && (
                      <span className={`story-quality-pill story-quality-${cleanupQualityTone}`}>
                        {isZh ? "质量" : "Quality"} {cleanupStats.quality_score}/100 · {cleanupQualityLabel}
                      </span>
                    )}
                    <span>{isZh ? "原文" : "Raw"} {cleanupStats.raw_length}</span>
                    <span>{isZh ? "清洗稿" : "Cleaned"} {cleanupStats.cleaned_length}</span>
                    <span>{isZh ? "压缩" : "Trimmed"} {cleanupStats.compression_percent}%</span>
                    <span>{isZh ? "噪声" : "Noise"} {cleanupStats.noise_marker_count}</span>
                    <span>{isZh ? "重复句" : "Duplicates"} {cleanupStats.duplicate_sentence_count}</span>
                    <span>{isZh ? "段落" : "Paragraphs"} {cleanupStats.paragraph_count}</span>
                  </div>
                )}
                {hasCleanupChanges && cleanupChanges && (
                  <article className="story-cleanup-diff">
                    <div className="story-panel-heading">
                      <h3>{isZh ? "清洗差异" : "Cleanup Changes"}</h3>
                      <span className="status-pill status-pill-muted">
                        {(cleanupChanges.removed_noise?.length ?? 0) + (cleanupChanges.removed_duplicates?.length ?? 0)}
                      </span>
                    </div>
                    {!!cleanupChanges.removed_noise?.length && (
                      <div>
                        <strong>{isZh ? "移除字幕噪声" : "Removed Noise"}</strong>
                        <ul className="compact-list">
                          {cleanupChanges.removed_noise.map((item, index) => (
                            <li key={`${item.text}-${index}`}>{item.text}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {!!cleanupChanges.removed_duplicates?.length && (
                      <div>
                        <strong>{isZh ? "移除重复句" : "Removed Duplicates"}</strong>
                        <ul className="compact-list">
                          {cleanupChanges.removed_duplicates.map((item, index) => (
                            <li key={`${item.text}-${index}`}>{item.text}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {!!cleanupChanges.paragraph_changes?.length && (
                      <div>
                        <strong>{isZh ? "段落整理" : "Paragraphs"}</strong>
                        <ul className="compact-list">
                          {cleanupChanges.paragraph_changes.map(item => (
                            <li key={item}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {!!cleanupChanges.sentence_break_changes?.length && (
                      <div>
                        <strong>{isZh ? "断句说明" : "Sentence Breaks"}</strong>
                        <ul className="compact-list">
                          {cleanupChanges.sentence_break_changes.map(item => (
                            <li key={item}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </article>
                )}
                {!!cleanupStats?.manual_review_reasons?.length && (
                  <article className="story-quality-review">
                    <h3>{isZh ? "人工复核提示" : "Manual Review Notes"}</h3>
                    <ul className="compact-list">
                      {cleanupStats.manual_review_reasons.map(reason => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                  </article>
                )}
                <div className="story-compare-grid">
                  <article className="story-raw-panel">
                    <div className="story-panel-heading">
                      <h3>{isZh ? "原始字幕" : "Raw Transcript"}</h3>
                      <span className="status-pill status-pill-muted">{storyWorkbench?.raw_length ?? rawText.length}</span>
                    </div>
                    {storyWorkbench?.raw_text || rawText ? (
                      <pre className="script-box story-raw-box">{storyWorkbench?.raw_text || rawText}</pre>
                    ) : (
                      <p className="panel-note">{isZh ? "暂无原始字幕。" : "No raw transcript is available."}</p>
                    )}
                  </article>
                  <label className="field-group story-editor-field">
                    <span>{isZh ? "清洗文案" : "Cleaned Script"}</span>
                    <textarea
                      className="inline-textarea story-cleaned-editor"
                      onChange={event => setCleanedDraft(event.target.value)}
                      placeholder={isZh ? "暂无清洗文案。请先完成视频分析或粘贴文案后保存。" : "No cleaned script yet. Analyze the video or paste script here, then save."}
                      value={cleanedDraft}
                    />
                    <small>
                      {isZh
                        ? `${storyWorkbench?.cleaned_length ?? cleanedDraft.length} 字符；后续创作转化和结构分析优先使用这份清洗稿。`
                        : `${storyWorkbench?.cleaned_length ?? cleanedDraft.length} chars; story remix and analysis use this cleaned draft first.`}
                    </small>
                  </label>
                </div>
                <div className="story-editor-grid">
                  <article className="story-segment-panel">
                    <h3>{isZh ? "段落标签" : "Segment Labels"}</h3>
                    {storyWorkbench?.segments.length ? (
                      <div className="story-segment-list">
                        {storyWorkbench.segments.map(segment => (
                          <div className="story-segment-item" key={`${segment.index}-${segment.label_key}`}>
                            <span className="status-pill status-pill-muted">{segment.label}</span>
                            <p>{segment.text}</p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="panel-note">{isZh ? "保存清洗文案后会自动生成段落标签。" : "Save a cleaned script to generate segment labels."}</p>
                    )}
                  </article>
                </div>

                {cleanedVersions.length > 0 && (
                  <article className="story-version-panel">
                    <div className="panel-heading">
                      <div>
                        <p className="eyebrow">{isZh ? "清洗版本" : "Cleaned Versions"}</p>
                        <h3>{isZh ? "最近保存的文案" : "Recently Saved Scripts"}</h3>
                      </div>
                      <span className="status-pill status-pill-muted">{cleanedVersions.length}</span>
                    </div>
                    <div className="story-version-list">
                      {cleanedVersions.map(version => (
                        <article className="story-version-item" key={version.id}>
                          <div>
                            <strong>v{version.version}</strong>
                            <span>
                              {version.cleaned_length} {isZh ? "字符" : "chars"} · {version.segment_count} {isZh ? "段" : "segments"} ·{" "}
                              {version.structure_confidence || "-"}
                            </span>
                            {typeof version.quality_score === "number" && (
                              <span className={`story-version-quality story-quality-${storyQualityTone(version.quality_status)}`}>
                                {isZh ? "质量" : "Quality"} {version.quality_score}/100 · {storyQualityLabel(version.quality_status)}
                              </span>
                            )}
                            <small>
                              {formatReportTime(version.created_at, language)}
                              {version.source ? ` · ${version.source}` : ""}
                            </small>
                          </div>
                          <div className="story-version-actions">
                            <button className="secondary-action compact-action" onClick={() => setCleanedDraft(version.cleaned_text)} type="button">
                              {isZh ? "载入编辑" : "Load"}
                            </button>
                            <button
                              className="primary-action compact-action"
                              disabled={restoringStoryVersionId === version.id}
                              onClick={() => void restoreCleanedVersion(version.id)}
                              type="button"
                            >
                              {restoringStoryVersionId === version.id ? (isZh ? "恢复中..." : "Restoring...") : isZh ? "恢复此版" : "Restore"}
                            </button>
                          </div>
                        </article>
                      ))}
                    </div>
                  </article>
                )}

                {storyWorkbench?.analysis && (
                  <>
                    <article className="story-analysis-editor">
                      <div className="panel-heading">
                        <div>
                          <p className="eyebrow">{isZh ? "人工结构" : "Manual Structure"}</p>
                          <h3>{isZh ? "编辑可复用机制与避抄边界" : "Edit Reusable Mechanics and Boundaries"}</h3>
                        </div>
                        <button className="primary-action compact-action" disabled={isSavingStoryAnalysis} onClick={() => void saveStoryAnalysis()} type="button">
                          {isSavingStoryAnalysis ? (isZh ? "保存中..." : "Saving...") : isZh ? "保存结构" : "Save Structure"}
                        </button>
                      </div>
                      <div className="story-analysis-editor-grid">
                        <label className="field-group">
                          <span>{isZh ? "5 秒钩子" : "5s Hook"}</span>
                          <input className="inline-input" onChange={event => updateStoryAnalysisDraft({ opening_5s_hook: event.target.value })} value={storyAnalysisDraft.opening_5s_hook} />
                        </label>
                        <label className="field-group">
                          <span>{isZh ? "前 30 秒留存" : "First 30s Retention"}</span>
                          <input className="inline-input" onChange={event => updateStoryAnalysisDraft({ first_30s_retention: event.target.value })} value={storyAnalysisDraft.first_30s_retention} />
                        </label>
                        <label className="field-group">
                          <span>{isZh ? "主角初始处境" : "Protagonist Position"}</span>
                          <input className="inline-input" onChange={event => updateStoryAnalysisDraft({ protagonist_position: event.target.value })} value={storyAnalysisDraft.protagonist_position} />
                        </label>
                        <label className="field-group">
                          <span>{isZh ? "身份/信息/能力差" : "Status / Info / Ability Gap"}</span>
                          <input className="inline-input" onChange={event => updateStoryAnalysisDraft({ status_gap: event.target.value })} value={storyAnalysisDraft.status_gap} />
                        </label>
                        <label className="field-group">
                          <span>{isZh ? "第一次爽点" : "First Payoff"}</span>
                          <input className="inline-input" onChange={event => updateStoryAnalysisDraft({ first_payoff: event.target.value })} value={storyAnalysisDraft.first_payoff} />
                        </label>
                        <label className="field-group">
                          <span>{isZh ? "中段升级" : "Middle Escalation"}</span>
                          <input className="inline-input" onChange={event => updateStoryAnalysisDraft({ middle_escalation: event.target.value })} value={storyAnalysisDraft.middle_escalation} />
                        </label>
                        <label className="field-group">
                          <span>{isZh ? "反派/阻力" : "Opposition"}</span>
                          <input className="inline-input" onChange={event => updateStoryAnalysisDraft({ opposition_design: event.target.value })} value={storyAnalysisDraft.opposition_design} />
                        </label>
                        <label className="field-group">
                          <span>{isZh ? "公开反转" : "Public Reversal"}</span>
                          <input className="inline-input" onChange={event => updateStoryAnalysisDraft({ public_reversal: event.target.value })} value={storyAnalysisDraft.public_reversal} />
                        </label>
                        <label className="field-group">
                          <span>{isZh ? "结尾悬念" : "Ending Suspense"}</span>
                          <input className="inline-input" onChange={event => updateStoryAnalysisDraft({ ending_suspense: event.target.value })} value={storyAnalysisDraft.ending_suspense} />
                        </label>
                        <label className="field-group">
                          <span>{isZh ? "结构置信度" : "Structure Confidence"}</span>
                          <select className="inline-input" onChange={event => updateStoryAnalysisDraft({ structure_confidence: event.target.value })} value={storyAnalysisDraft.structure_confidence}>
                            <option value="low">{isZh ? "低" : "Low"}</option>
                            <option value="medium">{isZh ? "中" : "Medium"}</option>
                            <option value="high">{isZh ? "高" : "High"}</option>
                          </select>
                        </label>
                        <label className="field-group story-analysis-editor-wide">
                          <span>{isZh ? "可复用结构模板（每行一条）" : "Reusable Template (one per line)"}</span>
                          <textarea className="inline-textarea" onChange={event => updateStoryAnalysisDraft({ reusable_template: event.target.value })} value={storyAnalysisDraft.reusable_template} />
                        </label>
                        <label className="field-group story-analysis-editor-wide">
                          <span>{isZh ? "不可复用内容/避抄边界（每行一条）" : "Do Not Reuse / Boundaries (one per line)"}</span>
                          <textarea className="inline-textarea" onChange={event => updateStoryAnalysisDraft({ non_reusable_content: event.target.value })} value={storyAnalysisDraft.non_reusable_content} />
                        </label>
                      </div>
                    </article>

                    <div className="story-analysis-grid">
                      <article>
                        <p className="eyebrow">{isZh ? "开场" : "Opening"}</p>
                        <h3>{isZh ? "5 秒钩子" : "5s Hook"}</h3>
                        <p>{storyWorkbench.analysis.opening_5s_hook || "-"}</p>
                        {renderStoryEvidence("opening_5s_hook")}
                      </article>
                      <article>
                        <p className="eyebrow">{isZh ? "留存" : "Retention"}</p>
                        <h3>{isZh ? "前 30 秒" : "First 30s"}</h3>
                        <p>{storyWorkbench.analysis.first_30s_retention || "-"}</p>
                        {renderStoryEvidence("first_30s_retention")}
                      </article>
                      <article>
                        <p className="eyebrow">{isZh ? "主角" : "Protagonist"}</p>
                        <h3>{isZh ? "初始处境" : "Initial Position"}</h3>
                        <p>{storyWorkbench.analysis.protagonist_position || "-"}</p>
                        {renderStoryEvidence("protagonist_position")}
                      </article>
                      <article>
                        <p className="eyebrow">{isZh ? "信息差" : "Gap"}</p>
                        <h3>{isZh ? "身份/信息/能力差" : "Status / Info / Ability Gap"}</h3>
                        <p>{storyWorkbench.analysis.status_gap || "-"}</p>
                        {renderStoryEvidence("status_gap")}
                      </article>
                      <article>
                        <p className="eyebrow">{isZh ? "爽点" : "Payoff"}</p>
                        <h3>{isZh ? "第一次兑现" : "First Payoff"}</h3>
                        <p>{storyWorkbench.analysis.first_payoff || "-"}</p>
                        {renderStoryEvidence("first_payoff")}
                      </article>
                      <article>
                        <p className="eyebrow">{isZh ? "升级" : "Escalation"}</p>
                        <h3>{isZh ? "中段升级" : "Middle Escalation"}</h3>
                        <p>{storyWorkbench.analysis.middle_escalation || "-"}</p>
                        {renderStoryEvidence("middle_escalation")}
                      </article>
                      <article>
                        <p className="eyebrow">{isZh ? "阻力" : "Opposition"}</p>
                        <h3>{isZh ? "反派/压力设计" : "Opposition Design"}</h3>
                        <p>{storyWorkbench.analysis.opposition_design || "-"}</p>
                        {renderStoryEvidence("opposition_design")}
                      </article>
                      <article>
                        <p className="eyebrow">{isZh ? "结尾" : "Ending"}</p>
                        <h3>{isZh ? "悬念" : "Suspense"}</h3>
                        <p>{storyWorkbench.analysis.ending_suspense || "-"}</p>
                        {renderStoryEvidence("ending_suspense")}
                      </article>
                    </div>

                    <div className="story-list-grid">
                      <article>
                        <h3>{isZh ? "可复用结构模板" : "Reusable Template"}</h3>
                        <ul className="compact-list">
                          {storyWorkbench.analysis.reusable_template.map(item => (
                            <li key={item}>{item}</li>
                          ))}
                        </ul>
                      </article>
                      <article>
                        <h3>{isZh ? "不可复用内容清单" : "Do Not Reuse"}</h3>
                        <ul className="compact-list">
                          {storyWorkbench.analysis.non_reusable_content.map(item => (
                            <li key={item}>{item}</li>
                          ))}
                        </ul>
                      </article>
                    </div>
                  </>
                )}
              </div>
            )}

            {activeTab === "raw" && (
              <div className="transcript-content">
                <div className="transcript-meta">
                  <span>{bundle.transcript?.transcript_source ?? "-"}</span>
                  <span>{bundle.transcript?.language ?? "-"}</span>
                  <span>{bundle.transcript?.raw_length ?? 0} chars</span>
                </div>
                {rawText ? (
                  <pre className="script-box">{rawText}</pre>
                ) : (
                  <p className="panel-note">
                    {isZh ? "\u5c1a\u672a\u4fdd\u5b58\u539f\u59cb\u811a\u672c\uff0c\u8bf7\u91cd\u65b0\u5206\u6790\u8fd9\u6761\u89c6\u9891\u3002" : "No raw script has been saved yet. Analyze this video again."}
                  </p>
                )}
              </div>
            )}

            {activeTab === "translation" && (
              <div className="transcript-content">
                <div className="translation-actions">
                  <div>
                    <p className="eyebrow">OpenAI</p>
                    <h2>{bundle.translation?.model ?? (isZh ? "\u5c1a\u672a\u7ffb\u8bd1" : "Not translated yet")}</h2>
                  </div>
                  <button className="primary-action compact-action" disabled={isTranslating || !rawText} onClick={() => void translate(false)} type="button">
                    {isTranslating ? (isZh ? "\u7ffb\u8bd1\u4e2d..." : "Translating...") : isZh ? "\u7ffb\u8bd1\u6210\u4e2d\u6587" : "Translate to Chinese"}
                  </button>
                  <button className="secondary-action compact-action" disabled={isTranslating || !rawText} onClick={() => void translate(true)} type="button">
                    {isZh ? "\u5f3a\u5236\u91cd\u65b0\u7ffb\u8bd1" : "Force Retranslate"}
                  </button>
                </div>
                {bundle.translation_status?.status === "running" && (
                  <p className="form-message-saving">
                    {isZh
                      ? `\u7ffb\u8bd1\u8fdb\u884c\u4e2d\uff1a${bundle.translation_status.completed_chunks ?? 0}/${bundle.translation_status.total_chunks ?? 0}`
                      : `Translation running: ${bundle.translation_status.completed_chunks ?? 0}/${bundle.translation_status.total_chunks ?? 0}`}
                  </p>
                )}
                {bundle.translation_status?.status === "failed" && (
                  <p className="form-message-error">{bundle.translation_status.error_message}</p>
                )}
                {translationError && <p className="form-message-error">{translationError}</p>}
                {translatedText ? (
                  <pre className="script-box">{translatedText}</pre>
                ) : (
                  <p className="panel-note">
                    {isZh ? "\u70b9\u51fb\u6309\u94ae\u540e\u4f1a\u4f7f\u7528 OpenAI \u7ffb\u8bd1\u5e76\u7f13\u5b58\u7ed3\u679c\u3002" : "Click the button to translate with OpenAI and cache the result."}
                  </p>
                )}
              </div>
            )}
          </article>

          <article className="panel transcript-panel sample-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">{isZh ? "\u7206\u6b3e\u6837\u672c" : "Viral samples"}</p>
                <h2>{isZh ? "\u524d 5 \u5206\u949f\u6df1\u5ea6\u5206\u6790" : "First 5 Minute Analysis"}</h2>
              </div>
            </div>
            {reportSampleAnalyses.length ? (
              <div className="sample-list">
                {reportSampleAnalyses.map(sample => (
                  <div className="sample-card" key={sample.id}>
                    <div className="sample-card-header">
                      <div>
                        <h3>{sample.video_title}</h3>
                        <p>
                          {sample.analyzed_seconds}s · {sample.opening_transcript_length ?? 0} {isZh ? "\u5b57\u7b26\u811a\u672c" : "script chars"}
                        </p>
                      </div>
                      <span className="status-pill">{sample.status}</span>
                    </div>
                    <p className="panel-note">{sample.visual_summary}</p>
                    <dl className="sample-fields">
                      <div>
                        <dt>{isZh ? "\u5f00\u573a\u94a9\u5b50" : "Opening"}</dt>
                        <dd>{sample.opening_hook}</dd>
                      </div>
                      <div>
                        <dt>{isZh ? "\u6545\u4e8b\u8bbe\u5b9a" : "Story Setup"}</dt>
                        <dd>{sample.story_setup || "-"}</dd>
                      </div>
                      <div>
                        <dt>{isZh ? "\u7b2c\u4e00\u51b2\u7a81" : "First Conflict"}</dt>
                        <dd>{sample.first_conflict || "-"}</dd>
                      </div>
                      <div>
                        <dt>{isZh ? "\u7b2c\u4e00\u8f6c\u6298" : "First Turn"}</dt>
                        <dd>{sample.first_turning_point || "-"}</dd>
                      </div>
                      <div>
                        <dt>{isZh ? "\u8282\u594f" : "Pacing"}</dt>
                        <dd>{sample.pacing_notes.join(" / ")}</dd>
                      </div>
                      <div>
                        <dt>{isZh ? "\u590d\u7528\u6a21\u677f" : "Template"}</dt>
                        <dd>{sample.reuse_template.join(" / ")}</dd>
                      </div>
                      <div>
                        <dt>{isZh ? "\u907f\u6284" : "Avoid"}</dt>
                        <dd>{sample.risk_notes.join(" / ")}</dd>
                      </div>
                    </dl>
                  </div>
                ))}
              </div>
            ) : (
              <p className="panel-note">
                {isZh
                  ? "\u5f53\u524d\u89c6\u9891\u8fd8\u6ca1\u6709\u524d 5 \u5206\u949f\u6837\u672c\u5206\u6790\u3002\u4ece\u4eea\u8868\u76d8\u6216\u672c\u9875\u624b\u52a8\u89e6\u53d1\u540e\uff0c\u7cfb\u7edf\u4f1a\u53ea\u5904\u7406\u8fd9\u6761\u89c6\u9891\u7684\u524d 5 \u5206\u949f\u3002"
                  : "No first-five-minute sample analysis exists for the selected video yet. Trigger it from the dashboard or this page; the system only processes this video's first 5 minutes."}
              </p>
            )}
          </article>
        </section>
      ) : (
        <>
          <article className="panel action-empty-state">
            <div>
              <p className="eyebrow">{isZh ? "下一步" : "Next step"}</p>
              <h2>{nextAction?.label || (isZh ? "先分析一条视频" : "Analyze a video first")}</h2>
              <p className="panel-note">
                {nextAction?.description ||
                  (isZh
                    ? "还没有分析报告。回到仪表盘同步频道或选择候选视频，完成分析后再进入清洗文案和结构拆解。"
                    : "No report yet. Go back to the dashboard to sync a channel or analyze a candidate video, then return here for script cleanup and structure work.")}
              </p>
            </div>
            <button className="primary-action compact-action" onClick={() => onRunNextAction?.(nextAction) ?? onOpenDashboard?.()} type="button">
              {nextAction?.target_view === "settings"
                ? isZh
                  ? "去配置频道"
                  : "Open Settings"
                : nextAction?.action_type === "sync_channel"
                  ? isZh
                    ? "去同步频道"
                    : "Sync Channel"
                  : isZh
                    ? "去仪表盘分析视频"
                    : "Open Dashboard"}
            </button>
          </article>
          <article className="panel transcript-panel sample-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">{isZh ? "\u7206\u6b3e\u6837\u672c" : "Viral samples"}</p>
                <h2>{isZh ? "\u524d 5 \u5206\u949f\u6df1\u5ea6\u5206\u6790" : "First 5 Minute Analysis"}</h2>
              </div>
            </div>
            {sampleAnalyses.length ? (
              <div className="sample-list">
                {sampleAnalyses.map(sample => (
                  <div className="sample-card" key={sample.id}>
                    <div className="sample-card-header">
                      <div>
                        <h3>{sample.video_title}</h3>
                        <p>
                          {sample.analyzed_seconds}s · {sample.opening_transcript_length ?? 0} {isZh ? "\u5b57\u7b26\u811a\u672c" : "script chars"}
                        </p>
                      </div>
                      <span className="status-pill">{sample.status}</span>
                    </div>
                    <p className="panel-note">{sample.visual_summary}</p>
                    <dl className="sample-fields">
                      <div>
                        <dt>{isZh ? "\u5f00\u573a\u94a9\u5b50" : "Opening"}</dt>
                        <dd>{sample.opening_hook}</dd>
                      </div>
                      <div>
                        <dt>{isZh ? "\u6545\u4e8b\u8bbe\u5b9a" : "Story Setup"}</dt>
                        <dd>{sample.story_setup || "-"}</dd>
                      </div>
                      <div>
                        <dt>{isZh ? "\u7b2c\u4e00\u51b2\u7a81" : "First Conflict"}</dt>
                        <dd>{sample.first_conflict || "-"}</dd>
                      </div>
                      <div>
                        <dt>{isZh ? "\u7b2c\u4e00\u8f6c\u6298" : "First Turn"}</dt>
                        <dd>{sample.first_turning_point || "-"}</dd>
                      </div>
                      <div>
                        <dt>{isZh ? "\u8282\u594f" : "Pacing"}</dt>
                        <dd>{sample.pacing_notes.join(" / ")}</dd>
                      </div>
                      <div>
                        <dt>{isZh ? "\u590d\u7528\u6a21\u677f" : "Template"}</dt>
                        <dd>{sample.reuse_template.join(" / ")}</dd>
                      </div>
                      <div>
                        <dt>{isZh ? "\u907f\u6284" : "Avoid"}</dt>
                        <dd>{sample.risk_notes.join(" / ")}</dd>
                      </div>
                    </dl>
                  </div>
                ))}
              </div>
            ) : (
              <div className="action-empty-state action-empty-state-inline">
                <p className="panel-note">
                  {isZh
                    ? "还没有精品样本分析。先从仪表盘选择一个视频进入分析队列，随后可在本页触发前 5 分钟样本分析。"
                    : "No sample analysis yet. Start by analyzing a video from the dashboard, then trigger the first-five-minute sample analysis here."}
                </p>
                <button className="secondary-action compact-action" onClick={() => onRunNextAction?.(nextAction) ?? onOpenDashboard?.()} type="button">
                  {isZh ? "选择候选视频" : "Pick Candidate Video"}
                </button>
              </div>
            )}
          </article>
        </>
      )}
    </main>
  );
}
