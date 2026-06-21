import { Archive, ArrowRight, CheckSquare, Download, Filter, PlayCircle, Search, ShieldAlert, ShieldCheck, Square, Star } from "lucide-react";
import { useMemo, useState } from "react";

import { bulkCheckProjectDrafts, bulkExportProjectMarkdown, bulkRunProjectInkos, bulkUpdateProjectStatus, favoriteStructureTemplate, unfavoriteStructureTemplate, updateStructureTemplate } from "../api";
import type { CreationPipelineNextAction, DashboardData, FavoriteStructureTemplate, ImitationProjectSummary, Language } from "../types";

interface ProjectLibraryProps {
  data: DashboardData;
  language: Language;
  nextAction?: CreationPipelineNextAction;
  onDashboardChanged?: () => void | Promise<void>;
  onOpenCreation?: () => void;
  onOpenProject: (projectId: string) => void;
  onRunNextAction?: (action?: CreationPipelineNextAction) => void;
  onUseTemplate?: (templateId: string) => void;
}

const copy = {
  zh: {
    all: "全部",
    allRisks: "全部风险",
    batchDiscard: "标记废弃",
    batchExport: "导出选中",
    batchNeedsReview: "标记待审查",
    batchNeedsRevision: "标记待修改",
    batchPublishable: "标记可发布",
    batchSummary: "已选择 {count} 个项目",
    board: "看板",
    channel: "频道",
    clearSelection: "清空选择",
    continue: "继续处理",
    direction: "方向",
    draft: "草稿",
    empty: "还没有创作项目。先从视频报告进入创作转化工坊生成创作包。",
    filters: "筛选",
    highRisk: "高风险",
    intro: "汇总所有创作项目、生成稿状态和最新风险，方便从待修改稿件继续推进到可发布稿。",
    latestRisk: "最新风险",
    latestGate: "质量门禁",
    list: "列表",
    risk: "风险",
    templateMetrics: "质量指标",
    templateReuse: "复用",
    templatePassRate: "通过率",
    templateAverageRisk: "平均风险",
    templateAverageOverlap: "平均重合",
    templateFilter: "模板标签/题材",
    templateName: "模板名称",
    templateNotes: "备注",
    templateTags: "标签",
    templateTopics: "适用题材",
    templateCases: "成功案例",
    templateSave: "保存模板",
    templateUse: "复用模板",
    templateQualityFilter: "模板质量",
    templateQualityAll: "全部模板",
    templateQualityProven: "高通过率",
    templateQualityReused: "已有复用",
    templateQualityLowRisk: "低风险",
    templateQualityHighRisk: "高风险",
    templateSort: "模板排序",
    templateSortPassRate: "通过率",
    templateSortReuse: "复用次数",
    templateSortRisk: "风险最低",
    templateSortOverlap: "重合最低",
    search: "搜索来源/频道/方向",
    select: "选择",
    selectAllVisible: "选择当前结果",
    needsWork: "待修改",
    failedGate: "门禁未通过",
    noMatch: "没有符合筛选条件的项目。",
    overlap: "文本重合",
    publishable: "可发布",
    referenceOnly: "仅创作包",
    sort: "排序",
    sortNewest: "最新创建",
    sortUpdated: "最新处理",
    sortRisk: "风险最高",
    sortOverlap: "重合最高",
    sortDrafts: "草稿最多",
    sortFavorites: "模板优先",
    source: "来源",
    templateEmpty: "还没有收藏的结构模板。可以从高质量项目里收藏一套复用结构。",
    templateFavorite: "收藏模板",
    templateSaved: "已收藏",
    templates: "结构模板",
    status: "状态",
    topic: "题材",
    title: "创作项目库"
  },
  en: {
    all: "All",
    allRisks: "All risks",
    batchDiscard: "Discard",
    batchExport: "Export selected",
    batchNeedsReview: "Needs review",
    batchNeedsRevision: "Needs revision",
    batchPublishable: "Publishable",
    batchSummary: "{count} projects selected",
    batchInkos: "Run InkOS",
    board: "Board",
    channel: "Channel",
    clearSelection: "Clear selection",
    continue: "Continue",
    direction: "Direction",
    draft: "Drafts",
    empty: "No creation projects yet. Create a reference package from a video report first.",
    filters: "Filters",
    highRisk: "High Risk",
    intro: "Collect creation projects, draft status, and latest risk so drafts can move from revision to publishable.",
    latestRisk: "Latest Risk",
    latestGate: "Quality Gate",
    list: "List",
    risk: "Risk",
    templateMetrics: "Quality Metrics",
    templateReuse: "Reuse",
    templatePassRate: "Pass Rate",
    templateAverageRisk: "Avg Risk",
    templateAverageOverlap: "Avg Overlap",
    templateFilter: "Template tag/topic",
    templateName: "Template Name",
    templateNotes: "Notes",
    templateTags: "Tags",
    templateTopics: "Topics",
    templateCases: "Success Cases",
    templateSave: "Save Template",
    templateUse: "Use Template",
    templateQualityFilter: "Template Quality",
    templateQualityAll: "All Templates",
    templateQualityProven: "High Pass Rate",
    templateQualityReused: "Reused",
    templateQualityLowRisk: "Low Risk",
    templateQualityHighRisk: "High Risk",
    templateSort: "Template Sort",
    templateSortPassRate: "Pass Rate",
    templateSortReuse: "Reuse Count",
    templateSortRisk: "Lowest Risk",
    templateSortOverlap: "Lowest Overlap",
    search: "Search source/channel/direction",
    select: "Select",
    selectAllVisible: "Select visible",
    needsWork: "Needs Work",
    failedGate: "Failed Gate",
    noMatch: "No projects match the current filters.",
    overlap: "Text overlap",
    publishable: "Publishable",
    priority: "Priority",
    priorityUrgent: "Urgent",
    priorityHigh: "High",
    priorityMedium: "Medium",
    priorityLow: "Low",
    referenceOnly: "Reference Only",
    sort: "Sort",
    sortPriority: "Production Priority",
    sortNewest: "Newest",
    sortUpdated: "Recently Updated",
    sortRisk: "Highest Risk",
    sortOverlap: "Highest Overlap",
    sortDrafts: "Most Drafts",
    sortFavorites: "Templates First",
    source: "Source",
    templateEmpty: "No saved structure templates yet. Favorite reusable structures from high-quality projects.",
    templateFavorite: "Favorite Template",
    templateSaved: "Saved",
    templates: "Structure Templates",
    status: "Status",
    topic: "Topic",
    title: "Project Library"
  }
} satisfies Record<Language, Record<string, string>>;

