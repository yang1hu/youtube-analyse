import { Clipboard, Download, Factory, FileText, Play, ScanSearch, ShieldAlert, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  createImitationProject,
  exportImitationDraftMarkdown,
  exportImitationMarkdown,
  fetchImitationFactory,
  InkOSRunApiError,
  reduceImitationDraftRisk,
  rewriteImitationDraft,
  rewriteImitationRiskSegment,
  runImitationInkos,
  saveImitationDraft,
  updateImitationDraftStatus
} from "../api";
import type { CreationPipelineNextAction, ImitationDraft, ImitationFactoryResponse, ImitationProject, Language } from "../types";

interface ImitationFactoryProps {
  focusedProjectId?: string;
  focusedTemplateId?: string;
  language: Language;
  nextAction?: CreationPipelineNextAction;
  onOpenDashboard?: () => void;
  onOpenReports?: () => void;
  onProjectsChanged?: () => void | Promise<void>;
  onRunNextAction?: (action?: CreationPipelineNextAction) => void;
}

const copy = {
  zh: {
    antiCopy: "避抄规则",
    checkDraft: "保存并检测",
    copyCommand: "复制命令",
    create: "生成创作包",
    draft: "生成稿质检",
    draftExport: "导出",
    draftPlaceholder: "把 InkOS 或人工改写后的成稿粘贴到这里，检测与原文案的重合、句段复用和结构风险。",
    markPublishable: "可发布",
    markRevision: "待修改",
    direction: "新故事方向",
    directionPlaceholder: "例如：改成现代都市短片小说，主角是被低估的实习生，保留信息差和公开反转。",
    download: "下载参考包",
    empty: "还没有创作项目。先分析一条视频，再在这里生成 InkOS 创作包。",
    exportCopied: "已复制 InkOS 命令。",
    intro: "把 YouTube 视频报告转成 InkOS 可执行的原创转化创作包：参考结构、节奏和爽点机制，同时明确避抄边界。",
    inkosNotReady: "InkOS 未配置，先设置 YCA_INKOS_COMMAND 或把 inkos 加入 PATH。",
    inkosReady: "InkOS 已就绪",
    inkosRun: "InkOS 生成记录",
    inkosRunComplete: "生成成功",
    inkosRunFailed: "生成失败",
    inkosRunHistory: "历史运行",
    inkosElapsed: "耗时",
    inkosReference: "参考包",
    inkosPreview: "生成前预览",
    inkosEstimatedTokens: "预估 tokens",
    inkosRiskNotes: "风险提示",
    inkosChecklist: "检查清单",
    inkosRetry: "重新运行",
    inkosRerunReference: "用此参考包重新生成",
    keepNarration: "保持原视频叙述口吻",
    outputType: "输出类型",
    projects: "创作项目",
    quality: "验收标准",
    reference: "InkOS 创作包",
    repeatedPhrases: "重复短语",
    reduceRisk: "降低风险",
    rewriteSegment: "改写此段",
    rewriteDraft: "生成改写",
    reusedEntities: "复用设定",
    riskSegments: "风险段落",
    qaHistory: "质检历史",
    riskLow: "低风险",
    riskMedium: "中风险",
    riskHigh: "高风险",
    report: "源视频报告",
    risk: "风险",
    runInkos: "运行 InkOS",
    rewriteFaster: "节奏更快",
    rewriteOpening: "开场更强",
    rewriteShortDrama: "短剧对白",
    rewriteShorts: "Shorts 口播",
    rewriteCompressed: "压缩篇幅",
    rewritePlotReframe: "桥段重构",
    selectIdea: "选题卡",
    selectTemplate: "结构模板",
    selectStyle: "风格包",
    similarity: "结构保留强度",
    targetLength: "目标长度",
    title: "创作转化工坊"
  },
  en: {
    antiCopy: "Anti-copy Rules",
    checkDraft: "Save & Check",
    copyCommand: "Copy Command",
    create: "Create Brief",
    draft: "Draft QA",
    draftExport: "Export",
    draftPlaceholder: "Paste the InkOS or edited draft here to check text overlap, repeated phrases, and structural risk against the source script.",
    markPublishable: "Publishable",
    markRevision: "Needs Revision",
    direction: "New Story Direction",
    directionPlaceholder: "Example: turn it into a modern short fiction piece about an underestimated intern while keeping the information gap and public reversal.",
    download: "Download Reference",
    empty: "No creation projects yet. Analyze a video first, then create an InkOS transformation brief here.",
    exportCopied: "InkOS command copied.",
    intro: "Turn a YouTube video report into an InkOS-ready creation brief: reference structure, pacing, and payoff mechanics while defining clear anti-copy boundaries.",
    inkosNotReady: "InkOS is not configured. Set YCA_INKOS_COMMAND or add inkos to PATH.",
    inkosReady: "InkOS ready",
    inkosRun: "InkOS Run Record",
    inkosRunComplete: "Generated",
    inkosRunFailed: "Failed",
    inkosRunHistory: "Run History",
    inkosElapsed: "Elapsed",
    inkosReference: "Reference",
    inkosPreview: "Generation Preview",
    inkosEstimatedTokens: "Estimated tokens",
    inkosRiskNotes: "Risk Notes",
    inkosChecklist: "Checklist",
    inkosRetry: "Retry",
    inkosRerunReference: "Regenerate from this reference",
    keepNarration: "Keep source narration voice",
    outputType: "Output Type",
    projects: "Creation Projects",
    quality: "Quality Checks",
    reference: "InkOS Brief",
    repeatedPhrases: "Repeated Phrases",
    reduceRisk: "Reduce Risk",
    rewriteSegment: "Rewrite Segment",
    rewriteDraft: "Rewrite",
    reusedEntities: "Reused Entities",
    riskSegments: "Risk Segments",
    qaHistory: "QA History",
    riskLow: "Low Risk",
    riskMedium: "Medium Risk",
    riskHigh: "High Risk",
    report: "Source Report",
    risk: "Risk",
    runInkos: "Run InkOS",
    rewriteFaster: "Faster pacing",
    rewriteOpening: "Stronger opening",
    rewriteShortDrama: "Short drama",
    rewriteShorts: "Shorts narration",
    rewriteCompressed: "Compress",
    rewritePlotReframe: "Plot reframe",
    selectIdea: "Idea Card",
    selectTemplate: "Structure Template",
    selectStyle: "Style Pack",
    similarity: "Structure Retention",
    targetLength: "Target Length",
    title: "Story Remix Lab"
  }
} satisfies Record<Language, Record<string, string>>;

const outputLabels = {
  zh: {
    short_fiction: "短片小说",
    story_recap: "故事解说文案",
    short_drama: "短剧脚本",
    interactive: "互动故事"
  },
  en: {
    short_fiction: "Short Fiction",
    story_recap: "Story Recap",
    short_drama: "Short Drama",
    interactive: "Interactive Story"
  }
};

const similarityLabels = {
  zh: {
    low: "轻度：只保留机制",
    medium: "中度：保留结构和节奏",
    high: "强风格：贴近叙述口吻"
  },
  en: {
    low: "Low: mechanics only",
    medium: "Medium: structure and pacing",
    high: "High: close narrative voice"
  }
};

type RewriteMode = "faster_pacing" | "stronger_opening" | "short_drama" | "shorts_narration" | "compressed" | "plot_reframe";

