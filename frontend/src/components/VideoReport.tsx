import { ChartNoAxesCombined, ListChecks, MessageSquareText, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import {
  analyzeSample,
  fetchSampleAnalyses,
  fetchReportTranscript,
  fetchReports,
  queueReportTranslation,
  reanalyzeLatestReport,
} from "../api";
import type { Language, SampleAnalysis, TranscriptBundle, VideoReportData } from "../types";

interface VideoReportProps {
  language: Language;
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

export default function VideoReport({ language }: VideoReportProps) {
  const [report, setReport] = useState<VideoReportData | null>(null);
  const [reports, setReports] = useState<VideoReportData[]>([]);
  const [selectedReportId, setSelectedReportId] = useState("");
  const [bundle, setBundle] = useState<TranscriptBundle>({ transcript: null, translation: null });
  const [activeTab, setActiveTab] = useState<"analysis" | "raw" | "translation">("analysis");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isTranslating, setIsTranslating] = useState(false);
  const [translationError, setTranslationError] = useState("");
  const [analysisError, setAnalysisError] = useState("");
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
    } else {
      setBundle({ transcript: null, translation: null });
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

  const selectReport = async (reportId: string) => {
    const selected = reports.find(item => item.id === reportId);
    setSelectedReportId(reportId);
    setReport(selected ?? null);
    setBundle(await fetchReportTranscript(reportId));
    setActiveTab("analysis");
    setAnalysisError("");
    setTranslationError("");
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
          <article className="panel">
            <p className="panel-note">
              {isZh ? "\u8fd8\u6ca1\u6709\u5206\u6790\u62a5\u544a\uff0c\u8bf7\u5148\u5728\u4eea\u8868\u76d8\u5206\u6790\u4e00\u6761\u89c6\u9891\u3002" : "No report yet. Analyze a video from the dashboard first."}
            </p>
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
              <p className="panel-note">
                {isZh
                  ? "\u8fd8\u6ca1\u6709\u7cbe\u54c1\u6837\u672c\u5206\u6790\u3002\u4ece\u4eea\u8868\u76d8\u6216\u672c\u9875\u624b\u52a8\u89e6\u53d1\u540e\uff0c\u7cfb\u7edf\u4f1a\u53ea\u5904\u7406\u89c6\u9891\u524d 5 \u5206\u949f\u3002"
                  : "No sample analysis yet. Trigger it from the dashboard or this page; the system only processes the first 5 minutes."}
              </p>
            )}
          </article>
        </>
      )}
    </main>
  );
}
