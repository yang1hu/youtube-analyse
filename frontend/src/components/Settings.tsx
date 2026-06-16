import { Activity, Save, Trash2 } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import {
  clearCache,
  defaultWorkspaceSettings,
  fetchCacheInfo,
  fetchHealthChecks,
  fetchMonitorStatus,
  fetchSettings,
  runMonitorOnce,
  saveSettings
} from "../api";
import type { CacheInfo, HealthCheckResponse, Language, MonitorRunResult, MonitorStatus, WorkspaceSettings } from "../types";

type SaveState = "idle" | "saving" | "saved" | "error";

interface SettingsProps {
  language: Language;
}

const copy = {
  zh: {
    browserCdpUrl: "\u73b0\u6709\u6d4f\u89c8\u5668 CDP URL",
    browserEngine: "\u6d4f\u89c8\u5668\u5f15\u64ce",
    browserPath: "\u6d4f\u89c8\u5668\u8def\u5f84",
    channelSettings: "\u9891\u9053\u76d1\u63a7\u914d\u7f6e",
    channelUrl: "\u9891\u9053\u5730\u5740",
    channelList: "\u9891\u9053列表",
    addChannel: "\u6dfb\u52a0\u9891\u9053",
    removeChannel: "\u5220\u9664",
    debugPort: "\u8c03\u8bd5\u7aef\u53e3",
    headlessMode: "\u65e0\u5934\u6a21\u5f0f",
    healthCheck: "\u5065\u5eb7\u68c0\u67e5",
    healthIntro: "\u68c0\u67e5 LLM\u3001yt-dlp\u3001ffmpeg\u3001CDP\u3001MySQL\u3001Redis \u548c\u7f13\u5b58\u76ee\u5f55\u3002",
    cache: "\u7f13\u5b58\u548c\u98ce\u9669\u63a7\u5236",
    clearSamples: "\u6e05\u7406\u6837\u672c\u7f13\u5b58",
    monitor: "\u81ea\u52a8\u76d1\u63a7",
    monitorAutoAnalyze: "\u65b0\u89c6\u9891\u81ea\u52a8\u5206\u6790",
    monitorAutoTranslate: "\u5206\u6790\u5b8c\u6210\u540e\u81ea\u52a8\u7ffb\u8bd1",
    monitorEnabled: "\u5b9a\u65f6\u68c0\u67e5\u9891\u9053",
    monitorInterval: "\u68c0\u67e5\u95f4\u9694\uff08\u5206\u949f\uff09",
    monitorMinViews: "\u6700\u4f4e\u64ad\u653e\u91cf\u9608\u503c",
    monitorRun: "\u7acb\u5373\u68c0\u67e5",
    monitorStatus: "\u76d1\u63a7\u72b6\u6001",
    monitorLastRun: "\u4e0a\u6b21\u8fd0\u884c",
    monitorNextRun: "\u4e0b\u6b21\u8fd0\u884c",
    monitorResult: "\u65b0\u89c6\u9891 {newVideos} \u6761\uff0c\u5165\u961f\u5206\u6790 {queued} \u6761\uff0c\u8df3\u8fc7 {skipped} \u6761\u3002",
    invalidChannel: "\u5982\u679c\u586b\u5199\u9891\u9053\uff0c\u8bf7\u4f7f\u7528\u6709\u6548\u7684 YouTube \u9891\u9053\u5730\u5740\u3002",
    invalidLlm: "\u8bf7\u586b\u5199 LLM Base URL \u548c\u6a21\u578b\u540d\u79f0\u3002",
    intro:
      "\u914d\u7f6e\u552f\u4e00\u9700\u8981\u76d1\u63a7\u7684 YouTube \u9891\u9053\uff0c\u5e76\u9009\u62e9\u6d4f\u89c8\u5668\u91c7\u96c6\u65b9\u5f0f\u3002CDP \u53ef\u8fde\u63a5\u5df2\u6253\u5f00\u7684 Chrome/Edge\u3002",
    llmAnalysisModel: "LLM \u5206\u6790\u6a21\u578b",
    llmApiKey: "LLM API Key",
    llmApiKeyHelp: "\u7559\u7a7a\u8868\u793a\u4fdd\u7559\u5df2\u4fdd\u5b58\u7684 key\u3002",
    llmBaseUrl: "LLM Base URL",
    llmConfigured: "\u5df2\u914d\u7f6e",
    llmMissing: "\u672a\u914d\u7f6e",
    llmSettings: "LLM \u914d\u7f6e",
    llmTranslationModel: "LLM \u7ffb\u8bd1\u6a21\u578b",
    save: "\u4fdd\u5b58",
    saveFailed: "\u4fdd\u5b58\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u540e\u7aef\u670d\u52a1\u3002",
    saved: "\u5df2\u4fdd\u5b58\u9891\u9053\u3001\u6d4f\u89c8\u5668\u548c LLM \u914d\u7f6e\u3002",
    saving: "\u4fdd\u5b58\u4e2d",
    savingMessage: "\u6b63\u5728\u4fdd\u5b58...",
    setup: "\u5de5\u4f5c\u533a\u914d\u7f6e",
    title: "\u8bbe\u7f6e"
  },
  en: {
    browserCdpUrl: "Existing Browser CDP URL",
    browserEngine: "Browser Engine",
    browserPath: "Browser Path",
    channelSettings: "Channel monitoring settings",
    channelUrl: "Channel URL",
    channelList: "Tracked channels",
    addChannel: "Add channel",
    removeChannel: "Remove",
    debugPort: "Debug Port",
    headlessMode: "Headless mode",
    healthCheck: "Health Check",
    healthIntro: "Check LLM, yt-dlp, ffmpeg, CDP, MySQL, Redis, and cache directories.",
    cache: "Cache and Risk Controls",
    clearSamples: "Clear sample cache",
    monitor: "Auto Monitor",
    monitorAutoAnalyze: "Auto analyze new videos",
    monitorAutoTranslate: "Auto translate after analysis",
    monitorEnabled: "Check channel on a schedule",
    monitorInterval: "Check interval (minutes)",
    monitorMinViews: "Minimum view threshold",
    monitorRun: "Run now",
    monitorStatus: "Monitor status",
    monitorLastRun: "Last run",
    monitorNextRun: "Next run",
    monitorResult: "{newVideos} new videos, {queued} queued for analysis, {skipped} skipped.",
    invalidChannel: "Enter a valid YouTube channel URL, or leave it blank.",
    invalidLlm: "Enter the LLM base URL and model names.",
    intro:
      "Configure the YouTube channels this agent should monitor and choose the browser collection engine. CDP can connect to an already-open Chrome or Edge instance.",
    llmAnalysisModel: "LLM Analysis Model",
    llmApiKey: "LLM API Key",
    llmApiKeyHelp: "Leave blank to keep the saved key.",
    llmBaseUrl: "LLM Base URL",
    llmConfigured: "Configured",
    llmMissing: "Missing",
    llmSettings: "LLM settings",
    llmTranslationModel: "LLM Translation Model",
    save: "Save",
    saveFailed: "Save failed. Check the backend service.",
    saved: "Channel list, browser, and LLM settings saved.",
    saving: "Saving",
    savingMessage: "Saving...",
    setup: "Workspace setup",
    title: "Settings"
  }
} satisfies Record<Language, Record<string, string>>;

