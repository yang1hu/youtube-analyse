import { Play, RefreshCw, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";

import { fetchTasks, retryTask, runNextQueuedTask, runTask } from "../api";
import type { DashboardJob, Language, TaskCenterResponse } from "../types";

interface TaskCenterProps {
  language: Language;
}

const copy = {
  zh: {
    empty: "\u8fd8\u6ca1\u6709\u4efb\u52a1\u3002\u540c\u6b65\u3001\u5206\u6790\u548c\u6837\u672c\u4efb\u52a1\u4f1a\u51fa\u73b0\u5728\u8fd9\u91cc\u3002",
    intro: "\u7edf\u4e00\u8ddf\u8e2a\u9891\u9053\u540c\u6b65\u3001\u5b57\u5e55\u83b7\u53d6\u3001\u62bd\u5e27\u3001LLM \u5206\u6790\u548c\u7ffb\u8bd1\u4efb\u52a1\u3002",
    redis: "Redis",
    queue: "\u961f\u5217",
    queueCount: "\u5f85\u5904\u7406",
    refresh: "\u5237\u65b0",
    retry: "\u91cd\u8bd5",
    retryOf: "\u91cd\u8bd5\u81ea",
    run: "\u8fd0\u884c",
    runNext: "\u8fd0\u884c\u961f\u5217\u4e0b\u4e00\u4e2a",
    target: "\u76ee\u6807",
    title: "\u4efb\u52a1\u4e2d\u5fc3",
    updated: "\u66f4\u65b0"
  },
  en: {
    empty: "No tasks yet. Sync, analysis, and sample jobs will appear here.",
    intro: "Track channel sync, transcript, frame extraction, LLM analysis, and translation jobs in one place.",
    redis: "Redis",
    queue: "Queue",
    queueCount: "Queued",
    refresh: "Refresh",
    retry: "Retry",
    retryOf: "Retry of",
    run: "Run",
    runNext: "Run next queued",
    target: "Target",
    title: "Task Center",
    updated: "Updated"
  }
} satisfies Record<Language, Record<string, string>>;

function formatTime(value: string | undefined, language: Language) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(language === "zh" ? "zh-CN" : "en-US", {
    dateStyle: "short",
    timeStyle: "short"
  }).format(date);
}

function statusClass(status: string | undefined) {
  return `status-pill status-pill-${status || "unknown"}`;
}

export default function TaskCenter({ language }: TaskCenterProps) {
  const t = copy[language];
  const [data, setData] = useState<TaskCenterResponse>({
    tasks: [],
    redis: { configured: false, status: "skipped", message: "" }
  });
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState("");

  const load = async () => {
    setIsLoading(true);
    try {
      setData(await fetchTasks());
      setMessage("");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void fetchTasks().then(setData), 8000);
    return () => window.clearInterval(timer);
  }, []);

  const retry = async (task: DashboardJob) => {
    if (!task.id) {
      return;
    }
    try {
      await retryTask(task.id);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Retry failed.");
    }
  };

  const run = async (task: DashboardJob) => {
    if (!task.id) {
      return;
    }
    try {
      await runTask(task.id);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Run failed.");
    }
  };

  const runNext = async () => {
    try {
      await runNextQueuedTask();
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Run failed.");
    }
  };

  return (
    <main className="app-shell workspace-page">
      <section className="page-intro">
        <p className="eyebrow">{language === "zh" ? "\u8fd0\u884c\u72b6\u6001" : "Operations"}</p>
        <h1>{t.title}</h1>
        <p className="hero-summary">{t.intro}</p>
        <div className="hero-actions report-actions">
          <button className="secondary-action compact-action" disabled={isLoading} onClick={() => void load()} type="button">
            <RefreshCw aria-hidden="true" size={18} />
            {t.refresh}
          </button>
          <button className="secondary-action compact-action" disabled={(data.queue?.queued_count ?? data.redis.queued_count ?? 0) <= 0} onClick={() => void runNext()} type="button">
            <Play aria-hidden="true" size={18} />
            {t.runNext}
          </button>
        </div>
      </section>

      <section className="task-grid">
        <article className="panel task-health">
          <p className="eyebrow">{t.redis}</p>
          <h2>{data.redis.status}</h2>
          <p className="panel-note">{data.redis.message}</p>
          <div className="task-queue-meter">
            <span>{t.queue}</span>
            <strong>{data.queue?.status ?? data.redis.status}</strong>
          </div>
          <div className="task-queue-meter">
            <span>{t.queueCount}</span>
            <strong>{data.queue?.queued_count ?? data.redis.queued_count ?? 0}</strong>
          </div>
        </article>

        <article className="panel task-list-panel">
          {message && <p className="form-message form-message-error">{message}</p>}
          {data.tasks.length ? (
            <div className="task-list">
              {data.tasks.map(task => (
                <div className="task-card" key={task.id}>
                  <div className="task-card-header">
                    <div>
                      <p className="eyebrow">{task.kind}</p>
                      <h2>{task.current_step_label || task.current_step || task.status}</h2>
                    </div>
                    <span className={statusClass(task.status)}>{task.status}</span>
                  </div>
                  <p className="panel-note">
                    {t.target}: {task.target_url || "-"}
                  </p>
                  {task.retry_of && <p className="panel-note">{t.retryOf}: {task.retry_of}</p>}
                  {task.queue_message && (
                    <p className={task.queue_status === "not_enqueued" ? "form-message form-message-error" : "panel-note"}>
                      {task.queue_message}
                    </p>
                  )}
                  {task.error_message && <p className="form-message form-message-error">{task.error_message}</p>}
                  <div className="task-step-row">
                    {(task.steps ?? []).map(step => (
                      <span className={`task-step task-step-${step.status}`} key={step.key}>
                        {step.label}
                      </span>
                    ))}
                  </div>
                  <div className="task-card-footer">
                    <small>
                      {t.updated}: {formatTime(task.updated_at, language)}
                    </small>
                    <div className="task-card-actions">
                      <button className="secondary-action compact-action" disabled={task.status !== "queued"} onClick={() => void run(task)} type="button">
                        <Play aria-hidden="true" size={16} />
                        {t.run}
                      </button>
                      <button className="secondary-action compact-action" disabled={task.status !== "failed"} onClick={() => void retry(task)} type="button">
                        <RotateCcw aria-hidden="true" size={16} />
                        {t.retry}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="panel-note">{isLoading ? "..." : t.empty}</p>
          )}
        </article>
      </section>
    </main>
  );
}
