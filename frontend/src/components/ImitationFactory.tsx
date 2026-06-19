import { Clipboard, Download, Factory, FileText, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { createImitationProject, exportImitationMarkdown, fetchImitationFactory } from "../api";
import type { ImitationFactoryResponse, ImitationProject, Language } from "../types";

interface ImitationFactoryProps {
  language: Language;
}

const copy = {
  zh: {
    antiCopy: "避抄规则",
    copyCommand: "复制命令",
    create: "生成参考包",
    direction: "新故事方向",
    directionPlaceholder: "例如：改成现代都市短片小说，主角是被低估的实习生，保留信息差和公开反转。",
    download: "下载参考包",
    empty: "还没有仿写项目。先分析一条视频，再在这里生成 InkOS 参考包。",
    exportCopied: "已复制 InkOS 命令。",
    intro: "把 YouTube 视频报告转成 InkOS 可执行的仿写参考包：保留结构、节奏和爽点机制，同时明确避抄边界。",
    keepNarration: "保持原视频叙述口吻",
    outputType: "输出类型",
    projects: "仿写项目",
    quality: "验收标准",
    reference: "InkOS 参考包",
    report: "源视频报告",
    risk: "风险",
    selectIdea: "选题卡",
    similarity: "相似强度",
    targetLength: "目标长度",
    title: "仿写工厂"
  },
  en: {
    antiCopy: "Anti-copy Rules",
    copyCommand: "Copy Command",
    create: "Create Reference",
    direction: "New Story Direction",
    directionPlaceholder: "Example: turn it into a modern short fiction piece about an underestimated intern while keeping the information gap and public reversal.",
    download: "Download Reference",
    empty: "No imitation projects yet. Analyze a video first, then create an InkOS reference package here.",
    exportCopied: "InkOS command copied.",
    intro: "Turn a YouTube video report into an InkOS-ready imitation package: keep structure, pacing, and payoff mechanics while defining clear anti-copy boundaries.",
    keepNarration: "Keep source narration voice",
    outputType: "Output Type",
    projects: "Imitation Projects",
    quality: "Quality Checks",
    reference: "InkOS Reference",
    report: "Source Report",
    risk: "Risk",
    selectIdea: "Idea Card",
    similarity: "Similarity",
    targetLength: "Target Length",
    title: "Imitation Factory"
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

export default function ImitationFactory({ language }: ImitationFactoryProps) {
  const t = copy[language];
  const [data, setData] = useState<ImitationFactoryResponse>({ projects: [], reports: [], ideas: [] });
  const [selectedReportId, setSelectedReportId] = useState("");
  const [selectedIdeaId, setSelectedIdeaId] = useState("");
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [direction, setDirection] = useState("");
  const [outputType, setOutputType] = useState<"short_fiction" | "story_recap" | "short_drama" | "interactive">("short_fiction");
  const [similarityLevel, setSimilarityLevel] = useState<"low" | "medium" | "high">("medium");
  const [targetLength, setTargetLength] = useState("2500-4000 Chinese characters");
  const [keepNarration, setKeepNarration] = useState(true);
  const [isWorking, setIsWorking] = useState(false);
  const [message, setMessage] = useState("");

  const selectedProject = data.projects.find(project => project.id === selectedProjectId) ?? data.projects[0] ?? null;
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
      setMessage(error instanceof Error ? error.message : "Imitation factory failed to load.");
    }
  };

  useEffect(() => {
    void load();
  }, []);

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
        direction,
        output_type: outputType,
        similarity_level: similarityLevel,
        target_length: targetLength,
        keep_narration: keepNarration
      });
      setData(current => ({ ...current, projects: [project, ...current.projects] }));
      setSelectedProjectId(project.id);
      setMessage(language === "zh" ? "仿写参考包已生成。" : "Imitation reference package created.");
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

  return (
    <main className="app-shell workspace-page">
      <section className="page-intro" aria-labelledby="imitation-factory-title">
        <p className="eyebrow">{language === "zh" ? "视频到故事" : "Video to story"}</p>
        <h1 id="imitation-factory-title">{t.title}</h1>
        <p className="hero-summary">{t.intro}</p>
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

          {!data.projects.length && <p className="panel-note">{t.empty}</p>}
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
              </div>
            </div>

            <pre className="script-box imitation-command">{selectedProject.inkos_command}</pre>

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

            <h3>{t.reference}</h3>
            <pre className="script-box">{selectedProject.reference_markdown}</pre>
          </div>
        ) : (
          <p className="panel-note">{t.empty}</p>
        )}
      </section>
    </main>
  );
}
