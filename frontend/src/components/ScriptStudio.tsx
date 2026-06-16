import { Clipboard, Download, FileText, PenLine, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { exportScriptMarkdown, fetchIdeas, fetchScripts, fetchStyles, generateScript, rewriteScript, updateScript } from "../api";
import type { IdeaCard, Language, ScriptDraft, StyleProfile } from "../types";

interface ScriptStudioProps {
  language: Language;
}

const copy = {
  zh: {
    empty: "\u8fd8\u6ca1\u6709\u811a\u672c\u8349\u7a3f\u3002\u5148\u9009\u62e9\u9009\u9898\u548c\u98ce\u683c\u751f\u6210\u4e00\u7248\u3002",
    export: "Markdown",
    copy: "\u590d\u5236",
    download: "\u4e0b\u8f7d",
    fullScript: "\u5b8c\u6574\u811a\u672c",
    generate: "\u751f\u6210\u811a\u672c",
    intro: "\u628a\u9009\u9898\u53d8\u6210\u6807\u9898\u3001\u524d 30 \u79d2\u548c\u5b8c\u6574\u811a\u672c\uff0c\u5e76\u4fdd\u7559\u7248\u672c\u5386\u53f2\u3002",
    opening: "\u524d 30 \u79d2",
    rewrite: "\u5957\u7528\u98ce\u683c\u91cd\u5199",
    selectIdea: "\u9009\u62e9\u9009\u9898",
    selectStyle: "\u9009\u62e9\u98ce\u683c",
    title: "\u521b\u4f5c\u53f0",
    titleOptions: "\u6807\u9898\u65b9\u6848",
    useTitle: "\u9009\u7528\u5e76\u751f\u6210\u65b0\u7248",
    versions: "\u811a\u672c\u7248\u672c"
  },
  en: {
    empty: "No script drafts yet. Select an idea and style to generate one.",
    export: "Markdown",
    copy: "Copy",
    download: "Download",
    fullScript: "Full Script",
    generate: "Generate Script",
    intro: "Turn an idea into title options, the first 30 seconds, and a full script with version history.",
    opening: "First 30 Seconds",
    rewrite: "Rewrite With Style",
    selectIdea: "Select Idea",
    selectStyle: "Select Style",
    title: "Script Studio",
    titleOptions: "Title Options",
    useTitle: "Use as new version",
    versions: "Script Versions"
  }
} satisfies Record<Language, Record<string, string>>;

export default function ScriptStudio({ language }: ScriptStudioProps) {
  const t = copy[language];
  const [ideas, setIdeas] = useState<IdeaCard[]>([]);
  const [styles, setStyles] = useState<StyleProfile[]>([]);
  const [scripts, setScripts] = useState<ScriptDraft[]>([]);
  const [selectedIdeaId, setSelectedIdeaId] = useState("");
  const [selectedStyleId, setSelectedStyleId] = useState("");
  const [selectedScriptId, setSelectedScriptId] = useState("");
  const [message, setMessage] = useState("");
  const [isWorking, setIsWorking] = useState(false);

  const selectedScript = scripts.find(script => script.id === selectedScriptId) ?? scripts[0] ?? null;

  const load = async () => {
    try {
      const [ideaData, styleData, scriptData] = await Promise.all([fetchIdeas(), fetchStyles(), fetchScripts()]);
      setIdeas(ideaData);
      setStyles(styleData.style_profiles);
      setScripts(scriptData);
      setSelectedIdeaId(current => current || ideaData[0]?.id || "");
      setSelectedStyleId(current => current || styleData.style_profiles[0]?.id || "");
      setSelectedScriptId(current => current || scriptData[0]?.id || "");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : language === "zh" ? "创作台加载失败。" : "Script Studio failed to load.");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const generate = async () => {
    if (!selectedIdeaId) {
      return;
    }
    setIsWorking(true);
    setMessage("");
    try {
      const script = await generateScript(selectedIdeaId, selectedStyleId);
      setScripts(current => [script, ...current]);
      setSelectedScriptId(script.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Generation failed.");
    } finally {
      setIsWorking(false);
    }
  };

  const rewrite = async () => {
    if (!selectedScript?.id) {
      return;
    }
    setIsWorking(true);
    setMessage("");
    try {
      const script = await rewriteScript(selectedScript.id, selectedStyleId);
      setScripts(current => [script, ...current]);
      setSelectedScriptId(script.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Rewrite failed.");
    } finally {
      setIsWorking(false);
    }
  };

  const selectTitle = async (title: string) => {
    if (!selectedScript?.id || title === selectedScript.selected_title) {
      return;
    }
    setIsWorking(true);
    setMessage("");
    try {
      const script = await updateScript(selectedScript.id, { selected_title: title });
      setScripts(current => [script, ...current]);
      setSelectedScriptId(script.id);
      setMessage(language === "zh" ? "\u5df2\u7528\u8be5\u6807\u9898\u751f\u6210\u65b0\u7248\u672c\u3002" : "New version created with that title.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Title update failed.");
    } finally {
      setIsWorking(false);
    }
  };

  const copyMarkdown = async () => {
    if (!selectedScript?.markdown) {
      return;
    }
    await navigator.clipboard.writeText(selectedScript.markdown);
    setMessage(language === "zh" ? "\u5df2\u590d\u5236 Markdown\u3002" : "Markdown copied.");
  };

  const downloadMarkdown = async () => {
    if (!selectedScript?.id) {
      return;
    }
    try {
      const exported = await exportScriptMarkdown(selectedScript.id);
      const blob = new Blob([exported.markdown], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = exported.filename;
      link.click();
      URL.revokeObjectURL(url);
      setMessage(language === "zh" ? "\u5df2\u5bfc\u51fa Markdown\u3002" : "Markdown exported.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Export failed.");
    }
  };

  return (
    <main className="app-shell workspace-page">
      <section className="page-intro">
        <p className="eyebrow">{language === "zh" ? "\u751f\u4ea7\u5de5\u4f5c\u6d41" : "Production workflow"}</p>
        <h1>{t.title}</h1>
        <p className="hero-summary">{t.intro}</p>
      </section>

      <section className="style-grid">
        <article className="panel style-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">{language === "zh" ? "\u8f93\u5165" : "Inputs"}</p>
              <h2>{t.generate}</h2>
            </div>
            <PenLine aria-hidden="true" size={22} />
          </div>
          <label className="field-group">
            <span>{t.selectIdea}</span>
            <select onChange={event => setSelectedIdeaId(event.target.value)} value={selectedIdeaId}>
              <option value="">{language === "zh" ? "\u6682\u65e0\u9009\u9898" : "No idea"}</option>
              {ideas.map(idea => (
                <option key={idea.id ?? idea.title} value={idea.id}>
                  {idea.title}
                </option>
              ))}
            </select>
          </label>
          <label className="field-group">
            <span>{t.selectStyle}</span>
            <select onChange={event => setSelectedStyleId(event.target.value)} value={selectedStyleId}>
              <option value="">{language === "zh" ? "\u4e0d\u5957\u98ce\u683c" : "No style"}</option>
              {styles.map(style => (
                <option key={style.id} value={style.id}>
                  {style.name}
                </option>
              ))}
            </select>
          </label>
          <button className="primary-action compact-action" disabled={isWorking || !selectedIdeaId} onClick={() => void generate()} type="button">
            <FileText aria-hidden="true" size={18} />
            {t.generate}
          </button>
          {message && <p className="form-message form-message-idle">{message}</p>}
        </article>

        <article className="panel style-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">{language === "zh" ? "\u7248\u672c" : "Versions"}</p>
              <h2>{t.versions}</h2>
            </div>
            <RefreshCw aria-hidden="true" size={22} />
          </div>
          <div className="report-history-list">
            {scripts.map(script => (
              <button
                className={script.id === selectedScript?.id ? "report-history-item report-history-item-active" : "report-history-item"}
                key={script.id}
                onClick={() => setSelectedScriptId(script.id)}
                type="button"
              >
                <span>{script.selected_title}</span>
                <small>v{script.version} · {script.id}</small>
              </button>
            ))}
          </div>
          {selectedScript && (
            <div className="hero-actions report-actions">
              <button className="secondary-action compact-action" disabled={isWorking} onClick={() => void rewrite()} type="button">
                <RefreshCw aria-hidden="true" size={18} />
                {t.rewrite}
              </button>
              <button className="secondary-action compact-action" onClick={() => void copyMarkdown()} type="button">
                <Clipboard aria-hidden="true" size={18} />
                {t.copy}
              </button>
              <button className="secondary-action compact-action" onClick={() => void downloadMarkdown()} type="button">
                <Download aria-hidden="true" size={18} />
                {t.download}
              </button>
            </div>
          )}
        </article>
      </section>

      <section className="panel transcript-panel">
        {selectedScript ? (
          <div className="transcript-content">
            <p className="eyebrow">v{selectedScript.version}</p>
            <h2>{selectedScript.selected_title}</h2>
            <h3>{t.titleOptions}</h3>
            <ol className="report-list script-title-options">
              {selectedScript.title_options.map(title => (
                <li key={title}>
                  <span>{title}</span>
                  <button className="secondary-action compact-action" disabled={isWorking || title === selectedScript.selected_title} onClick={() => void selectTitle(title)} type="button">
                    {t.useTitle}
                  </button>
                </li>
              ))}
            </ol>
            <h3>{t.opening}</h3>
            <pre className="script-box">{selectedScript.opening_30s}</pre>
            <h3>{t.fullScript}</h3>
            <pre className="script-box">{selectedScript.markdown}</pre>
          </div>
        ) : (
          <p className="panel-note">{t.empty}</p>
        )}
      </section>
    </main>
  );
}
