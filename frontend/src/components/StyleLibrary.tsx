import { BookOpenText, Layers3, PenLine, WandSparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { applyStyle, fetchIdeas, fetchReports, fetchStyles, learnLatestStyle, mergeReportStyles } from "../api";
import type { CopyDraft, IdeaCard, Language, StyleProfile, VideoReportData } from "../types";

interface StyleLibraryProps {
  language: Language;
}

export default function StyleLibrary({ language }: StyleLibraryProps) {
  const isZh = language === "zh";
  const [styles, setStyles] = useState<StyleProfile[]>([]);
  const [drafts, setDrafts] = useState<CopyDraft[]>([]);
  const [ideas, setIdeas] = useState<IdeaCard[]>([]);
  const [reports, setReports] = useState<VideoReportData[]>([]);
  const [selectedStyleId, setSelectedStyleId] = useState("");
  const [selectedIdeaId, setSelectedIdeaId] = useState("");
  const [selectedReportIds, setSelectedReportIds] = useState<string[]>([]);
  const [styleName, setStyleName] = useState("");
  const [message, setMessage] = useState("");
  const [isLearning, setIsLearning] = useState(false);
  const [isMerging, setIsMerging] = useState(false);
  const [isWriting, setIsWriting] = useState(false);

  const load = async () => {
    try {
      const [styleData, ideaData, reportData] = await Promise.all([fetchStyles(), fetchIdeas(), fetchReports()]);
      setStyles(styleData.style_profiles);
      setDrafts(styleData.copy_drafts);
      setIdeas(ideaData);
      setReports(reportData);
      setSelectedStyleId(current => current || styleData.style_profiles[0]?.id || "");
      setSelectedIdeaId(current => current || ideaData[0]?.id || "");
      setSelectedReportIds(current => current.length ? current : reportData.slice(0, 2).map(report => report.id));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : isZh ? "风格库加载失败。" : "Style library failed to load.");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const learn = async () => {
    setIsLearning(true);
    setMessage("");
    try {
      const profile = await learnLatestStyle(styleName);
      await load();
      setSelectedStyleId(profile.id);
      setMessage(isZh ? "已从最新 LLM 报告学习脚本风格。" : "Learned a style from the latest LLM report.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : isZh ? "学习失败。" : "Learning failed.");
    } finally {
      setIsLearning(false);
    }
  };

  const toggleReport = (reportId: string) => {
    setSelectedReportIds(current =>
      current.includes(reportId) ? current.filter(item => item !== reportId) : [...current, reportId]
    );
  };

  const mergeReports = async () => {
    if (selectedReportIds.length < 2) {
      setMessage(isZh ? "请至少选择两个报告。" : "Select at least two reports.");
      return;
    }
    setIsMerging(true);
    setMessage("");
    try {
      const profile = await mergeReportStyles(selectedReportIds, styleName);
      await load();
      setSelectedStyleId(profile.id);
      setMessage(isZh ? "已融合多个报告的共同结构和风格。" : "Merged reusable style from multiple reports.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : isZh ? "融合失败。" : "Merge failed.");
    } finally {
      setIsMerging(false);
    }
  };

  const writeCopy = async () => {
    if (!selectedStyleId || !selectedIdeaId) {
      setMessage(isZh ? "请先选择风格和选题。" : "Select a style and an idea first.");
      return;
    }
    setIsWriting(true);
    setMessage(isZh ? "正在调用 LLM 写文案，通常需要几十秒，请稍等。" : "Calling the LLM to write copy. This can take tens of seconds.");
    try {
      const draft = await applyStyle(selectedStyleId, selectedIdeaId);
      setDrafts(current => [draft, ...current]);
      setMessage(isZh ? "系统已根据爆款风格生成文案。" : "Generated copy from the selected style.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : isZh ? "生成失败。" : "Copy generation failed.");
    } finally {
      setIsWriting(false);
    }
  };

  return (
    <main className="app-shell workspace-page">
      <section className="page-intro" aria-labelledby="style-library-title">
        <p className="eyebrow">{isZh ? "爆款方法论" : "Viral playbook"}</p>
        <h1 id="style-library-title">{isZh ? "风格库" : "Style Library"}</h1>
        <p className="hero-summary">
          {isZh
            ? "从爆款视频中学习脚本风格，再把风格应用到新选题，自动生成原创文案。"
            : "Learn reusable script styles from viral videos, then apply them to new ideas to write original copy."}
        </p>
      </section>

      <section className="style-grid">
        <article className="panel style-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">{isZh ? "学习样本" : "Learning sample"}</p>
              <h2>{isZh ? "从最新报告学习风格" : "Learn From Latest Report"}</h2>
            </div>
            <BookOpenText aria-hidden="true" size={22} />
          </div>
          <label className="field-group">
            <span>{isZh ? "风格名称" : "Style name"}</span>
            <input
              onChange={event => setStyleName(event.target.value)}
              placeholder={isZh ? "例如：系统流暴富爽文风格" : "Example: Cashback fantasy recap style"}
              type="text"
              value={styleName}
            />
          </label>
          <button className="primary-action compact-action" disabled={isLearning} onClick={() => void learn()} type="button">
            <WandSparkles aria-hidden="true" size={18} />
            {isLearning ? (isZh ? "学习中..." : "Learning...") : isZh ? "学习最新爆款风格" : "Learn Latest Style"}
          </button>
          {message && <p className="form-message form-message-idle">{message}</p>}
        </article>

        <article className="panel style-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">{isZh ? "多视频融合" : "Multi-report merge"}</p>
              <h2>{isZh ? "融合多个报告风格" : "Merge Report Styles"}</h2>
            </div>
            <Layers3 aria-hidden="true" size={22} />
          </div>
          <div className="report-select-list">
            {reports.length ? (
              reports.slice(0, 8).map(report => (
                <label className="report-select-item" key={report.id}>
                  <input
                    checked={selectedReportIds.includes(report.id)}
                    onChange={() => toggleReport(report.id)}
                    type="checkbox"
                  />
                  <span>{report.video_title || report.video_url}</span>
                </label>
              ))
            ) : (
              <p className="panel-note">{isZh ? "暂无报告，先分析视频。" : "No reports yet. Analyze videos first."}</p>
            )}
          </div>
          <button className="secondary-action compact-action" disabled={isMerging || selectedReportIds.length < 2} onClick={() => void mergeReports()} type="button">
            <Layers3 aria-hidden="true" size={18} />
            {isMerging ? (isZh ? "融合中..." : "Merging...") : isZh ? "融合报告风格" : "Merge Reports"}
          </button>
        </article>

        <article className="panel style-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">{isZh ? "应用风格" : "Apply style"}</p>
              <h2>{isZh ? "系统写文案" : "Generate Copy"}</h2>
            </div>
            <PenLine aria-hidden="true" size={22} />
          </div>
          <label className="field-group">
            <span>{isZh ? "选择风格" : "Select style"}</span>
            <select onChange={event => setSelectedStyleId(event.target.value)} value={selectedStyleId}>
              <option value="">{isZh ? "暂无风格" : "No style yet"}</option>
              {styles.map(style => (
                <option key={style.id} value={style.id}>
                  {style.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field-group">
            <span>{isZh ? "选择选题" : "Select idea"}</span>
            <select onChange={event => setSelectedIdeaId(event.target.value)} value={selectedIdeaId}>
              <option value="">{isZh ? "暂无选题" : "No idea yet"}</option>
              {ideas.map(idea => (
                <option key={idea.id ?? idea.title} value={idea.id}>
                  {idea.title}
                </option>
              ))}
            </select>
          </label>
          <button className="primary-action compact-action" disabled={isWriting || !selectedStyleId || !selectedIdeaId} onClick={() => void writeCopy()} type="button">
            <PenLine aria-hidden="true" size={18} />
            {isWriting ? (isZh ? "写作中..." : "Writing...") : isZh ? "套用风格生成文案" : "Generate Copy"}
          </button>
          {isWriting && (
            <p className="panel-note">
              {isZh ? "正在生成标题、前 60 秒口播和分段大纲。" : "Generating titles, the first 60 seconds, and the section outline."}
            </p>
          )}
        </article>
      </section>

      <section className="style-grid style-grid-wide">
        <article className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">{isZh ? "风格档案" : "Style profiles"}</p>
              <h2>{isZh ? "已学习风格" : "Learned Styles"}</h2>
            </div>
          </div>
          <div className="style-list">
            {styles.length ? (
              styles.map(style => (
                <div className="style-card" key={style.id}>
                  <h3>{style.name}</h3>
                  <p>{style.source_video_title}</p>
                  <dl className="style-fields">
                    <div>
                      <dt>{isZh ? "开场公式" : "Opening"}</dt>
                      <dd>{style.opening_formula}</dd>
                    </div>
                    <div>
                      <dt>{isZh ? "节奏公式" : "Rhythm"}</dt>
                      <dd>{style.rhythm_formula?.join(" / ")}</dd>
                    </div>
                    <div>
                      <dt>{isZh ? "避抄规则" : "Avoid copying"}</dt>
                      <dd>{style.avoid_copying?.join(" / ")}</dd>
                    </div>
                  </dl>
                </div>
              ))
            ) : (
              <p className="panel-note">{isZh ? "还没有风格档案，先学习最新报告。" : "No style profiles yet. Learn from the latest report first."}</p>
            )}
          </div>
        </article>

        <article className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">{isZh ? "文案草稿" : "Copy drafts"}</p>
              <h2>{isZh ? "系统生成结果" : "Generated Copy"}</h2>
            </div>
          </div>
          <div className="style-list">
            {drafts.length ? (
              drafts.map(draft => (
                <div className="style-card" key={draft.id}>
                  <div className="idea-badges">
                    <span className="status-pill">{draft.provider.toUpperCase()}</span>
                    <span className="status-pill status-pill-muted">{draft.model}</span>
                  </div>
                  <h3>{draft.title}</h3>
                  <pre className="script-box copy-draft-box">{draft.copy}</pre>
                </div>
              ))
            ) : (
              <p className="panel-note">{isZh ? "还没有生成文案，选择风格和选题后生成。" : "No copy drafts yet. Select a style and idea to generate one."}</p>
            )}
          </div>
        </article>
      </section>
    </main>
  );
}