function formatElapsed(ms?: number) {
  if (!ms && ms !== 0) return "-";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatRunTime(value?: string) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default function ImitationFactory({
  focusedProjectId = "",
  focusedTemplateId = "",
  language,
  nextAction,
  onOpenDashboard,
  onOpenReports,
  onProjectsChanged,
  onRunNextAction
}: ImitationFactoryProps) {
  const t = copy[language];
  const [data, setData] = useState<ImitationFactoryResponse>({ projects: [], reports: [], ideas: [] });
  const [selectedReportId, setSelectedReportId] = useState("");
  const [selectedIdeaId, setSelectedIdeaId] = useState("");
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [selectedStyleId, setSelectedStyleId] = useState("");
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [direction, setDirection] = useState("");
  const [outputType, setOutputType] = useState<"short_fiction" | "story_recap" | "short_drama" | "interactive">("short_fiction");
  const [similarityLevel, setSimilarityLevel] = useState<"low" | "medium" | "high">("medium");
  const [targetLength, setTargetLength] = useState("2500-4000 Chinese characters");
  const [keepNarration, setKeepNarration] = useState(true);
  const [draftText, setDraftText] = useState("");
  const [isWorking, setIsWorking] = useState(false);
  const [isCheckingDraft, setIsCheckingDraft] = useState(false);
  const [isRunningInkos, setIsRunningInkos] = useState(false);
  const [activeDraftActionId, setActiveDraftActionId] = useState("");
  const [rewriteModes, setRewriteModes] = useState<Record<string, RewriteMode>>({});
  const [message, setMessage] = useState("");

  const selectedProject = data.projects.find(project => project.id === selectedProjectId) ?? data.projects[0] ?? null;
  const selectedTemplate = data.templates?.find(template => template.id === selectedTemplateId) ?? null;
  const latestDraft = selectedProject?.generated_drafts?.[0] ?? null;
  const latestReport = selectedProject?.latest_similarity_report ?? null;
  const inkosStatus = data.inkos_status;
  const canRunInkos = Boolean(inkosStatus?.configured);
  const reportIdeas = useMemo(
    () => data.ideas.filter(idea => !selectedReportId || idea.source_report_id === selectedReportId),
    [data.ideas, selectedReportId]
  );

  const load = async () => {
    try {
      const next = await fetchImitationFactory();
      setData(next);
      setSelectedReportId(current => current || next.reports[0]?.id || "");
      setSelectedIdeaId(current => current || next.ideas[0]?.id || "");
      setSelectedProjectId(current => current || next.projects[0]?.id || "");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Creation workspace failed to load.");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (focusedProjectId && data.projects.some(project => project.id === focusedProjectId)) {
      setSelectedProjectId(focusedProjectId);
    }
  }, [data.projects, focusedProjectId]);

  useEffect(() => {
    if (focusedTemplateId && data.templates?.some(template => template.id === focusedTemplateId)) {
      setSelectedTemplateId(focusedTemplateId);
    }
  }, [data.templates, focusedTemplateId]);

  useEffect(() => {
    if (reportIdeas.length && !reportIdeas.some(idea => idea.id === selectedIdeaId)) {
      setSelectedIdeaId(reportIdeas[0].id);
    } else if (!reportIdeas.length && selectedIdeaId) {
      setSelectedIdeaId("");
    }
  }, [reportIdeas, selectedIdeaId]);

  const createProject = async () => {
    if (!selectedReportId || !direction.trim()) {
      setMessage(language === "zh" ? "请选择报告并填写新故事方向。" : "Select a report and enter a new story direction.");
      return;
    }
    setIsWorking(true);
    setMessage("");
    try {
      const project = await createImitationProject({
        report_id: selectedReportId,
        idea_id: selectedIdeaId || null,
        template_id: selectedTemplateId || null,
        style_id: selectedStyleId || null,
        direction,
        output_type: outputType,
        similarity_level: similarityLevel,
        target_length: targetLength,
        keep_narration: keepNarration
      });
      setData(current => ({ ...current, projects: [project, ...current.projects] }));
      setSelectedProjectId(project.id);
      setMessage(language === "zh" ? "创作包已生成。" : "Creation brief created.");
      void onProjectsChanged?.();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Creation failed.");
    } finally {
      setIsWorking(false);
    }
  };

  const copyCommand = async (project: ImitationProject) => {
    await navigator.clipboard.writeText(project.inkos_command);
    setMessage(t.exportCopied);
  };

  const checkDraft = async (project: ImitationProject) => {
    if (!draftText.trim()) {
      setMessage(language === "zh" ? "请先粘贴生成稿。" : "Paste a draft first.");
      return;
    }
    setIsCheckingDraft(true);
    setMessage("");
    try {
      const updated = await saveImitationDraft(project.id, {
        draft_text: draftText,
        title: language === "zh" ? "生成稿检测" : "Draft check"
      });
      setData(current => ({
        ...current,
        projects: current.projects.map(item => (item.id === updated.id ? updated : item))
      }));
      setSelectedProjectId(updated.id);
      setDraftText("");
      setMessage(language === "zh" ? "生成稿已保存，风险检测已完成。" : "Draft saved and checked.");
      void onProjectsChanged?.();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Draft check failed.");
    } finally {
      setIsCheckingDraft(false);
    }
  };

  const runInkos = async (project: ImitationProject, referenceRunId?: string) => {
    setIsRunningInkos(true);
    setMessage("");
    try {
      const updated = await runImitationInkos(project.id, referenceRunId);
      setData(current => ({
        ...current,
        projects: current.projects.map(item => (item.id === updated.id ? updated : item))
      }));
      setSelectedProjectId(updated.id);
      setMessage(
        referenceRunId
          ? language === "zh"
            ? "InkOS 已使用历史参考包重新生成草稿，并完成风险检测。"
            : "InkOS regenerated a draft from the historical reference and completed the risk check."
          : language === "zh"
            ? "InkOS 已生成草稿并完成风险检测。"
            : "InkOS generated a draft and completed the risk check."
      );
      void onProjectsChanged?.();
    } catch (error) {
      if (error instanceof InkOSRunApiError && error.project) {
        updateProject(error.project);
      }
      setMessage(error instanceof Error ? error.message : "InkOS run failed.");
    } finally {
      setIsRunningInkos(false);
    }
  };

  const downloadReference = async (project: ImitationProject) => {
    try {
      const exported = await exportImitationMarkdown(project.id);
      const blob = new Blob([exported.markdown], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = exported.filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Export failed.");
    }
  };

  const updateProject = (updated: ImitationProject) => {
    setData(current => ({
      ...current,
      projects: current.projects.map(item => (item.id === updated.id ? updated : item))
    }));
    setSelectedProjectId(updated.id);
    void onProjectsChanged?.();
  };

  const downloadDraft = async (project: ImitationProject, draft: ImitationDraft) => {
    try {
      const exported = await exportImitationDraftMarkdown(project.id, draft.id);
      const blob = new Blob([exported.markdown], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = exported.filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Export failed.");
    }
  };

  const setDraftStatus = async (project: ImitationProject, draft: ImitationDraft, status: string) => {
    setActiveDraftActionId(draft.id);
    try {
      const updated = await updateImitationDraftStatus(project.id, draft.id, status);
      updateProject(updated);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Draft update failed.");
    } finally {
      setActiveDraftActionId("");
    }
  };

  const reduceRisk = async (project: ImitationProject, draft: ImitationDraft) => {
    setActiveDraftActionId(draft.id);
    try {
      const updated = await reduceImitationDraftRisk(project.id, draft.id);
      updateProject(updated);
      setMessage(language === "zh" ? "已生成降风险版本，并重新完成检测。" : "A lower-risk version was created and checked.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Risk reduction failed.");
    } finally {
      setActiveDraftActionId("");
    }
  };

  const rewriteDraft = async (project: ImitationProject, draft: ImitationDraft, overrideMode?: RewriteMode) => {
    setActiveDraftActionId(draft.id);
    try {
      const updated = await rewriteImitationDraft(project.id, draft.id, overrideMode ?? rewriteModes[draft.id] ?? "faster_pacing");
      updateProject(updated);
      setMessage(language === "zh" ? "已生成新的改写版本，并完成风险检测。" : "A rewritten version was created and checked.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Rewrite failed.");
    } finally {
      setActiveDraftActionId("");
    }
  };

  const rewriteRiskSegment = async (project: ImitationProject, draft: ImitationDraft, segmentIndex: number) => {
    setActiveDraftActionId(`${draft.id}:segment:${segmentIndex}`);
    setMessage("");
    try {
      const updated = await rewriteImitationRiskSegment(project.id, draft.id, segmentIndex);
      updateProject(updated);
      await onProjectsChanged?.();
      setMessage(language === "zh" ? "已生成局部降风险版本。" : "Risk segment rewrite created.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Risk segment rewrite failed.");
    } finally {
      setActiveDraftActionId("");
    }
  };

  const riskLabel = (risk: string) => {
    if (risk === "high") return t.riskHigh;
    if (risk === "medium") return t.riskMedium;
    if (risk === "low") return t.riskLow;
    return risk;
  };

  const riskTone = (risk: string) => {
    if (risk === "high") return "failed";
    if (risk === "medium") return "warning";
    if (risk === "low") return "ok";
    return "muted";
  };

  const riskTypeLabel = (riskType: string) => {
    if (riskType === "semantic_plot") return language === "zh" ? "语义桥段" : "Semantic plot";
    if (riskType === "plot_order") return language === "zh" ? "桥段顺序" : "Plot order";
    if (riskType === "pacing") return language === "zh" ? "叙事节奏" : "Pacing";
    if (riskType === "structure") return language === "zh" ? "结构保留" : "Structure";
    if (riskType === "style") return language === "zh" ? "风格接近" : "Style";
    if (riskType === "text_overlap") return language === "zh" ? "文本重合" : "Text overlap";
    if (riskType === "entity_reuse") return language === "zh" ? "设定复用" : "Entity reuse";
    return riskType.replace(/_/g, " ");
  };

  const qualityGateStatusLabel = (status?: string) => {
    if (!status) return "-";
    if (status === "pass") return language === "zh" ? "通过" : "Pass";
    if (status === "blocked") return language === "zh" ? "阻断" : "Blocked";
    if (status === "needs_revision") return language === "zh" ? "待修改" : "Needs Revision";
    return status;
  };

  const qualityGateStatusTone = (status?: string) => {
    if (status === "pass") return "ok";
    if (status === "blocked") return "failed";
    if (status === "needs_revision") return "warning";
    return "muted";
  };

  const storyEvidenceFields = selectedProject?.story_workbench_analysis
    ? [
        { key: "opening_5s_hook", label: language === "zh" ? "5 秒钩子" : "5s Hook" },
        { key: "first_30s_retention", label: language === "zh" ? "前 30 秒留存" : "First 30s" },
        { key: "protagonist_position", label: language === "zh" ? "主角处境" : "Protagonist" },
        { key: "status_gap", label: language === "zh" ? "身份/信息差" : "Status Gap" },
        { key: "first_payoff", label: language === "zh" ? "第一爽点" : "First Payoff" },
        { key: "middle_escalation", label: language === "zh" ? "中段升级" : "Escalation" },
        { key: "opposition_design", label: language === "zh" ? "阻力设计" : "Opposition" },
        { key: "public_reversal", label: language === "zh" ? "公开反转" : "Public Reversal" },
        { key: "ending_suspense", label: language === "zh" ? "结尾悬念" : "Ending Suspense" }
      ].filter(field => String(selectedProject.story_workbench_analysis?.[field.key as keyof typeof selectedProject.story_workbench_analysis] ?? "").trim())
    : [];

  const actionLevelLabel = (level?: string, fallback?: string) => {
    if (fallback) return fallback;
    if (level === "must_fix") return language === "zh" ? "必须修改" : "Must Fix";
    if (level === "should_fix") return language === "zh" ? "建议修改" : "Should Fix";
    if (level === "acceptable") return language === "zh" ? "可接受" : "Acceptable";
    return level || (language === "zh" ? "建议修改" : "Should Fix");
  };

  const actionLevelTone = (level?: string, severity?: string) => {
    if (level === "must_fix" || severity === "high") return "failed";
    if (level === "acceptable" || severity === "low") return "ok";
    return "warning";
  };

  const rewriteOptions: { value: RewriteMode; label: string }[] = [
    { value: "faster_pacing", label: t.rewriteFaster },
    { value: "stronger_opening", label: t.rewriteOpening },
    { value: "short_drama", label: t.rewriteShortDrama },
    { value: "shorts_narration", label: t.rewriteShorts },
    { value: "compressed", label: t.rewriteCompressed },
    { value: "plot_reframe", label: t.rewritePlotReframe }
  ];

  const rewritePlan = useMemo(() => {
    if (!latestReport) return null;
    const failedChecks = latestReport.quality_gate?.checks.filter(check => !check.passed) ?? [];
    const failedCheckKeys = new Set([
      ...failedChecks.map(check => check.key),
      ...(latestReport.quality_gate?.failed_checks ?? [])
    ]);
    const riskSegments = latestReport.risk_segments ?? [];
    const mustFixSegments = riskSegments.filter(segment => segment.action_level === "must_fix" || segment.severity === "high");
    const shouldFixSegments = riskSegments.filter(
      segment => segment.action_level === "should_fix" && segment.severity !== "high"
    );
    const hasTextRisk =
      latestReport.risk_level === "high" ||
      ["text_overlap", "repeated_phrases", "reused_entities"].some(key => failedCheckKeys.has(key)) ||
      mustFixSegments.some(segment => ["text_overlap", "entity_reuse"].includes(segment.risk_type));
    const hasStructureRisk =
      ["structure_similarity", "style_similarity", "semantic_similarity"].some(key => failedCheckKeys.has(key)) ||
      riskSegments.some(segment => ["plot_order", "pacing", "structure", "style", "semantic_plot"].includes(segment.risk_type));
    const hasSemanticPlotRisk =
      failedCheckKeys.has("semantic_similarity") || riskSegments.some(segment => segment.risk_type === "semantic_plot");

    if (hasTextRisk) {
      return {
        tone: "failed",
        primaryAction: "reduce_risk",
        title: language === "zh" ? "先处理避抄边界" : "Fix anti-copy boundaries first",
        body:
          language === "zh"
            ? "当前稿件仍有文本重合、短语复用或专名沿用风险，建议先生成降风险版本，再重新检测。"
            : "This draft still has text overlap, phrase reuse, or entity reuse risk. Create a lower-risk version before checking again.",
        ctaLabel: t.reduceRisk,
        failedChecks,
        mustFixCount: mustFixSegments.length,
        shouldFixCount: shouldFixSegments.length,
        recommendations: latestReport.recommendations.slice(0, 3)
      };
    }

    if (hasStructureRisk || failedChecks.length > 0 || shouldFixSegments.length > 0) {
      return {
        tone: "warning",
        primaryAction: "rewrite",
        suggestedMode: hasSemanticPlotRisk ? ("plot_reframe" as RewriteMode) : undefined,
        title: hasSemanticPlotRisk
          ? language === "zh"
            ? "先重构语义桥段"
            : "Reframe semantic plot beats"
          : language === "zh"
            ? "进入结构与节奏改写"
            : "Rewrite structure and pacing",
        body:
          hasSemanticPlotRisk
            ? language === "zh"
              ? "当前稿件可能只是替换了词语，但事件载体、人物动机或反转兑现方式仍过近。建议使用桥段重构版，先换掉关键事件机制再复检。"
              : "This draft may have changed wording while keeping the same event carrier, motive, or payoff. Use plot reframe, then check again."
            : language === "zh"
              ? "硬性风险已可控，但结构保留强度、桥段顺序或叙事节奏仍需要调整，建议选择改写模式生成新版本。"
              : "Hard risks are controlled, but structure retention, plot order, or pacing still needs revision. Pick a rewrite mode and create a new version.",
        ctaLabel: t.rewriteDraft,
        failedChecks,
        mustFixCount: mustFixSegments.length,
        shouldFixCount: shouldFixSegments.length,
        recommendations: latestReport.recommendations.slice(0, 3)
      };
    }

    return {
      tone: "ok",
      primaryAction: "publish",
      title: language === "zh" ? "可进入人工终审" : "Ready for human review",
      body:
        language === "zh"
          ? "质量门槛已通过，建议人工确认角色、地名、关键设定和具体事件没有沿用原视频后再导出。"
          : "The quality gate passed. Have a human confirm names, settings, and concrete events are not reused before export.",
      ctaLabel: t.markPublishable,
      failedChecks,
      mustFixCount: mustFixSegments.length,
      shouldFixCount: shouldFixSegments.length,
      recommendations: latestReport.recommendations.slice(0, 3)
    };
  }, [language, latestReport, t.markPublishable, t.reduceRisk, t.rewriteDraft]);

  return (
    <main className="app-shell workspace-page">
      <section className="page-intro" aria-labelledby="imitation-factory-title">
        <p className="eyebrow">{language === "zh" ? "视频到故事" : "Video to story"}</p>
        <h1 id="imitation-factory-title">{t.title}</h1>
        <p className="hero-summary">{t.intro}</p>
        <div className={canRunInkos ? "integration-status integration-status-ok" : "integration-status integration-status-warning"}>
          {canRunInkos ? <ShieldCheck aria-hidden="true" size={18} /> : <ShieldAlert aria-hidden="true" size={18} />}
          <span>{canRunInkos ? t.inkosReady : t.inkosNotReady}</span>
          {inkosStatus?.command && <code>{inkosStatus.command}</code>}
        </div>
      </section>

      <section className="imitation-layout">
        <article className="panel style-panel imitation-control-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">{language === "zh" ? "输入" : "Inputs"}</p>
              <h2>{t.create}</h2>
            </div>
            <Factory aria-hidden="true" size={22} />
          </div>

          <label className="field-group">
            <span>{t.report}</span>
            <select onChange={event => setSelectedReportId(event.target.value)} value={selectedReportId}>
              <option value="">{language === "zh" ? "暂无报告" : "No report"}</option>
              {data.reports.map(report => (
                <option key={report.id} value={report.id}>
                  {report.video_title || report.video_url}
                </option>
              ))}
            </select>
          </label>

          <label className="field-group">
            <span>{t.selectIdea}</span>
            <select onChange={event => setSelectedIdeaId(event.target.value)} value={selectedIdeaId}>
              <option value="">{language === "zh" ? "自动使用第一张选题卡" : "Use first available idea"}</option>
              {reportIdeas.map(idea => (
                <option key={idea.id} value={idea.id}>
                  {idea.title || idea.id}
                </option>
              ))}
            </select>
          </label>

          <label className="field-group">
            <span>{t.selectTemplate}</span>
            <select onChange={event => setSelectedTemplateId(event.target.value)} value={selectedTemplateId}>
              <option value="">{language === "zh" ? "不使用收藏模板" : "No saved template"}</option>
              {data.templates?.map(template => (
                <option key={template.id} value={template.id}>
                  {template.name}
                </option>
              ))}
            </select>
          </label>
          {selectedTemplate && (
            <div className="template-selected-summary">
              <span>{language === "zh" ? "复用" : "Reuse"} {selectedTemplate.reuse_count ?? 0}</span>
              <span>{language === "zh" ? "通过率" : "Pass"} {Number(selectedTemplate.publishable_rate || 0).toFixed(1)}%</span>
              <span>{language === "zh" ? "平均风险" : "Risk"} {selectedTemplate.average_risk_level || "-"}</span>
            </div>
          )}

          <label className="field-group">
            <span>{t.selectStyle}</span>
            <select onChange={event => setSelectedStyleId(event.target.value)} value={selectedStyleId}>
              <option value="">{language === "zh" ? "不使用风格包" : "No style pack"}</option>
              {data.styles?.map(style => (
                <option key={style.id} value={style.id}>
                  {style.name}
                </option>
              ))}
            </select>
          </label>

          <label className="field-group">
            <span>{t.direction}</span>
            <textarea
              className="inline-textarea imitation-direction"
              onChange={event => setDirection(event.target.value)}
              placeholder={t.directionPlaceholder}
              value={direction}
            />
          </label>

          <div className="imitation-options">
            <label className="field-group">
              <span>{t.outputType}</span>
              <select onChange={event => setOutputType(event.target.value as typeof outputType)} value={outputType}>
                {Object.entries(outputLabels[language]).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-group">
              <span>{t.similarity}</span>
              <select onChange={event => setSimilarityLevel(event.target.value as typeof similarityLevel)} value={similarityLevel}>
                {Object.entries(similarityLabels[language]).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="field-group">
            <span>{t.targetLength}</span>
            <input onChange={event => setTargetLength(event.target.value)} value={targetLength} />
          </label>

          <label className="field-toggle">
            <input checked={keepNarration} onChange={event => setKeepNarration(event.target.checked)} type="checkbox" />
            {t.keepNarration}
          </label>

          <button className="primary-action compact-action" disabled={isWorking || !selectedReportId} onClick={() => void createProject()} type="button">
            <FileText aria-hidden="true" size={18} />
            {isWorking ? (language === "zh" ? "生成中..." : "Creating...") : t.create}
          </button>
          {message && <p className="form-message form-message-idle">{message}</p>}
        </article>

        <article className="panel imitation-project-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">{language === "zh" ? "输出" : "Outputs"}</p>
              <h2>{t.projects}</h2>
            </div>
            <ShieldCheck aria-hidden="true" size={22} />
          </div>

          <div className="report-history-list imitation-project-list">
            {data.projects.map(project => (
              <button
                className={project.id === selectedProject?.id ? "report-history-item report-history-item-active" : "report-history-item"}
                key={project.id}
                onClick={() => setSelectedProjectId(project.id)}
                type="button"
              >
                <span>{project.name}</span>
                <small>
                  {outputLabels[language][project.output_type as keyof typeof outputLabels.zh] ?? project.output_type} / {similarityLabels[language][project.similarity_level as keyof typeof similarityLabels.zh] ?? project.similarity_level}
                </small>
              </button>
            ))}
          </div>

          {!data.projects.length && (
            <div className="action-empty-state action-empty-state-inline">
              <p className="panel-note">
                {data.reports.length
                  ? language === "zh"
                    ? "已有报告可用。选择源报告、填写新故事方向，然后生成 InkOS 创作包。"
                    : "Reports are ready. Select a source report, describe the new story direction, and create an InkOS brief."
                  : nextAction?.description ||
                    (language === "zh"
                      ? "还没有可用报告。先分析一条 YouTube 视频，再回来生成创作转化包。"
                      : "No source report is available yet. Analyze a YouTube video first, then return to create a transformation brief.")}
              </p>
              {data.reports.length ? (
                <button
                  className="primary-action compact-action"
                  disabled={isWorking || !selectedReportId}
                  onClick={() => void createProject()}
                  type="button"
                >
                  <FileText aria-hidden="true" size={16} />
                  {language === "zh" ? "生成创作包" : "Create Brief"}
                </button>
              ) : (
                <button className="secondary-action compact-action" onClick={() => onRunNextAction?.(nextAction) ?? (onOpenDashboard ?? onOpenReports)?.()} type="button">
                  {nextAction?.label || (language === "zh" ? "去分析视频" : "Analyze Video")}
                </button>
              )}
            </div>
          )}
        </article>
      </section>

      <section className="panel transcript-panel imitation-result-panel">
        {selectedProject ? (
          <div className="transcript-content">
            <div className="imitation-result-header">
              <div>
                <p className="eyebrow">{selectedProject.risk_level === "needs_review" ? `${t.risk}: review` : `${t.risk}: ${selectedProject.risk_level}`}</p>
                <h2>{selectedProject.name}</h2>
              </div>
              <div className="hero-actions report-actions">
                <button className="secondary-action compact-action" onClick={() => void copyCommand(selectedProject)} type="button">
                  <Clipboard aria-hidden="true" size={18} />
                  {t.copyCommand}
                </button>
                <button className="secondary-action compact-action" onClick={() => void downloadReference(selectedProject)} type="button">
                  <Download aria-hidden="true" size={18} />
                  {t.download}
                </button>
                <button className="primary-action compact-action" disabled={isRunningInkos || !canRunInkos} onClick={() => void runInkos(selectedProject)} type="button">
                  <Play aria-hidden="true" size={18} />
                  {isRunningInkos ? (language === "zh" ? "运行中..." : "Running...") : t.runInkos}
                </button>
              </div>
            </div>

            <pre className="script-box imitation-command">{selectedProject.inkos_command}</pre>

            {selectedProject.inkos_preview && (
              <article className="inkos-preview-panel">
                <div className="panel-heading">
                  <div>
                    <p className="eyebrow">{t.inkosPreview}</p>
                    <h3>{t.inkosEstimatedTokens}: {selectedProject.inkos_preview.estimated_total_tokens}</h3>
                  </div>
                  <span className="status-pill status-pill-warning">
                    {selectedProject.inkos_preview.similarity_level}
                  </span>
                </div>
                <div className="inkos-run-meta">
                  <span>{t.inkosReference}: {selectedProject.inkos_preview.reference_length}</span>
                  <span>Input: {selectedProject.inkos_preview.estimated_input_tokens}</span>
                  <span>Output: {selectedProject.inkos_preview.estimated_output_tokens}</span>
                  <span>{selectedProject.inkos_preview.target_length}</span>
                </div>
                <div className="inkos-preview-grid">
                  <div>
                    <strong>{t.inkosRiskNotes}</strong>
                    <ul className="compact-list">
                      {selectedProject.inkos_preview.risk_notes.map(item => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <strong>{t.inkosChecklist}</strong>
                    <ul className="compact-list">
                      {selectedProject.inkos_preview.checklist.map(item => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </article>
            )}

            {selectedProject.last_inkos_run && (
              <article className={`inkos-run-panel inkos-run-panel-${selectedProject.last_inkos_run.status}`}>
                <div className="panel-heading">
                  <div>
                    <p className="eyebrow">{t.inkosRun}</p>
                    <h3>
                      {selectedProject.last_inkos_run.status === "complete" ? t.inkosRunComplete : t.inkosRunFailed}
                    </h3>
                  </div>
                  <span className={`status-pill status-pill-${selectedProject.last_inkos_run.status === "complete" ? "ok" : "failed"}`}>
                    {selectedProject.last_inkos_run.status}
                  </span>
                </div>
                <div className="inkos-run-meta">
                  <span>{formatRunTime(selectedProject.last_inkos_run.completed_at || selectedProject.last_inkos_run.ran_at)}</span>
                  <span>{t.inkosElapsed}: {formatElapsed(selectedProject.last_inkos_run.elapsed_ms)}</span>
                  <span>
                    {t.inkosReference}: {selectedProject.last_inkos_run.request?.reference_length ?? 0}
                  </span>
                </div>
                {selectedProject.last_inkos_run.error_message && (
                  <p className="inkos-run-error">{selectedProject.last_inkos_run.error_message}</p>
                )}
                {selectedProject.last_inkos_run.status === "failed" && (
                  <div className="inkos-run-diagnostics">
                    <strong>{language === "zh" ? "失败诊断" : "Failure Diagnostics"}</strong>
                    <span>
                      {language === "zh" ? "运行目录" : "Run dir"}: {selectedProject.last_inkos_run.run_dir || "-"}
                    </span>
                    <span>
                      {language === "zh" ? "命令" : "Command"}: {(selectedProject.last_inkos_run.command ?? []).join(" ") || "-"}
                    </span>
                    <span>
                      {language === "zh" ? "建议" : "Next"}:{" "}
                      {language === "zh"
                        ? "检查 InkOS 命令、项目目录和输出文件后，可直接重试。"
                        : "Check the InkOS command, project directory, and output file, then retry."}
                    </span>
                  </div>
                )}
                {selectedProject.last_inkos_run.draft_preview && (
                  <p className="inkos-run-preview">{selectedProject.last_inkos_run.draft_preview}</p>
                )}
                <button
                  className="secondary-action compact-action"
                  disabled={isRunningInkos || !canRunInkos}
                  onClick={() => void runInkos(selectedProject)}
                  type="button"
                >
                  <Play aria-hidden="true" size={18} />
                  {t.inkosRetry}
                </button>
              </article>
            )}

            {(selectedProject.inkos_run_history?.length ?? 0) > 1 && (
              <details className="inkos-history-panel">
                <summary>{t.inkosRunHistory}</summary>
                <div className="inkos-history-list">
                  {selectedProject.inkos_run_history?.slice(1).map((run, index) => (
                    <div className="inkos-history-item" key={run.id ?? `${run.ran_at}-${index}`}>
                      <strong>{run.status === "complete" ? t.inkosRunComplete : t.inkosRunFailed}</strong>
                      <span>{formatRunTime(run.completed_at || run.ran_at)}</span>
                      <span>{formatElapsed(run.elapsed_ms)}</span>
                      {run.error_message && <small>{run.error_message}</small>}
                      <button
                        className="secondary-action compact-action"
                        disabled={isRunningInkos || !canRunInkos || !run.id || !run.request?.reference_markdown}
                        onClick={() => run.id && void runInkos(selectedProject, run.id)}
                        type="button"
                      >
                        <Play aria-hidden="true" size={16} />
                        {t.inkosRerunReference}
                      </button>
                    </div>
                  ))}
                </div>
              </details>
            )}

            {selectedProject.story_workbench_analysis && Object.keys(selectedProject.story_workbench_analysis).length > 0 && (
              <article className="story-reference-panel">
                <div className="panel-heading">
                  <div>
                    <p className="eyebrow">{language === "zh" ? "故事工坊引用" : "Story Workbench Reference"}</p>
                    <h3>{language === "zh" ? "短片小说结构基准" : "Short Fiction Structure Baseline"}</h3>
                  </div>
                  <span className="status-pill status-pill-ok">
                    {selectedProject.story_workbench_analysis.structure_confidence || selectedProject.story_workbench_source || "ok"}
                  </span>
                </div>
                <dl className="story-reference-fields">
                  <div>
                    <dt>{language === "zh" ? "5 秒钩子" : "5s Hook"}</dt>
                    <dd>{selectedProject.story_workbench_analysis.opening_5s_hook || "-"}</dd>
                  </div>
                  <div>
                    <dt>{language === "zh" ? "前 30 秒" : "First 30s"}</dt>
                    <dd>{selectedProject.story_workbench_analysis.first_30s_retention || "-"}</dd>
                  </div>
                  <div>
                    <dt>{language === "zh" ? "第一次爽点" : "First Payoff"}</dt>
                    <dd>{selectedProject.story_workbench_analysis.first_payoff || "-"}</dd>
                  </div>
                  <div>
                    <dt>{language === "zh" ? "结尾悬念" : "Ending Suspense"}</dt>
                    <dd>{selectedProject.story_workbench_analysis.ending_suspense || "-"}</dd>
                  </div>
                </dl>
                {storyEvidenceFields.length > 0 && (
                  <div className="story-reference-evidence-list">
                    {storyEvidenceFields.map(field => {
                      const analysisValue = String(
                        selectedProject.story_workbench_analysis?.[
                          field.key as keyof typeof selectedProject.story_workbench_analysis
                        ] ?? ""
                      );
                      const evidenceItem = selectedProject.story_workbench_analysis?.evidence?.[field.key];
                      const excerpt = evidenceItem?.excerpts?.[0] ?? "";
                      return (
                        <div className="story-reference-evidence-item" key={field.key}>
                          <strong>{field.label}</strong>
                          <p>{analysisValue}</p>
                          {excerpt && (
                            <small>
                              {language === "zh" ? "证据片段：" : "Evidence: "}
                              {excerpt}
                            </small>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
                {((selectedProject.story_workbench_analysis.reusable_template?.length ?? 0) > 0 ||
                  (selectedProject.story_workbench_analysis.non_reusable_content?.length ?? 0) > 0) && (
                  <div className="story-reference-boundary-grid">
                    <article>
                      <h4>{language === "zh" ? "可复用机制" : "Reusable mechanics"}</h4>
                      <ul className="compact-list">
                        {selectedProject.story_workbench_analysis.reusable_template?.map(item => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </article>
                    <article>
                      <h4>{language === "zh" ? "不可复用内容" : "Do not reuse"}</h4>
                      <ul className="compact-list">
                        {selectedProject.story_workbench_analysis.non_reusable_content?.map(item => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </article>
                  </div>
                )}
              </article>
            )}

            {selectedProject.source_style_profile && Object.keys(selectedProject.source_style_profile).length > 0 && (
              <article className="story-reference-panel">
                <div className="panel-heading">
                  <div>
                    <p className="eyebrow">{language === "zh" ? "风格包引用" : "Style Pack Reference"}</p>
                    <h3>{selectedProject.source_style_profile.name || selectedProject.source_style_name}</h3>
                  </div>
                  <span className="status-pill status-pill-muted">
                    {selectedProject.source_style_profile.topic_type || "style"}
                  </span>
                </div>
                <dl className="story-reference-fields">
                  <div>
                    <dt>{language === "zh" ? "开场公式" : "Opening Formula"}</dt>
                    <dd>{selectedProject.source_style_profile.opening_formula || "-"}</dd>
                  </div>
                  <div>
                    <dt>{language === "zh" ? "句式风格" : "Sentence Style"}</dt>
                    <dd>{selectedProject.source_style_profile.sentence_style || "-"}</dd>
                  </div>
                </dl>
                {!!selectedProject.source_style_profile.rhythm_formula?.length && (
                  <ul className="compact-list">
                    {selectedProject.source_style_profile.rhythm_formula.slice(0, 5).map(item => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                )}
              </article>
            )}

            <div className="imitation-detail-grid">
              <article>
                <h3>{language === "zh" ? "必须保留" : "Keep"}</h3>
                <ul className="compact-list">
                  {selectedProject.reuse_constraints.map(item => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>
              <article>
                <h3>{t.antiCopy}</h3>
                <ul className="compact-list">
                  {selectedProject.anti_copy_rules.map(item => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>
              <article>
                <h3>{t.quality}</h3>
                <ul className="compact-list">
                  {selectedProject.quality_checks.map(item => (
                    <li key={item.key}>
                      <strong>{item.label}</strong>
                      <span>{item.target}</span>
                    </li>
                  ))}
                </ul>
              </article>
              <article>
                <h3>{language === "zh" ? "文风指纹" : "Style Fingerprint"}</h3>
                <dl className="style-fields">
                  <div>
                    <dt>{language === "zh" ? "人称" : "Person"}</dt>
                    <dd>{selectedProject.style_fingerprint.narration_person}</dd>
                  </div>
                  <div>
                    <dt>{language === "zh" ? "节奏" : "Pacing"}</dt>
                    <dd>{selectedProject.style_fingerprint.pacing_rule}</dd>
                  </div>
                  <div>
                    <dt>{language === "zh" ? "转场" : "Transition"}</dt>
                    <dd>{selectedProject.style_fingerprint.transition_style}</dd>
                  </div>
                </dl>
              </article>
            </div>

            <div className="draft-check-panel">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">{language === "zh" ? "发布前验收" : "Pre-publish QA"}</p>
                  <h3>{t.draft}</h3>
                </div>
                <ScanSearch aria-hidden="true" size={20} />
              </div>
              <textarea
                className="inline-textarea draft-check-editor"
                onChange={event => setDraftText(event.target.value)}
                placeholder={t.draftPlaceholder}
                value={draftText}
              />
              <button className="secondary-action compact-action" disabled={isCheckingDraft} onClick={() => void checkDraft(selectedProject)} type="button">
                <ScanSearch aria-hidden="true" size={18} />
                {isCheckingDraft ? (language === "zh" ? "检测中..." : "Checking...") : t.checkDraft}
              </button>

              {selectedProject.latest_similarity_report && (
                <div className="draft-risk-report">
                  <div className={`draft-risk-score draft-risk-${selectedProject.latest_similarity_report.risk_level}`}>
                    <strong>{riskLabel(selectedProject.latest_similarity_report.risk_level)}</strong>
                    <span>{selectedProject.latest_similarity_report.text_overlap_percent}% {language === "zh" ? "文本重合" : "text overlap"}</span>
                  </div>
                  {selectedProject.latest_similarity_report.quality_gate && (
                    <article className={`quality-gate-panel quality-gate-${selectedProject.latest_similarity_report.quality_gate.status}`}>
                      <div>
                        <p className="eyebrow">{language === "zh" ? "质量门槛" : "Quality Gate"}</p>
                        <h4>{selectedProject.latest_similarity_report.quality_gate.summary}</h4>
                        <p>{selectedProject.latest_similarity_report.quality_gate.next_action}</p>
                      </div>
                      <div className="quality-gate-checks">
                        {selectedProject.latest_similarity_report.quality_gate.checks.map(check => (
                          <span className={`status-pill status-pill-${check.passed ? "ok" : "failed"}`} key={check.key}>
                            {check.label}: {String(check.value)} / {check.target}
                          </span>
                        ))}
                      </div>
                    </article>
                  )}
                  {rewritePlan && (
                    <article className={`rewrite-plan-panel rewrite-plan-${rewritePlan.tone}`}>
                      <div className="rewrite-plan-main">
                        <p className="eyebrow">{language === "zh" ? "改写前检查" : "Rewrite Plan"}</p>
                        <h4>{rewritePlan.title}</h4>
                        <p>{rewritePlan.body}</p>
                      </div>
                      <div className="rewrite-plan-counters">
                        <span>{language === "zh" ? "未通过" : "Failed"} {rewritePlan.failedChecks.length}</span>
                        <span>{language === "zh" ? "必须修" : "Must fix"} {rewritePlan.mustFixCount}</span>
                        <span>{language === "zh" ? "建议修" : "Should fix"} {rewritePlan.shouldFixCount}</span>
                      </div>
                      {rewritePlan.failedChecks.length > 0 && (
                        <div className="rewrite-plan-checks">
                          {rewritePlan.failedChecks.map(check => (
                            <span className="status-pill status-pill-failed" key={check.key}>
                              {check.label}: {String(check.value)} / {check.target}
                            </span>
                          ))}
                        </div>
                      )}
                      {rewritePlan.recommendations.length > 0 && (
                        <ul className="compact-list rewrite-plan-recommendations">
                          {rewritePlan.recommendations.map(item => (
                            <li key={item}>{item}</li>
                          ))}
                        </ul>
                      )}
                      <div className="rewrite-plan-actions">
                        <button
                          className="primary-action compact-action"
                          disabled={!latestDraft || (latestDraft ? activeDraftActionId.startsWith(latestDraft.id) : false)}
                          onClick={() => {
                            if (!latestDraft) return;
                            if (rewritePlan.primaryAction === "reduce_risk") {
                              void reduceRisk(selectedProject, latestDraft);
                            } else if (rewritePlan.primaryAction === "rewrite") {
                              const suggestedMode = rewritePlan.suggestedMode;
                              if (suggestedMode) {
                                setRewriteModes(current => ({ ...current, [latestDraft.id]: suggestedMode }));
                              }
                              void rewriteDraft(selectedProject, latestDraft, suggestedMode);
                            } else {
                              void setDraftStatus(selectedProject, latestDraft, "publishable");
                            }
                          }}
                          type="button"
                        >
                          {rewritePlan.primaryAction === "publish" ? (
                            <ShieldCheck aria-hidden="true" size={16} />
                          ) : (
                            <FileText aria-hidden="true" size={16} />
                          )}
                          {rewritePlan.ctaLabel}
                        </button>
                        <small>
                          {latestDraft
                            ? language === "zh"
                              ? `基于最新版本：${latestDraft.title}`
                              : `Based on latest draft: ${latestDraft.title}`
                            : language === "zh"
                              ? "先保存生成稿后再执行改写动作"
                              : "Save a draft before running rewrite actions"}
                        </small>
                      </div>
                    </article>
                  )}
                  <div className="draft-risk-metrics">
                    <span>{language === "zh" ? "结构相似" : "Structure"} {(selectedProject.latest_similarity_report.structure_similarity * 100).toFixed(0)}%</span>
                    <span>{language === "zh" ? "文风相似" : "Style"} {(selectedProject.latest_similarity_report.style_similarity * 100).toFixed(0)}%</span>
                    <span>{language === "zh" ? "桥段顺序" : "Plot Order"} {((selectedProject.latest_similarity_report.plot_similarity ?? 0) * 100).toFixed(0)}%</span>
                    <span>{language === "zh" ? "叙事节奏" : "Pacing"} {((selectedProject.latest_similarity_report.pacing_similarity ?? 0) * 100).toFixed(0)}%</span>
                    <span>{language === "zh" ? "语义桥段" : "Semantic Plot"} {((selectedProject.latest_similarity_report.semantic_similarity ?? 0) * 100).toFixed(0)}%</span>
                  </div>
                  {selectedProject.latest_similarity_report.repeated_phrases.length > 0 && (
                    <article>
                      <h4>{t.repeatedPhrases}</h4>
                      <ul className="compact-list">
                        {selectedProject.latest_similarity_report.repeated_phrases.map(item => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </article>
                  )}
                  {(selectedProject.latest_similarity_report.reused_entities?.length ?? 0) > 0 && (
                    <article>
                      <h4>{t.reusedEntities}</h4>
                      <div className="entity-risk-list">
                        {selectedProject.latest_similarity_report.reused_entities?.map(item => (
                          <span className="status-pill status-pill-failed" key={item}>{item}</span>
                        ))}
                      </div>
                    </article>
                  )}
                  {(selectedProject.latest_similarity_report.risk_segments?.length ?? 0) > 0 && (
                    <article>
                      <h4>{t.riskSegments}</h4>
                      <div className="risk-segment-list">
                        {selectedProject.latest_similarity_report.risk_segments?.map((segment, index) => (
                          <div className="risk-segment-item" key={`${segment.risk_type}-${segment.draft_index ?? index}`}>
                            <div className="risk-segment-heading">
                              <span className={`status-pill status-pill-${segment.severity === "high" ? "failed" : "warning"}`}>
                                {segment.severity}
                              </span>
                              <span className={`status-pill status-pill-${actionLevelTone(segment.action_level, segment.severity)}`}>
                                {actionLevelLabel(segment.action_level, segment.action_label)}
                              </span>
                              <span className="status-pill status-pill-muted">{riskTypeLabel(segment.risk_type)}</span>
                              <strong>{language === "zh" ? `第 ${segment.draft_index ?? index + 1} 句` : `Sentence ${segment.draft_index ?? index + 1}`}</strong>
                            </div>
                            <p>{segment.draft_excerpt}</p>
                            {segment.source_excerpt && (
                              <small>
                                {language === "zh" ? "来源：" : "Source: "}
                                {segment.source_excerpt}
                              </small>
                            )}
                            <em>{segment.recommendation}</em>
                            {(segment.similarity_reason || segment.rewrite_goal || segment.suggested_rewrite_mode) && (
                              <div className="risk-segment-diagnosis">
                                {segment.similarity_reason && (
                                  <p>
                                    <strong>{language === "zh" ? "相似原因" : "Why similar"}: </strong>
                                    {segment.similarity_reason}
                                  </p>
                                )}
                                {segment.rewrite_goal && (
                                  <p>
                                    <strong>{language === "zh" ? "改写目标" : "Rewrite goal"}: </strong>
                                    {segment.rewrite_goal}
                                  </p>
                                )}
                                {segment.suggested_rewrite_mode && (
                                  <p>
                                    <strong>{language === "zh" ? "建议模式" : "Suggested mode"}: </strong>
                                    {segment.suggested_rewrite_mode}
                                  </p>
                                )}
                                {(segment.must_replace?.length ?? 0) > 0 && (
                                  <p>
                                    <strong>{language === "zh" ? "必须替换" : "Must replace"}: </strong>
                                    {segment.must_replace?.join(" / ")}
                                  </p>
                                )}
                                {(segment.can_keep?.length ?? 0) > 0 && (
                                  <p>
                                    <strong>{language === "zh" ? "可以保留" : "Can keep"}: </strong>
                                    {segment.can_keep?.join(" / ")}
                                  </p>
                                )}
                              </div>
                            )}
                            {latestDraft && (
                              <button
                                className="secondary-action compact-action risk-segment-action"
                                disabled={activeDraftActionId === `${latestDraft.id}:segment:${index}`}
                                onClick={() => void rewriteRiskSegment(selectedProject, latestDraft, index)}
                                type="button"
                              >
                                <FileText aria-hidden="true" size={16} />
                                {t.rewriteSegment}
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                    </article>
                  )}
                  <article>
                    <h4>{language === "zh" ? "改写建议" : "Recommendations"}</h4>
                    <ul className="compact-list">
                      {selectedProject.latest_similarity_report.recommendations.map(item => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </article>
                </div>
              )}
              {(selectedProject.generated_drafts?.length ?? 0) > 0 && (
                <article>
                  {(selectedProject.similarity_report_history?.length ?? 0) > 0 && (
                    <div className="qa-history-panel">
                      <h4>{t.qaHistory}</h4>
                      <div className="qa-history-list">
                        {selectedProject.similarity_report_history?.map(item => (
                          <div className="qa-history-item" key={item.id}>
                            <div>
                              <strong>{item.draft_title}</strong>
                              <small>{item.draft_source || "-"}</small>
                            </div>
                            <span className={`status-pill status-pill-${riskTone(item.risk_level)}`}>{riskLabel(item.risk_level)}</span>
                            <small>{Number(item.text_overlap_percent || 0).toFixed(1)}% {language === "zh" ? "重合" : "overlap"}</small>
                            <small>{language === "zh" ? "复用设定" : "entities"} {item.reused_entity_count}</small>
                            <small>{language === "zh" ? "风险段" : "segments"} {item.risk_segment_count}</small>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  <h4>{language === "zh" ? "草稿版本" : "Draft Versions"}</h4>
                  <div className="draft-version-list">
                    {selectedProject.generated_drafts?.map(draft => (
                      <div className="draft-version-item" key={draft.id}>
                        <button className="draft-version-main" onClick={() => setDraftText(draft.draft_text)} type="button">
                          <span>{draft.title}</span>
                          <small>
                            {draft.source === "inkos" ? "InkOS" : language === "zh" ? "手动" : "Manual"} / {riskLabel(draft.similarity_report.risk_level)} / {draft.status}
                          </small>
                        </button>
                        {draft.inkos_result?.rewrite_comparison && (
                          <div className="draft-rewrite-comparison">
                            <span>
                              {language === "zh" ? "风险" : "Risk"}:{" "}
                              {riskLabel(draft.inkos_result.rewrite_comparison.before.risk_level)} {" -> "}
                              {riskLabel(draft.inkos_result.rewrite_comparison.after.risk_level)}
                            </span>
                            <span>
                              {language === "zh" ? "重合" : "Overlap"}:{" "}
                              {draft.inkos_result.rewrite_comparison.before.text_overlap_percent.toFixed(1)}% {" -> "}
                              {draft.inkos_result.rewrite_comparison.after.text_overlap_percent.toFixed(1)}% (
                              {draft.inkos_result.rewrite_comparison.delta.text_overlap_percent > 0 ? "+" : ""}
                              {draft.inkos_result.rewrite_comparison.delta.text_overlap_percent.toFixed(1)}%)
                            </span>
                            {draft.inkos_result.rewrite_comparison.before.semantic_similarity !== undefined &&
                              draft.inkos_result.rewrite_comparison.after.semantic_similarity !== undefined && (
                                <span>
                                  {language === "zh" ? "语义桥段" : "Semantic"}:{" "}
                                  {(draft.inkos_result.rewrite_comparison.before.semantic_similarity * 100).toFixed(0)}% {" -> "}
                                  {(draft.inkos_result.rewrite_comparison.after.semantic_similarity * 100).toFixed(0)}% (
                                  {(draft.inkos_result.rewrite_comparison.delta.semantic_similarity ?? 0) > 0 ? "+" : ""}
                                  {((draft.inkos_result.rewrite_comparison.delta.semantic_similarity ?? 0) * 100).toFixed(0)}%)
                                </span>
                              )}
                            <span>
                              {language === "zh" ? "风险段" : "Segments"}:{" "}
                              {draft.inkos_result.rewrite_comparison.before.risk_segment_count} {" -> "}
                              {draft.inkos_result.rewrite_comparison.after.risk_segment_count}
                            </span>
                            <span className={`draft-rewrite-gate draft-rewrite-gate-${qualityGateStatusTone(draft.inkos_result.rewrite_comparison.after.quality_gate_status)}`}>
                              {language === "zh" ? "门禁" : "Gate"}:{" "}
                              {qualityGateStatusLabel(draft.inkos_result.rewrite_comparison.before.quality_gate_status)} {" -> "}
                              {qualityGateStatusLabel(draft.inkos_result.rewrite_comparison.after.quality_gate_status)}
                            </span>
                          </div>
                        )}
                        <div className="draft-version-actions">
                          <button className="secondary-action compact-action" onClick={() => void downloadDraft(selectedProject, draft)} type="button">
                            <Download aria-hidden="true" size={16} />
                            {t.draftExport}
                          </button>
                          <button
                            className="secondary-action compact-action"
                            disabled={activeDraftActionId === draft.id}
                            onClick={() => void setDraftStatus(selectedProject, draft, "publishable")}
                            type="button"
                          >
                            {t.markPublishable}
                          </button>
                          <button
                            className="secondary-action compact-action"
                            disabled={activeDraftActionId === draft.id}
                            onClick={() => void setDraftStatus(selectedProject, draft, "needs_revision")}
                            type="button"
                          >
                            {t.markRevision}
                          </button>
                          <button
                            className="primary-action compact-action"
                            disabled={activeDraftActionId === draft.id}
                            onClick={() => void reduceRisk(selectedProject, draft)}
                            type="button"
                          >
                            <ScanSearch aria-hidden="true" size={16} />
                            {t.reduceRisk}
                          </button>
                          <label className="draft-rewrite-select">
                            <select
                              aria-label={t.rewriteDraft}
                              disabled={activeDraftActionId === draft.id}
                              onChange={event =>
                                setRewriteModes(current => ({ ...current, [draft.id]: event.target.value as RewriteMode }))
                              }
                              value={rewriteModes[draft.id] ?? "faster_pacing"}
                            >
                              {rewriteOptions.map(option => (
                                <option key={option.value} value={option.value}>
                                  {option.label}
                                </option>
                              ))}
                            </select>
                          </label>
                          <button
                            className="primary-action compact-action"
                            disabled={activeDraftActionId === draft.id}
                            onClick={() => void rewriteDraft(selectedProject, draft)}
                            type="button"
                          >
                            <FileText aria-hidden="true" size={16} />
                            {t.rewriteDraft}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </article>
              )}
            </div>

            <h3>{t.reference}</h3>
            <pre className="script-box">{selectedProject.reference_markdown}</pre>
          </div>
        ) : (
          <div className="action-empty-state">
            <div>
              <p className="eyebrow">{language === "zh" ? "下一步" : "Next step"}</p>
              <h2>{data.reports.length ? (language === "zh" ? "生成第一个创作包" : "Create the first brief") : nextAction?.label || (language === "zh" ? "先准备源报告" : "Prepare a source report")}</h2>
              <p className="panel-note">{data.reports.length ? t.empty : nextAction?.description || t.empty}</p>
            </div>
            <button
              className="primary-action compact-action"
              disabled={isWorking || !selectedReportId}
              onClick={data.reports.length ? () => void createProject() : () => onRunNextAction?.(nextAction) ?? (onOpenReports ?? onOpenDashboard)?.()}
              type="button"
            >
              {data.reports.length ? (language === "zh" ? "生成创作包" : "Create Brief") : language === "zh" ? "去视频报告" : "Open Reports"}
            </button>
          </div>
        )}
      </section>
    </main>
  );
}