type StatusFilter = "all" | "reference" | "needs_work" | "publishable" | "high_risk" | "failed_gate" | "urgent";
type RiskFilter = "all" | "high" | "medium" | "low";
type SortOption = "newest" | "updated" | "priority" | "risk" | "overlap" | "drafts" | "favorites";
type ViewMode = "list" | "board";
type ProductionStage = "reference" | "needs_review" | "needs_revision" | "publishable" | "discarded";
type TemplateQualityFilter = "all" | "proven" | "reused" | "low_risk" | "high_risk";
type TemplateSortOption = "pass_rate" | "reuse" | "risk" | "overlap";

const productionStages: ProductionStage[] = ["reference", "needs_review", "needs_revision", "publishable", "discarded"];

function projectMatches(project: ImitationProjectSummary, filter: StatusFilter) {
  if (filter === "all") return true;
  if (filter === "reference") return project.draft_count === 0;
  if (filter === "publishable") return project.latest_draft_status === "publishable";
  if (filter === "high_risk") return project.latest_risk_level === "high";
  if (filter === "failed_gate") return ["needs_revision", "blocked"].includes(project.latest_quality_gate_status || "");
  if (filter === "urgent") return project.production_priority === "urgent";
  if (filter === "needs_work") {
    return (
      ["needs_review", "needs_revision"].includes(project.latest_draft_status) ||
      ["needs_revision", "blocked"].includes(project.latest_quality_gate_status || "")
    );
  }
  return ["needs_review", "needs_revision"].includes(project.latest_draft_status);
}

function qualityGateLabel(project: ImitationProjectSummary, language: Language) {
  const status = project.latest_quality_gate_status || "";
  if (!status) return "-";
  if (status === "pass") return language === "zh" ? "通过" : "Pass";
  if (status === "blocked") return language === "zh" ? "阻断" : "Blocked";
  if (status === "needs_revision") return language === "zh" ? "需修改" : "Needs revision";
  return status;
}

function qualityGateTone(status = "") {
  if (status === "pass") return "ok";
  if (status === "blocked") return "failed";
  if (status === "needs_revision") return "warning";
  return "muted";
}

function dateValue(value = "") {
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? 0 : time;
}

function priorityRank(priority = "") {
  return { urgent: 4, high: 3, medium: 2, low: 1 }[priority as "urgent" | "high" | "medium" | "low"] ?? 0;
}

function sortedBy(projects: ImitationProjectSummary[], sort: SortOption) {
  const riskRank: Record<string, number> = { high: 3, medium: 2, low: 1 };
  return [...projects].sort((left, right) => {
    if (sort === "updated") return dateValue(right.updated_at || right.created_at) - dateValue(left.updated_at || left.created_at);
    if (sort === "priority") return priorityRank(right.production_priority) - priorityRank(left.production_priority);
    if (sort === "risk") return (riskRank[right.latest_risk_level] || 0) - (riskRank[left.latest_risk_level] || 0);
    if (sort === "overlap") return Number(right.text_overlap_percent || 0) - Number(left.text_overlap_percent || 0);
    if (sort === "drafts") return Number(right.draft_count || 0) - Number(left.draft_count || 0);
    if (sort === "favorites") return Number(Boolean(right.template_favorited)) - Number(Boolean(left.template_favorited));
    return dateValue(right.created_at) - dateValue(left.created_at);
  });
}

