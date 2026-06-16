import { AlertTriangle, ClipboardList, Lightbulb, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { fetchIdeas, pruneStaleIdeas } from "../api";
import type { IdeaCard, Language } from "../types";

interface IdeaLabProps {
  language: Language;
}

type IdeaAction = "score" | "outline" | "risk";

interface ActivePanel {
  ideaKey: string;
  action: IdeaAction;
}

function ideaKey(idea: IdeaCard) {
  return idea.id ?? idea.title ?? idea.source_video_url ?? "idea";
}

export default function IdeaLab({ language }: IdeaLabProps) {
  const [ideas, setIdeas] = useState<IdeaCard[]>([]);
  const [activePanel, setActivePanel] = useState<ActivePanel | null>(null);
  const [isCleaning, setIsCleaning] = useState(false);
  const [message, setMessage] = useState("");
  const isZh = language === "zh";

  useEffect(() => {
    void fetchIdeas()
      .then(setIdeas)
      .catch(error => {
        setMessage(error instanceof Error ? error.message : isZh ? "选题加载失败。" : "Ideas failed to load.");
      });
  }, [isZh]);

  const cleanStaleIdeas = async () => {
    setIsCleaning(true);
    setMessage("");
    try {
      const result = await pruneStaleIdeas();
      setIdeas(result.idea_cards);
      setActivePanel(null);
      setMessage(
        isZh
          ? `已清理 ${result.removed_count} 张旧规则选题卡。`
          : `Cleaned ${result.removed_count} stale rule-based idea cards.`
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : isZh ? "清理失败。" : "Cleanup failed.");
    } finally {
      setIsCleaning(false);
    }
  };

  const togglePanel = (idea: IdeaCard, action: IdeaAction) => {
    const key = ideaKey(idea);
    setActivePanel(current =>
      current?.ideaKey === key && current.action === action ? null : { ideaKey: key, action }
    );
  };

  const actionTitle = (action: IdeaAction) => {
    if (action === "score") {
      return isZh ? "评分说明" : "Score Notes";
    }
    if (action === "outline") {
      return isZh ? "可执行大纲" : "Actionable Outline";
    }
    return isZh ? "风险检查" : "Risk Check";
  };

  const renderActionPanel = (idea: IdeaCard, action: IdeaAction) => {
    if (action === "score") {
      return (
        <div className="idea-action-panel">
          <h3>{actionTitle(action)}</h3>
          <p>
            {isZh
              ? `这张卡当前评分为 ${idea.score ?? 0}。评分越高，代表它越接近可复用的强钩子、强冲突和清晰兑现路径。`
              : `This card is scored ${idea.score ?? 0}. Higher scores indicate a clearer hook, stronger conflict, and easier payoff path.`}
          </p>
          {idea.analysis_source && <p>{isZh ? "来源：" : "Source: "}{idea.analysis_source.toUpperCase()}</p>}
        </div>
      );
    }

    if (action === "outline") {
      return (
        <div className="idea-action-panel">
          <h3>{actionTitle(action)}</h3>
          {idea.outline?.length ? (
            <ol>
              {idea.outline.map(item => (
                <li key={item}>{item}</li>
              ))}
            </ol>
          ) : (
            <p>{isZh ? "这张卡还没有可用大纲。" : "This card does not have an outline yet."}</p>
          )}
        </div>
      );
    }

    return (
      <div className="idea-action-panel">
        <h3>{actionTitle(action)}</h3>
        <p>{idea.risk_notes || (isZh ? "暂无风险说明。" : "No risk notes yet.")}</p>
        <ul>
          <li>{isZh ? "避免照抄原视频标题、角色名和具体桥段。" : "Avoid copying the original title, character names, and exact beats."}</li>
          <li>{isZh ? "确认设定变化足够明显，不能只是换词。" : "Make sure the premise changes materially, not only cosmetically."}</li>
          <li>{isZh ? "保留爽点机制，但重新设计人物关系和场景。" : "Keep the payoff mechanism, but redesign relationships and scenes."}</li>
        </ul>
      </div>
    );
  };

  return (
    <main className="app-shell workspace-page">
      <section className="page-intro" aria-labelledby="idea-lab-title">
        <p className="eyebrow">{isZh ? "选题流水线" : "Idea pipeline"}</p>
        <h1 id="idea-lab-title">{isZh ? "选题实验室" : "Idea Lab"}</h1>
        <p className="hero-summary">
          {isZh
            ? "这里显示分析视频后生成的真实选题卡。"
            : "This page shows real idea cards generated after video analysis."}
        </p>
        <div className="hero-actions report-actions">
          <button className="secondary-action compact-action" disabled={isCleaning} onClick={() => void cleanStaleIdeas()} type="button">
            {isCleaning ? (isZh ? "清理中..." : "Cleaning...") : isZh ? "清理旧规则卡" : "Clean Rule Cards"}
          </button>
        </div>
        {message && <p className="form-message form-message-idle">{message}</p>}
      </section>

      {ideas.length ? (
        <section className="idea-grid" aria-label="Idea cards">
          {ideas.map(idea => {
            const key = ideaKey(idea);
            const activeAction = activePanel?.ideaKey === key ? activePanel.action : null;

            return (
              <article className="idea-preview" key={key}>
                <div className="idea-preview-header">
                  <div>
                    <p className="eyebrow">{idea.source ?? "Source video"}</p>
                    <h2>{idea.title}</h2>
                  </div>
                  <div className="idea-badges">
                    <span className="status-pill">{idea.score ?? 0}</span>
                    {idea.analysis_source && (
                      <span className="status-pill status-pill-muted">
                        {idea.analysis_source.toUpperCase()}
                      </span>
                    )}
                  </div>
                </div>

                <dl className="idea-fields">
                  <div>
                    <dt>{isZh ? "角度" : "Angle"}</dt>
                    <dd>{idea.angle}</dd>
                  </div>
                  <div>
                    <dt>{isZh ? "原因" : "Why"}</dt>
                    <dd>{idea.why_it_works}</dd>
                  </div>
                  <div>
                    <dt>{isZh ? "大纲" : "Outline"}</dt>
                    <dd>{idea.outline?.join(" / ")}</dd>
                  </div>
                  <div>
                    <dt>{isZh ? "风险" : "Risk"}</dt>
                    <dd>{idea.risk_notes}</dd>
                  </div>
                </dl>

                <div className="idea-footer">
                  <button className="idea-footer-action" onClick={() => togglePanel(idea, "score")} type="button">
                    <Sparkles aria-hidden="true" size={16} />
                    {isZh ? "评分" : "Score"} {idea.score ?? 0}
                  </button>
                  <button className="idea-footer-action" onClick={() => togglePanel(idea, "outline")} type="button">
                    <ClipboardList aria-hidden="true" size={16} />
                    {isZh ? "进入大纲" : "Open Outline"}
                  </button>
                  <button className="idea-footer-action" onClick={() => togglePanel(idea, "risk")} type="button">
                    <AlertTriangle aria-hidden="true" size={16} />
                    {isZh ? "风险检查" : "Risk Check"}
                  </button>
                </div>

                {activeAction && renderActionPanel(idea, activeAction)}
              </article>
            );
          })}
        </section>
      ) : (
        <article className="panel idea-empty">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">{isZh ? "空状态" : "Empty state"}</p>
              <h2>{isZh ? "等待选题" : "Waiting for ideas"}</h2>
            </div>
            <Lightbulb aria-hidden="true" size={22} />
          </div>
          <p className="panel-note">
            {isZh ? "分析一条视频后，选题卡会出现在这里。" : "Analyze a video and generated idea cards will appear here."}
          </p>
        </article>
      )}
    </main>
  );
}