function isYoutubeChannelUrl(value: string) {
  try {
    const url = new URL(value);
    return (
      ["youtube.com", "www.youtube.com"].includes(url.hostname) &&
      (url.pathname.startsWith("/@") ||
        url.pathname.startsWith("/channel/") ||
        url.pathname.startsWith("/c/") ||
        url.pathname.startsWith("/user/"))
    );
  } catch {
    return false;
  }
}

function normalizeChannelUrl(value: string) {
  return value.trim().replace(/\/+$/, "");
}

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

export default function Settings({ language }: SettingsProps) {
  const t = copy[language];
  const [settings, setSettings] = useState<WorkspaceSettings>(defaultWorkspaceSettings);
  const [isLoading, setIsLoading] = useState(true);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [message, setMessage] = useState("");
  const [health, setHealth] = useState<HealthCheckResponse | null>(null);
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);
  const [cache, setCache] = useState<CacheInfo | null>(null);
  const [isClearingCache, setIsClearingCache] = useState(false);
  const [monitor, setMonitor] = useState<MonitorStatus | null>(null);
  const [monitorResult, setMonitorResult] = useState<MonitorRunResult | null>(null);
  const [isRunningMonitor, setIsRunningMonitor] = useState(false);
  const [newChannelUrl, setNewChannelUrl] = useState("");

  useEffect(() => {
    let isMounted = true;

    fetchSettings()
      .then(data => {
        if (isMounted) {
          setSettings(data);
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });
    void fetchCacheInfo().then(setCache);
    void fetchMonitorStatus().then(setMonitor);

    return () => {
      isMounted = false;
    };
  }, []);

  const updateSetting = <Key extends keyof WorkspaceSettings>(
    key: Key,
    value: WorkspaceSettings[Key]
  ) => {
    setSettings(current => ({ ...current, [key]: value }));
    setSaveState("idle");
    setMessage("");
  };

  const addChannelUrl = () => {
    const candidate = normalizeChannelUrl(newChannelUrl);
    if (!candidate) {
      return;
    }
    if (!isYoutubeChannelUrl(candidate)) {
      setSaveState("error");
      setMessage(t.invalidChannel);
      return;
    }
    setSettings(current => {
      const channel_urls = Array.from(new Set([...(current.channel_urls ?? []), candidate]));
      return {
        ...current,
        channel_urls,
        channel_url: channel_urls[0] ?? ""
      };
    });
    setNewChannelUrl("");
    setSaveState("idle");
    setMessage("");
  };

  const removeChannelUrl = (url: string) => {
    setSettings(current => {
      const channel_urls = (current.channel_urls ?? []).filter(item => item !== url);
      return {
        ...current,
        channel_urls,
        channel_url: channel_urls[0] ?? ""
      };
    });
  };

  const runHealthCheck = async () => {
    setIsCheckingHealth(true);
    try {
      setHealth(await fetchHealthChecks());
    } finally {
      setIsCheckingHealth(false);
    }
  };

  const clearSampleCache = async () => {
    setIsClearingCache(true);
    try {
      setCache(await clearCache("samples"));
    } finally {
      setIsClearingCache(false);
    }
  };

  const runMonitor = async () => {
    setIsRunningMonitor(true);
    try {
      const result = await runMonitorOnce();
      setMonitorResult(result);
      setMonitor(await fetchMonitorStatus());
    } finally {
      setIsRunningMonitor(false);
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const channelUrl = settings.channel_url.trim();
    const channelUrls = Array.from(
      new Set(
        [channelUrl, ...(settings.channel_urls ?? [])]
          .map(normalizeChannelUrl)
          .filter(Boolean)
      )
    );

    if (channelUrls.some(url => !isYoutubeChannelUrl(url))) {
      setSaveState("error");
      setMessage(t.invalidChannel);
      return;
    }

    if (
      !settings.openai_base_url.trim() ||
      !settings.openai_translation_model.trim() ||
      !settings.openai_analysis_model.trim()
    ) {
      setSaveState("error");
      setMessage(t.invalidLlm);
      return;
    }

    setSaveState("saving");
    setMessage(t.savingMessage);

    try {
      const saved = await saveSettings({
        ...settings,
        channel_url: channelUrl,
        channel_urls: channelUrls,
        openai_base_url: settings.openai_base_url.trim(),
        openai_translation_model: settings.openai_translation_model.trim(),
        openai_analysis_model: settings.openai_analysis_model.trim()
      });
      setSettings(saved);
      setSaveState("saved");
      setMessage(t.saved);
    } catch {
      setSaveState("error");
      setMessage(t.saveFailed);
    }
  };

  return (
    <main className="app-shell workspace-page">
      <section className="page-intro" aria-labelledby="settings-title">
        <p className="eyebrow">{t.setup}</p>
        <h1 id="settings-title">{t.title}</h1>
        <p className="hero-summary">{t.intro}</p>
      </section>

      <section className="settings-layout" aria-label={t.channelSettings}>
        <form className="panel settings-form" onSubmit={event => void handleSubmit(event)}>
          <label className="field-group">
            <span>{t.channelUrl}</span>
            <input
              disabled={isLoading || saveState === "saving"}
              name="channelUrl"
              onChange={event => updateSetting("channel_url", event.target.value)}
              placeholder="https://www.youtube.com/@channel"
              type="url"
              value={settings.channel_url}
            />
          </label>

          <div className="settings-divider" />

          <div className="settings-section-heading">
            <div>
              <p className="eyebrow">{t.channelList}</p>
              <h2>{settings.channel_urls.length}</h2>
            </div>
          </div>

          <div className="channel-list-editor">
            <div className="channel-add-row">
              <input
                disabled={isLoading || saveState === "saving"}
                onChange={event => setNewChannelUrl(event.target.value)}
                placeholder="https://www.youtube.com/@channel"
                type="url"
                value={newChannelUrl}
              />
              <button className="secondary-action compact-action" disabled={isLoading || saveState === "saving"} onClick={addChannelUrl} type="button">
                <span>{t.addChannel}</span>
              </button>
            </div>
            {settings.channel_urls.length ? (
              <div className="channel-list">
                {settings.channel_urls.map(url => (
                  <div className="channel-list-item" key={url}>
                    <div>
                      <strong>{url}</strong>
                    </div>
                    <button className="secondary-action compact-action" disabled={isLoading || saveState === "saving"} onClick={() => removeChannelUrl(url)} type="button">
                      {t.removeChannel}
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="panel-note">{t.invalidChannel}</p>
            )}
          </div>

          <label className="field-group">
            <span>{t.browserEngine}</span>
            <select
              disabled={isLoading || saveState === "saving"}
              name="browserEngine"
              onChange={event =>
                updateSetting("browser_engine", event.target.value as WorkspaceSettings["browser_engine"])
              }
              value={settings.browser_engine}
            >
              <option value="playwright">Playwright</option>
              <option value="drission">DrissionPage</option>
              <option value="cdp">CDP</option>
            </select>
          </label>

          {settings.browser_engine === "cdp" && (
            <label className="field-group">
              <span>{t.browserCdpUrl}</span>
              <input
                disabled={isLoading || saveState === "saving"}
                name="browserCdpUrl"
                onChange={event => updateSetting("browser_cdp_url", event.target.value)}
                placeholder="http://127.0.0.1:9222"
                type="url"
                value={settings.browser_cdp_url}
              />
            </label>
          )}

          <label className="field-toggle">
            <input
              checked={settings.browser_headless}
              disabled={isLoading || saveState === "saving" || settings.browser_engine === "cdp"}
              name="browserHeadless"
              onChange={event => updateSetting("browser_headless", event.target.checked)}
              type="checkbox"
            />
            <span>{t.headlessMode}</span>
          </label>

          <label className="field-group">
            <span>{t.browserPath}</span>
            <input
              disabled={isLoading || saveState === "saving" || settings.browser_engine === "cdp"}
              name="browserPath"
              onChange={event => updateSetting("browser_path", event.target.value)}
              placeholder="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
              type="text"
              value={settings.browser_path}
            />
          </label>

          <label className="field-group">
            <span>{t.debugPort}</span>
            <input
              disabled={isLoading || saveState === "saving" || settings.browser_engine === "cdp"}
              inputMode="numeric"
              name="browserDebugPort"
              onChange={event =>
                updateSetting(
                  "browser_debug_port",
                  event.target.value ? Number(event.target.value) : null
                )
              }
              placeholder="9222"
              type="number"
              value={settings.browser_debug_port ?? ""}
            />
          </label>

          <div className="settings-divider" />

          <div className="settings-section-heading">
            <div>
              <p className="eyebrow">{t.monitor}</p>
              <h2>{t.monitorEnabled}</h2>
            </div>
            <span className={settings.monitor_enabled ? "status-pill status-pill-ok" : "status-pill status-pill-muted"}>
              {settings.monitor_enabled ? "on" : "off"}
            </span>
          </div>

          <label className="field-toggle">
            <input
              checked={settings.monitor_enabled}
              disabled={isLoading || saveState === "saving"}
              name="monitorEnabled"
              onChange={event => updateSetting("monitor_enabled", event.target.checked)}
              type="checkbox"
            />
            <span>{t.monitorEnabled}</span>
          </label>

          <label className="field-toggle">
            <input
              checked={settings.monitor_auto_analyze}
              disabled={isLoading || saveState === "saving" || !settings.monitor_enabled}
              name="monitorAutoAnalyze"
              onChange={event => updateSetting("monitor_auto_analyze", event.target.checked)}
              type="checkbox"
            />
            <span>{t.monitorAutoAnalyze}</span>
          </label>

          <label className="field-toggle">
            <input
              checked={settings.monitor_auto_translate}
              disabled={isLoading || saveState === "saving" || !settings.monitor_auto_analyze}
              name="monitorAutoTranslate"
              onChange={event => updateSetting("monitor_auto_translate", event.target.checked)}
              type="checkbox"
            />
            <span>{t.monitorAutoTranslate}</span>
          </label>

          <label className="field-group">
            <span>{t.monitorInterval}</span>
            <input
              disabled={isLoading || saveState === "saving" || !settings.monitor_enabled}
              inputMode="numeric"
              min={30}
              name="monitorInterval"
              onChange={event => updateSetting("monitor_interval_minutes", Number(event.target.value || 180))}
              type="number"
              value={settings.monitor_interval_minutes}
            />
          </label>

          <label className="field-group">
            <span>{t.monitorMinViews}</span>
            <input
              disabled={isLoading || saveState === "saving" || !settings.monitor_auto_analyze}
              inputMode="numeric"
              min={0}
              name="monitorMinViews"
              onChange={event => updateSetting("monitor_min_views", Number(event.target.value || 0))}
              type="number"
              value={settings.monitor_min_views}
            />
          </label>

          <div className="settings-divider" />

          <div className="settings-section-heading">
            <div>
              <p className="eyebrow">{t.llmSettings}</p>
              <h2>{t.llmBaseUrl}</h2>
            </div>
            <span className={settings.openai_api_key_set ? "status-pill" : "status-pill status-pill-muted"}>
              {settings.openai_api_key_set ? t.llmConfigured : t.llmMissing}
            </span>
          </div>

          <label className="field-group">
            <span>{t.llmBaseUrl}</span>
            <input
              disabled={isLoading || saveState === "saving"}
              name="openaiBaseUrl"
              onChange={event => updateSetting("openai_base_url", event.target.value)}
              placeholder="http://localhost:53881/v1"
              required
              type="url"
              value={settings.openai_base_url}
            />
          </label>

          <label className="field-group">
            <span>{t.llmAnalysisModel}</span>
            <input
              disabled={isLoading || saveState === "saving"}
              name="openaiAnalysisModel"
              onChange={event => updateSetting("openai_analysis_model", event.target.value)}
              placeholder="gpt-5.5"
              required
              type="text"
              value={settings.openai_analysis_model}
            />
          </label>

          <label className="field-group">
            <span>{t.llmTranslationModel}</span>
            <input
              disabled={isLoading || saveState === "saving"}
              name="openaiTranslationModel"
              onChange={event => updateSetting("openai_translation_model", event.target.value)}
              placeholder="gpt-5.5"
              required
              type="text"
              value={settings.openai_translation_model}
            />
          </label>

          <label className="field-group">
            <span>{t.llmApiKey}</span>
            <input
              autoComplete="off"
              disabled={isLoading || saveState === "saving"}
              name="openaiApiKey"
              onChange={event => updateSetting("openai_api_key", event.target.value)}
              placeholder={settings.openai_api_key_set ? "********" : "local-dev-key"}
              type="password"
              value={settings.openai_api_key}
            />
            <small>{t.llmApiKeyHelp}</small>
          </label>

          <button className="primary-action" disabled={isLoading || saveState === "saving"} type="submit">
            <Save aria-hidden="true" size={18} />
            <span>{saveState === "saving" ? t.saving : t.save}</span>
          </button>

          {message && <p className={`form-message form-message-${saveState}`}>{message}</p>}
        </form>

        <aside className="panel health-panel">
          <div className="settings-section-heading">
            <div>
              <p className="eyebrow">{t.monitorStatus}</p>
              <h2>{monitor?.enabled ? "on" : "off"}</h2>
            </div>
            <button className="secondary-action compact-action" disabled={isRunningMonitor || !settings.monitor_enabled} onClick={() => void runMonitor()} type="button">
              <Activity aria-hidden="true" size={18} />
              {isRunningMonitor ? "..." : t.monitorRun}
            </button>
          </div>
          <div className="cache-path-list">
            <div className="health-check-row">
              <span className={`status-pill status-pill-${monitor?.enabled ? "ok" : "muted"}`}>{monitor?.enabled ? "on" : "off"}</span>
              <div>
                <strong>{t.monitorLastRun}: {formatTime(monitor?.last_run_at, language)}</strong>
                <p>{t.monitorNextRun}: {formatTime(monitor?.next_run_at, language)}</p>
              </div>
            </div>
            {monitorResult && (
              <div className="health-check-row">
                <span className={`status-pill status-pill-${monitorResult.status}`}>{monitorResult.status}</span>
                <div>
                  <strong>
                    {t.monitorResult
                      .replace("{newVideos}", String(monitorResult.new_video_count))
                      .replace("{queued}", String(monitorResult.queued_analysis_count))
                      .replace("{skipped}", String(monitorResult.skipped_analysis_count))}
                  </strong>
                  {monitorResult.reason && <p>{monitorResult.reason}</p>}
                </div>
              </div>
            )}
          </div>

          <div className="settings-divider" />

          <div className="settings-section-heading">
            <div>
              <p className="eyebrow">{t.healthCheck}</p>
              <h2>{health?.summary.status ?? t.healthCheck}</h2>
            </div>
            <button className="secondary-action compact-action" disabled={isCheckingHealth} onClick={() => void runHealthCheck()} type="button">
              <Activity aria-hidden="true" size={18} />
              {isCheckingHealth ? "..." : t.healthCheck}
            </button>
          </div>
          <p className="panel-note">{t.healthIntro}</p>
          {health && (
            <div className="health-check-list">
              {health.checks.map(item => (
                <div className="health-check-row" key={item.key}>
                  <span className={`status-pill status-pill-${item.status}`}>{item.status}</span>
                  <div>
                    <strong>{item.label}</strong>
                    <p>{item.message}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="settings-divider" />
          <div className="settings-section-heading">
            <div>
              <p className="eyebrow">{t.cache}</p>
              <h2>{cache?.paths.samples.file_count ?? 0} files</h2>
            </div>
            <button className="secondary-action compact-action" disabled={isClearingCache} onClick={() => void clearSampleCache()} type="button">
              <Trash2 aria-hidden="true" size={18} />
              {isClearingCache ? "..." : t.clearSamples}
            </button>
          </div>
          {cache && (
            <div className="cache-path-list">
              {Object.entries(cache.paths).map(([key, value]) => (
                <div className="health-check-row" key={key}>
                  <span className="status-pill status-pill-muted">{key}</span>
                  <div>
                    <strong>{value.file_count} files / {value.size_bytes} bytes</strong>
                    <p>{value.path}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </aside>
      </section>
    </main>
  );
}