function priorityLabel(priority: string | undefined, language: Language) {
  if (priority === "urgent") return language === "zh" ? "立即处理" : "Urgent";
  if (priority === "high") return language === "zh" ? "高优先" : "High";
  if (priority === "medium") return language === "zh" ? "中优先" : "Medium";
  if (priority === "low") return language === "zh" ? "低优先" : "Low";
  return priority || "-";
}

function priorityTone(priority = "") {
  if (priority === "urgent") return "failed";
  if (priority === "high") return "warning";
  if (priority === "medium") return "muted";
  if (priority === "low") return "ok";
  return "muted";
}

function statusLabel(project: ImitationProjectSummary, language: Language) {
  if (!project.draft_count) return language === "zh" ? "仅参考包" : "Reference only";
  if (project.latest_draft_status === "publishable") return language === "zh" ? "可发布" : "Publishable";
  if (project.latest_draft_status === "needs_revision") return language === "zh" ? "待修改" : "Needs revision";
  if (project.latest_draft_status === "needs_review") return language === "zh" ? "待审查" : "Needs review";
  if (project.latest_draft_status === "discarded") return language === "zh" ? "已废弃" : "Discarded";
  return project.latest_draft_status || "-";
}

function productionStage(project: ImitationProjectSummary): ProductionStage {
  const stage = project.production_stage || "";
  if (productionStages.includes(stage as ProductionStage)) return stage as ProductionStage;
  if (!project.draft_count) return "reference";
  if (project.latest_draft_status === "discarded") return "discarded";
  if (project.latest_draft_status === "publishable") return "publishable";
  if (project.latest_draft_status === "needs_revision" || project.latest_risk_level === "high") return "needs_revision";
  return "needs_review";
}

function productionStageLabel(stage: ProductionStage, language: Language) {
  const labels: Record<ProductionStage, { zh: string; en: string }> = {
    reference: { zh: "参考包", en: "Reference" },
    needs_review: { zh: "待审查", en: "Review" },
    needs_revision: { zh: "待修改", en: "Revision" },
    publishable: { zh: "可发布", en: "Publishable" },
    discarded: { zh: "已废弃", en: "Discarded" }
  };
  return labels[stage][language];
}

function riskTone(risk: string) {
  if (risk === "high") return "failed";
  if (risk === "medium") return "warning";
  if (risk === "low") return "ok";
  return "muted";
}

function riskMatches(project: ImitationProjectSummary, filter: RiskFilter) {
  return filter === "all" || project.latest_risk_level === filter;
}

function queryMatches(project: ImitationProjectSummary, query: string) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return true;
  return [
    project.name,
    project.source_video_title,
    project.source_video_url,
    project.source_channel_title,
    project.source_topic_type,
    project.direction,
    project.output_type
  ]
    .join(" ")
    .toLowerCase()
    .includes(normalized);
}

function splitList(value: string) {
  return value
    .split(/[,，\n]+/)
    .map(item => item.trim())
    .filter(Boolean);
}

function joinList(value: string[] | undefined) {
  return (value ?? []).join(", ");
}

function templateMatches(template: FavoriteStructureTemplate, query: string) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return true;
  return [
    template.name,
    template.source_topic_type,
    template.output_type,
    template.notes,
    ...(template.tags ?? []),
    ...(template.applicable_topics ?? []),
    ...(template.success_cases ?? [])
  ]
    .join(" ")
    .toLowerCase()
    .includes(normalized);
}

function templateQualityMatches(template: FavoriteStructureTemplate, filter: TemplateQualityFilter) {
  if (filter === "all") return true;
  if (filter === "proven") return Number(template.publishable_rate || 0) >= 60;
  if (filter === "reused") return Number(template.reuse_count || 0) > 0;
  if (filter === "low_risk") return template.average_risk_level === "low";
  if (filter === "high_risk") return template.average_risk_level === "high";
  return true;
}

function sortedTemplates(templates: FavoriteStructureTemplate[], sort: TemplateSortOption) {
  const riskRank: Record<string, number> = { low: 1, medium: 2, high: 3 };
  return [...templates].sort((left, right) => {
    if (sort === "reuse") return Number(right.reuse_count || 0) - Number(left.reuse_count || 0);
    if (sort === "risk") return (riskRank[left.average_risk_level || ""] || 9) - (riskRank[right.average_risk_level || ""] || 9);
    if (sort === "overlap") return Number(left.average_text_overlap_percent || 0) - Number(right.average_text_overlap_percent || 0);
    return Number(right.publishable_rate || 0) - Number(left.publishable_rate || 0);
  });
}

export default function ProjectLibrary({ data, language, nextAction, onDashboardChanged, onOpenCreation, onOpenProject, onRunNextAction, onUseTemplate }: ProjectLibraryProps) {
  const t = copy[language];
  const optionalCopy = t as Record<string, string>;
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [riskFilter, setRiskFilter] = useState<RiskFilter>("all");
  const [sort, setSort] = useState<SortOption>("updated");
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [query, setQuery] = useState("");
  const [activeTemplateProjectId, setActiveTemplateProjectId] = useState("");
  const [selectedProjectIds, setSelectedProjectIds] = useState<string[]>([]);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkMessage, setBulkMessage] = useState("");
  const [templateQuery, setTemplateQuery] = useState("");
  const [templateQualityFilter, setTemplateQualityFilter] = useState<TemplateQualityFilter>("all");
  const [templateSort, setTemplateSort] = useState<TemplateSortOption>("pass_rate");
  const [editingTemplates, setEditingTemplates] = useState<Record<string, { name: string; tags: string; notes: string; applicable_topics: string; success_cases: string }>>({});
  const [savingTemplateId, setSavingTemplateId] = useState("");
  const projects = data.imitation_project_summaries ?? [];
  const templates = data.favorite_structure_templates ?? [];
  const filteredTemplates = useMemo(
    () => sortedTemplates(templates.filter(template => templateMatches(template, templateQuery) && templateQualityMatches(template, templateQualityFilter)), templateSort),
    [templateQualityFilter, templateQuery, templateSort, templates]
  );
  const filteredProjects = useMemo(
    () => sortedBy(projects.filter(project => projectMatches(project, filter) && riskMatches(project, riskFilter) && queryMatches(project, query)), sort),
    [filter, projects, query, riskFilter, sort]
  );
  const projectsByStage = useMemo(
    () =>
      productionStages.reduce<Record<ProductionStage, ImitationProjectSummary[]>>(
        (groups, stage) => {
          groups[stage] = filteredProjects.filter(project => productionStage(project) === stage);
          return groups;
        },
        {
          reference: [],
          needs_review: [],
          needs_revision: [],
          publishable: [],
          discarded: []
        }
      ),
    [filteredProjects]
  );
  const selectedVisibleCount = filteredProjects.filter(project => selectedProjectIds.includes(project.id)).length;
  const hasSelection = selectedProjectIds.length > 0;
  const filters: { value: StatusFilter; label: string }[] = [
    { value: "all", label: t.all },
    { value: "reference", label: t.referenceOnly },
    { value: "needs_work", label: t.needsWork },
    { value: "failed_gate", label: t.failedGate },
    { value: "urgent", label: language === "zh" ? "立即处理" : "Urgent" },
    { value: "publishable", label: t.publishable },
    { value: "high_risk", label: t.highRisk }
  ];
  const sortOptions: { value: SortOption; label: string }[] = [
    { value: "updated", label: t.sortUpdated },
    { value: "priority", label: optionalCopy.sortPriority || (language === "zh" ? "生产优先" : "Production Priority") },
    { value: "newest", label: t.sortNewest },
    { value: "risk", label: t.sortRisk },
    { value: "overlap", label: t.sortOverlap },
    { value: "drafts", label: t.sortDrafts },
    { value: "favorites", label: t.sortFavorites }
  ];
  const riskFilters: { value: RiskFilter; label: string }[] = [
    { value: "all", label: t.allRisks },
    { value: "high", label: t.highRisk },
    { value: "medium", label: language === "zh" ? "中风险" : "Medium" },
    { value: "low", label: language === "zh" ? "低风险" : "Low" }
  ];
  const templateQualityFilters: { value: TemplateQualityFilter; label: string }[] = [
    { value: "all", label: t.templateQualityAll },
    { value: "proven", label: t.templateQualityProven },
    { value: "reused", label: t.templateQualityReused },
    { value: "low_risk", label: t.templateQualityLowRisk },
    { value: "high_risk", label: t.templateQualityHighRisk }
  ];
  const templateSortOptions: { value: TemplateSortOption; label: string }[] = [
    { value: "pass_rate", label: t.templateSortPassRate },
    { value: "reuse", label: t.templateSortReuse },
    { value: "risk", label: t.templateSortRisk },
    { value: "overlap", label: t.templateSortOverlap }
  ];

  const toggleTemplate = async (project: ImitationProjectSummary) => {
    setActiveTemplateProjectId(project.id);
    try {
      if (project.template_favorited) {
        await unfavoriteStructureTemplate(project.id);
      } else {
        await favoriteStructureTemplate(project.id);
      }
      await onDashboardChanged?.();
    } finally {
      setActiveTemplateProjectId("");
    }
  };

  const toggleProjectSelection = (projectId: string) => {
    setBulkMessage("");
    setSelectedProjectIds(current =>
      current.includes(projectId) ? current.filter(item => item !== projectId) : [...current, projectId]
    );
  };

  const selectVisibleProjects = () => {
    setBulkMessage("");
    const visibleIds = filteredProjects.map(project => project.id);
    setSelectedProjectIds(current => Array.from(new Set([...current, ...visibleIds])));
  };

  const clearSelection = () => {
    setBulkMessage("");
    setSelectedProjectIds([]);
  };

  const runBulkStatus = async (status: string) => {
    if (!selectedProjectIds.length) return;
    setBulkBusy(true);
    setBulkMessage("");
    try {
      const result = await bulkUpdateProjectStatus(selectedProjectIds, status);
      setBulkMessage(
        language === "zh"
          ? `已更新 ${result.updated_count} 个项目，跳过 ${result.skipped_count} 个。`
          : `Updated ${result.updated_count} projects, skipped ${result.skipped_count}.`
      );
      await onDashboardChanged?.();
    } catch (error) {
      setBulkMessage(error instanceof Error ? error.message : language === "zh" ? "批量更新失败。" : "Bulk update failed.");
    } finally {
      setBulkBusy(false);
    }
  };

  const runBulkExport = async () => {
    if (!selectedProjectIds.length) return;
    setBulkBusy(true);
    setBulkMessage("");
    try {
      const result = await bulkExportProjectMarkdown(selectedProjectIds);
      const blob = new Blob([result.markdown], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = result.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setBulkMessage(
        language === "zh"
          ? `已导出 ${result.exported_count} 个项目，跳过 ${result.skipped_count} 个。`
          : `Exported ${result.exported_count} projects, skipped ${result.skipped_count}.`
      );
    } catch (error) {
      setBulkMessage(error instanceof Error ? error.message : language === "zh" ? "批量导出失败。" : "Bulk export failed.");
    } finally {
      setBulkBusy(false);
    }
  };

  const runBulkCheck = async () => {
    if (!selectedProjectIds.length) return;
    setBulkBusy(true);
    setBulkMessage("");
    try {
      const result = await bulkCheckProjectDrafts(selectedProjectIds);
      setBulkMessage(
        language === "zh"
          ? `已重新检测 ${result.checked_count} 个项目，跳过 ${result.skipped_count} 个。`
          : `Checked ${result.checked_count} projects, skipped ${result.skipped_count}.`
      );
      await onDashboardChanged?.();
    } catch (error) {
      setBulkMessage(error instanceof Error ? error.message : language === "zh" ? "批量风险检测失败。" : "Bulk risk check failed.");
    } finally {
      setBulkBusy(false);
    }
  };

  const runBulkInkos = async () => {
    if (!selectedProjectIds.length) return;
    setBulkBusy(true);
    setBulkMessage("");
    try {
      const result = await bulkRunProjectInkos(selectedProjectIds);
      setBulkMessage(
        language === "zh"
          ? `已生成 ${result.generated_count} 个草稿，跳过 ${result.skipped_count} 个，失败 ${result.failed_count} 个。`
          : `Generated ${result.generated_count} drafts, skipped ${result.skipped_count}, failed ${result.failed_count}.`
      );
      await onDashboardChanged?.();
    } catch (error) {
      setBulkMessage(error instanceof Error ? error.message : language === "zh" ? "批量 InkOS 生成失败。" : "Bulk InkOS run failed.");
    } finally {
      setBulkBusy(false);
    }
  };

  const templateDraft = (template: FavoriteStructureTemplate) =>
    editingTemplates[template.id] ?? {
      applicable_topics: joinList(template.applicable_topics),
      name: template.name,
      notes: template.notes ?? "",
      success_cases: joinList(template.success_cases),
      tags: joinList(template.tags)
    };

  const updateTemplateDraft = (template: FavoriteStructureTemplate, patch: Partial<ReturnType<typeof templateDraft>>) => {
    const current = templateDraft(template);
    setEditingTemplates(items => ({ ...items, [template.id]: { ...current, ...patch } }));
  };

  const saveTemplate = async (template: FavoriteStructureTemplate) => {
    const draft = templateDraft(template);
    setSavingTemplateId(template.id);
    setBulkMessage("");
    try {
      await updateStructureTemplate(template.id, {
        applicable_topics: splitList(draft.applicable_topics),
        name: draft.name,
        notes: draft.notes,
        success_cases: splitList(draft.success_cases),
        tags: splitList(draft.tags)
      });
      setBulkMessage(language === "zh" ? "结构模板已更新。" : "Structure template updated.");
      setEditingTemplates(items => {
        const next = { ...items };
        delete next[template.id];
        return next;
      });
      await onDashboardChanged?.();
    } catch (error) {
      setBulkMessage(error instanceof Error ? error.message : language === "zh" ? "模板保存失败。" : "Template save failed.");
    } finally {
      setSavingTemplateId("");
    }
  };

  return (
    <main className="app-shell workspace-page">
      <section className="page-intro" aria-labelledby="project-library-title">
        <p className="eyebrow">{language === "zh" ? "项目库" : "Library"}</p>
        <h1 id="project-library-title">{t.title}</h1>
        <p className="hero-summary">{t.intro}</p>
      </section>

      <section className="project-library-toolbar">
        <div className="project-library-filter-block">
          <p className="eyebrow">{t.filters}</p>
          <div className="segmented-control" role="tablist" aria-label={t.filters}>
            {filters.map(item => (
              <button
                aria-selected={filter === item.value}
                className={filter === item.value ? "segmented-control-item segmented-control-item-active" : "segmented-control-item"}
                key={item.value}
                onClick={() => setFilter(item.value)}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
        <div className="project-library-filter-block">
          <p className="eyebrow">{t.risk}</p>
          <div className="segmented-control" role="tablist" aria-label={t.risk}>
            {riskFilters.map(item => (
              <button
                aria-selected={riskFilter === item.value}
                className={riskFilter === item.value ? "segmented-control-item segmented-control-item-active" : "segmented-control-item"}
                key={item.value}
                onClick={() => setRiskFilter(item.value)}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
        <label className="project-library-search">
          <Search aria-hidden="true" size={18} />
          <input aria-label={t.search} onChange={event => setQuery(event.target.value)} placeholder={t.search} value={query} />
        </label>
        <label className="project-library-sort">
          <span>{t.sort}</span>
          <select onChange={event => setSort(event.target.value as SortOption)} value={sort}>
            {sortOptions.map(item => (
              <option key={item.value} value={item.value}>{item.label}</option>
            ))}
          </select>
        </label>
        <div className="project-library-filter-block">
          <p className="eyebrow">{language === "zh" ? "视图" : "View"}</p>
          <div className="segmented-control" role="tablist" aria-label={language === "zh" ? "视图" : "View"}>
            <button
              aria-selected={viewMode === "list"}
              className={viewMode === "list" ? "segmented-control-item segmented-control-item-active" : "segmented-control-item"}
              onClick={() => setViewMode("list")}
              type="button"
            >
              {t.list}
            </button>
            <button
              aria-selected={viewMode === "board"}
              className={viewMode === "board" ? "segmented-control-item segmented-control-item-active" : "segmented-control-item"}
              onClick={() => setViewMode("board")}
              type="button"
            >
              {t.board}
            </button>
          </div>
        </div>
        <Filter aria-hidden="true" size={22} />
      </section>

      {!!projects.length && (
        <section className="project-library-bulkbar" aria-label={language === "zh" ? "批量操作" : "Bulk actions"}>
          <div>
            <strong>{t.batchSummary.replace("{count}", String(selectedProjectIds.length))}</strong>
            <span>
              {selectedVisibleCount}/{filteredProjects.length} {language === "zh" ? "个当前结果已选择" : "visible selected"}
            </span>
          </div>
          <div className="project-library-bulk-actions">
            <button className="secondary-action compact-action" disabled={!filteredProjects.length || bulkBusy} onClick={selectVisibleProjects} type="button">
              <CheckSquare aria-hidden="true" size={16} />
              {t.selectAllVisible}
            </button>
            <button className="secondary-action compact-action" disabled={!hasSelection || bulkBusy} onClick={clearSelection} type="button">
              <Square aria-hidden="true" size={16} />
              {t.clearSelection}
            </button>
            <button className="secondary-action compact-action" disabled={!hasSelection || bulkBusy} onClick={() => void runBulkStatus("needs_review")} type="button">
              {t.batchNeedsReview}
            </button>
            <button className="secondary-action compact-action" disabled={!hasSelection || bulkBusy} onClick={() => void runBulkStatus("needs_revision")} type="button">
              {t.batchNeedsRevision}
            </button>
            <button className="secondary-action compact-action" disabled={!hasSelection || bulkBusy} onClick={() => void runBulkStatus("publishable")} type="button">
              {t.batchPublishable}
            </button>
            <button className="secondary-action compact-action" disabled={!hasSelection || bulkBusy} onClick={() => void runBulkStatus("discarded")} type="button">
              {t.batchDiscard}
            </button>
            <button className="secondary-action compact-action" disabled={!hasSelection || bulkBusy} onClick={() => void runBulkCheck()} type="button">
              <ShieldCheck aria-hidden="true" size={16} />
              {language === "zh" ? "批量风险检测" : "Check risk"}
            </button>
            <button className="secondary-action compact-action" disabled={!hasSelection || bulkBusy} onClick={() => void runBulkInkos()} type="button">
              <PlayCircle aria-hidden="true" size={16} />
              {language === "zh" ? "批量生成草稿" : "Run InkOS"}
            </button>
            <button className="primary-action compact-action" disabled={!hasSelection || bulkBusy} onClick={() => void runBulkExport()} type="button">
              <Download aria-hidden="true" size={16} />
              {t.batchExport}
            </button>
          </div>
          {bulkMessage && <p className="project-library-bulk-message">{bulkMessage}</p>}
        </section>
      )}

      {!projects.length && (
        <section className="panel action-empty-state">
          <div>
            <p className="eyebrow">{language === "zh" ? "下一步" : "Next step"}</p>
            <h2>{nextAction?.label || (language === "zh" ? "先生成创作项目" : "Create a project first")}</h2>
            <p className="panel-note">{nextAction?.description || t.empty}</p>
          </div>
          <button className="primary-action compact-action" onClick={() => onRunNextAction?.(nextAction) ?? onOpenCreation?.()} type="button">
            {nextAction?.target_view === "imitation-factory"
              ? nextAction.label
              : language === "zh"
                ? "去创作转化工坊"
                : "Open Creation Lab"}
          </button>
        </section>
      )}
      {projects.length > 0 && !filteredProjects.length && <p className="panel panel-note">{t.noMatch}</p>}

      {viewMode === "list" && (
        <section className="project-library-grid" aria-label={t.title}>
          {filteredProjects.map(project => (
          <article className="project-library-card" key={project.id}>
            <div className="project-library-card-header">
              <div>
                <p className="eyebrow">{project.output_type || "-"}</p>
                <h2>{project.name}</h2>
              </div>
              {project.latest_risk_level === "high" ? <ShieldAlert aria-hidden="true" size={22} /> : <ShieldCheck aria-hidden="true" size={22} />}
            </div>
            <div className="project-priority-strip">
              <span className={`status-pill status-pill-${priorityTone(project.production_priority)}`}>
                {priorityLabel(project.production_priority, language)}
              </span>
              <p>{project.production_priority_reason || project.recommended_next_action || "-"}</p>
            </div>
            <button
              className={selectedProjectIds.includes(project.id) ? "project-library-select project-library-select-active" : "project-library-select"}
              onClick={() => toggleProjectSelection(project.id)}
              type="button"
            >
              {selectedProjectIds.includes(project.id) ? <CheckSquare aria-hidden="true" size={17} /> : <Square aria-hidden="true" size={17} />}
              {t.select}
            </button>

            <dl className="project-library-fields">
              <div>
                <dt>{t.source}</dt>
                <dd>{project.source_video_title || project.source_video_url || "-"}</dd>
              </div>
              <div>
                <dt>{t.channel}</dt>
                <dd>{project.source_channel_title || "-"}</dd>
              </div>
              <div>
                <dt>{t.topic}</dt>
                <dd>{project.source_topic_type || "-"}</dd>
              </div>
              <div>
                <dt>{t.direction}</dt>
                <dd>{project.direction || "-"}</dd>
              </div>
              <div>
                <dt>{t.status}</dt>
                <dd><span className="status-pill status-pill-muted">{statusLabel(project, language)}</span></dd>
              </div>
              <div>
                <dt>{t.latestRisk}</dt>
                <dd><span className={`status-pill status-pill-${riskTone(project.latest_risk_level)}`}>{project.latest_risk_level || "-"}</span></dd>
              </div>
              <div>
                <dt>{t.latestGate}</dt>
                <dd><span className={`status-pill status-pill-${qualityGateTone(project.latest_quality_gate_status)}`}>{qualityGateLabel(project, language)}</span></dd>
              </div>
              <div>
                <dt>{optionalCopy.priority || (language === "zh" ? "优先级" : "Priority")}</dt>
                <dd>{project.recommended_next_action || "-"}</dd>
              </div>
              <div>
                <dt>{t.draft}</dt>
                <dd>{project.draft_count}</dd>
              </div>
              <div>
                <dt>{t.overlap}</dt>
                <dd>{Number(project.text_overlap_percent || 0).toFixed(1)}%</dd>
              </div>
            </dl>
            <button className="primary-action compact-action project-library-open" onClick={() => onOpenProject(project.id)} type="button">
              <ArrowRight aria-hidden="true" size={18} />
              {t.continue}
            </button>
            <button
              className={project.template_favorited ? "secondary-action compact-action project-library-open template-action-active" : "secondary-action compact-action project-library-open"}
              disabled={activeTemplateProjectId === project.id}
              onClick={() => void toggleTemplate(project)}
              type="button"
            >
              <Star aria-hidden="true" size={18} />
              {project.template_favorited ? t.templateSaved : t.templateFavorite}
            </button>
          </article>
          ))}
        </section>
      )}

      {viewMode === "board" && (
        <section className="project-kanban" aria-label={language === "zh" ? "生产看板" : "Production board"}>
          {productionStages.map(stage => (
            <div className="project-kanban-column" key={stage}>
              <div className="project-kanban-column-header">
                <h2>{productionStageLabel(stage, language)}</h2>
                <span>{projectsByStage[stage].length}</span>
              </div>
              <div className="project-kanban-list">
                {projectsByStage[stage].map(project => (
                  <article className="project-kanban-card" key={project.id}>
                    <button
                      className={selectedProjectIds.includes(project.id) ? "project-library-select project-library-select-active" : "project-library-select"}
                      onClick={() => toggleProjectSelection(project.id)}
                      type="button"
                    >
                      {selectedProjectIds.includes(project.id) ? <CheckSquare aria-hidden="true" size={17} /> : <Square aria-hidden="true" size={17} />}
                      {t.select}
                    </button>
                    <div>
                      <p className="eyebrow">{project.output_type || "-"}</p>
                      <h3>{project.name}</h3>
                    </div>
                    <p>{project.source_video_title || project.source_video_url || "-"}</p>
                    <div className="project-kanban-meta">
                      <span className={`status-pill status-pill-${priorityTone(project.production_priority)}`}>{priorityLabel(project.production_priority, language)}</span>
                      <span className={`status-pill status-pill-${riskTone(project.latest_risk_level)}`}>{project.latest_risk_level || "-"}</span>
                      <span className={`status-pill status-pill-${qualityGateTone(project.latest_quality_gate_status)}`}>{qualityGateLabel(project, language)}</span>
                      <span>{Number(project.text_overlap_percent || 0).toFixed(1)}%</span>
                    </div>
                    {project.recommended_next_action && <p className="project-kanban-action">{project.recommended_next_action}</p>}
                    <button className="primary-action compact-action project-library-open" onClick={() => onOpenProject(project.id)} type="button">
                      <ArrowRight aria-hidden="true" size={18} />
                      {t.continue}
                    </button>
                  </article>
                ))}
                {!projectsByStage[stage].length && <p className="project-kanban-empty">-</p>}
              </div>
            </div>
          ))}
        </section>
      )}

      {!!projects.length && (
        <section className="panel project-library-summary">
          <Archive aria-hidden="true" size={22} />
          <span>{data.pending_drafts_count ?? 0} {t.needsWork}</span>
          <span>{data.publishable_drafts_count ?? 0} {t.publishable}</span>
        </section>
      )}

      <section className="panel project-template-library" aria-label={t.templates}>
        <div className="panel-heading">
          <div>
            <p className="eyebrow">{t.templates}</p>
            <h2>{t.templates}</h2>
          </div>
          <Archive aria-hidden="true" size={22} />
        </div>
        {!!templates.length && (
          <div className="template-library-toolbar">
            <label className="project-library-search template-library-search">
              <Search aria-hidden="true" size={18} />
              <input aria-label={t.templateFilter} onChange={event => setTemplateQuery(event.target.value)} placeholder={t.templateFilter} value={templateQuery} />
            </label>
            <label className="project-library-sort">
              <span>{t.templateQualityFilter}</span>
              <select onChange={event => setTemplateQualityFilter(event.target.value as TemplateQualityFilter)} value={templateQualityFilter}>
                {templateQualityFilters.map(item => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </label>
            <label className="project-library-sort">
              <span>{t.templateSort}</span>
              <select onChange={event => setTemplateSort(event.target.value as TemplateSortOption)} value={templateSort}>
                {templateSortOptions.map(item => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </label>
          </div>
        )}
        {!templates.length && (
          <div className="action-empty-state action-empty-state-inline">
            <p className="panel-note">{t.templateEmpty}</p>
            <button className="secondary-action compact-action" disabled={!projects.length} onClick={onOpenCreation} type="button">
              {language === "zh" ? "查看创作项目" : "Open Projects"}
            </button>
          </div>
        )}
        {!!templates.length && (
          <>
          {!filteredTemplates.length && <p className="panel-note">{t.noMatch}</p>}
          <div className="template-library-list">
            {filteredTemplates.map(template => {
              const draft = templateDraft(template);
              return (
              <article className="template-library-item" key={template.id}>
                <div>
                  <p className="eyebrow">{template.output_type || template.source_topic_type || "-"}</p>
                  <label className="template-edit-field">
                    <span>{t.templateName}</span>
                    <input onChange={event => updateTemplateDraft(template, { name: event.target.value })} value={draft.name} />
                  </label>
                </div>
                <div className="template-metrics" aria-label={t.templateMetrics}>
                  <span>{t.templateReuse} {template.reuse_count ?? 0}</span>
                  <span>{t.templatePassRate} {Number(template.publishable_rate || 0).toFixed(1)}%</span>
                  <span>{t.templateAverageRisk} {template.average_risk_level || "-"}</span>
                  <span>{t.templateAverageOverlap} {Number(template.average_text_overlap_percent || 0).toFixed(1)}%</span>
                </div>
                {(template.recommendation_summary || template.recommended_usage) && (
                  <div className="template-recommendation">
                    {template.recommendation_summary && <p>{template.recommendation_summary}</p>}
                    {template.recommended_usage && <small>{template.recommended_usage}</small>}
                  </div>
                )}
                <div className="template-edit-grid">
                  <label className="template-edit-field">
                    <span>{t.templateTags}</span>
                    <input onChange={event => updateTemplateDraft(template, { tags: event.target.value })} value={draft.tags} />
                  </label>
                  <label className="template-edit-field">
                    <span>{t.templateTopics}</span>
                    <input onChange={event => updateTemplateDraft(template, { applicable_topics: event.target.value })} value={draft.applicable_topics} />
                  </label>
                </div>
                <label className="template-edit-field">
                  <span>{t.templateNotes}</span>
                  <textarea onChange={event => updateTemplateDraft(template, { notes: event.target.value })} value={draft.notes} />
                </label>
                <label className="template-edit-field">
                  <span>{t.templateCases}</span>
                  <input onChange={event => updateTemplateDraft(template, { success_cases: event.target.value })} value={draft.success_cases} />
                </label>
                <ul className="compact-list">
                  {template.structure_template.slice(0, 5).map(item => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
                <button
                  className="primary-action compact-action project-library-open"
                  disabled={savingTemplateId === template.id}
                  onClick={() => void saveTemplate(template)}
                  type="button"
                >
                  {savingTemplateId === template.id ? (language === "zh" ? "保存中..." : "Saving...") : t.templateSave}
                </button>
                <button className="secondary-action compact-action project-library-open" onClick={() => onUseTemplate?.(template.id)} type="button">
                  {t.templateUse}
                </button>
              </article>
              );
            })}
          </div>
          </>
        )}
      </section>
    </main>
  );
}
