import { useEffect, useState } from "react";

import { analyzeSample, analyzeVideo, fetchDashboard, syncChannel } from "./api";
import Dashboard from "./components/Dashboard";
import IdeaLab from "./components/IdeaLab";
import Settings from "./components/Settings";
import SampleLibrary from "./components/SampleLibrary";
import ScriptStudio from "./components/ScriptStudio";
import StyleLibrary from "./components/StyleLibrary";
import TaskCenter from "./components/TaskCenter";
import VideoReport from "./components/VideoReport";
import type { DashboardData, Language, RecentVideo } from "./types";

type View =
  | "dashboard"
  | "tasks"
  | "video-report"
  | "sample-library"
  | "idea-lab"
  | "style-library"
  | "script-studio"
  | "settings";

const languageStorageKey = "youtube-creator-agent-language";

const navLabels: Record<Language, Record<View, string>> = {
  zh: {
    dashboard: "\u4eea\u8868\u76d8",
    tasks: "\u4efb\u52a1\u4e2d\u5fc3",
    "video-report": "\u89c6\u9891\u62a5\u544a",
    "sample-library": "\u6837\u672c\u5e93",
    "idea-lab": "\u9009\u9898\u5b9e\u9a8c\u5ba4",
    "style-library": "\u98ce\u683c\u5e93",
    "script-studio": "\u521b\u4f5c\u53f0",
    settings: "\u8bbe\u7f6e"
  },
  en: {
    dashboard: "Dashboard",
    tasks: "Tasks",
    "video-report": "Video Report",
    "sample-library": "Samples",
    "idea-lab": "Idea Lab",
    "style-library": "Style Library",
    "script-studio": "Script Studio",
    settings: "Settings"
  }
};

function initialLanguage(): Language {
  const saved = window.localStorage.getItem(languageStorageKey);
  return saved === "en" || saved === "zh" ? saved : "zh";
}

const emptyDashboard: DashboardData = {
  channels: [],
  recent_videos: [],
  idea_cards: [],
  jobs: [],
  comment_collector_status: "unknown"
};

export default function App() {
  const [dashboard, setDashboard] = useState<DashboardData>(emptyDashboard);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);
  const [workspaceMessage, setWorkspaceMessage] = useState("");
  const [workspaceMessageTone, setWorkspaceMessageTone] = useState<"saved" | "error">("saved");
  const [activeView, setActiveView] = useState<View>("dashboard");
  const [language, setLanguage] = useState<Language>(initialLanguage);

  const loadDashboard = () => {
    setIsLoading(true);
    return fetchDashboard()
      .then(data => {
        setDashboard(data);
      })
      .catch(() => {
        setDashboard(emptyDashboard);
        setWorkspaceMessageTone("error");
        setWorkspaceMessage(
          language === "zh" ? "\u4eea\u8868\u76d8\u52a0\u8f7d\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u540e\u7aef\u670d\u52a1\u3002" : "Dashboard failed to load. Check the backend service."
        );
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  useEffect(() => {
    void loadDashboard();
  }, []);

  const handleSyncChannel = async () => {
    setIsWorking(true);
    setWorkspaceMessage("");
    try {
      await syncChannel();
      await loadDashboard();
      setActiveView("tasks");
    } catch (error) {
      setWorkspaceMessageTone("error");
      setWorkspaceMessage(error instanceof Error ? error.message : "Unable to sync channel.");
    } finally {
      setIsWorking(false);
    }
  };

  const handleAnalyzeVideo = async (videoUrl: string) => {
    setIsWorking(true);
    setWorkspaceMessage("");
    try {
      await analyzeVideo(videoUrl);
      await loadDashboard();
      setActiveView("tasks");
    } catch (error) {
      setWorkspaceMessageTone("error");
      setWorkspaceMessage(error instanceof Error ? error.message : "Unable to analyze video.");
    } finally {
      setIsWorking(false);
    }
  };

  const handleAnalyzeSample = async (video: RecentVideo) => {
    if (!video.url) {
      return;
    }
    const confirmed = window.confirm(
      language === "zh"
        ? "\u5c06\u521b\u5efa\u524d 5 \u5206\u949f\u6837\u672c\u5206\u6790\u4efb\u52a1\uff0c\u53ea\u62bd\u53d6\u6837\u672c\u5e27\uff0c\u9ed8\u8ba4\u4e0d\u4fdd\u5b58\u5b8c\u6574\u89c6\u9891\u3002"
        : "This will create a first-five-minute sample task, extract sample frames, and avoid retaining the full video by default."
    );
    if (!confirmed) {
      return;
    }
    setIsWorking(true);
    setWorkspaceMessage("");
    try {
      const task = await analyzeSample(video.url, video.title ?? "", video.youtube_video_id ?? video.id ?? "");
      setWorkspaceMessageTone(task.queue_status === "not_enqueued" ? "error" : "saved");
      setWorkspaceMessage(
        task.queue_message ||
          (language === "zh" ? "\u6837\u672c\u5206\u6790\u4efb\u52a1\u5df2\u52a0\u5165\u4efb\u52a1\u4e2d\u5fc3\u3002" : "Sample analysis task queued in Task Center.")
      );
      setActiveView("tasks");
    } catch (error) {
      setWorkspaceMessageTone("error");
      setWorkspaceMessage(error instanceof Error ? error.message : "Unable to analyze sample.");
    } finally {
      setIsWorking(false);
    }
  };

  const navItems: { view: View }[] = [
    { view: "dashboard" },
    { view: "tasks" },
    { view: "video-report" },
    { view: "sample-library" },
    { view: "idea-lab" },
    { view: "style-library" },
    { view: "script-studio" },
    { view: "settings" }
  ];

  const changeLanguage = (nextLanguage: Language) => {
    setLanguage(nextLanguage);
    window.localStorage.setItem(languageStorageKey, nextLanguage);
  };

  return (
    <>
      <header
        className="workspace-nav"
        aria-label={language === "zh" ? "\u521b\u4f5c\u8005\u5de5\u4f5c\u533a\u5bfc\u822a" : "Creator workspace navigation"}
      >
        <div className="workspace-nav-inner">
          <p className="workspace-brand">Creator Agent</p>
          <div className="workspace-actions">
            <nav className="workspace-tabs" aria-label={language === "zh" ? "\u4e3b\u89c6\u56fe" : "Primary views"}>
              {navItems.map(item => (
                <button
                  aria-current={activeView === item.view ? "page" : undefined}
                  className="workspace-tab"
                  key={item.view}
                  onClick={() => setActiveView(item.view)}
                  type="button"
                >
                  {navLabels[language][item.view]}
                </button>
              ))}
            </nav>
            <label className="language-select">
              <span>{language === "zh" ? "\u8bed\u8a00" : "Language"}</span>
              <select
                aria-label={language === "zh" ? "\u9009\u62e9\u8bed\u8a00" : "Select language"}
                onChange={event => changeLanguage(event.target.value as Language)}
                value={language}
              >
                <option value="zh">{"\u4e2d\u6587"}</option>
                <option value="en">English</option>
              </select>
            </label>
          </div>
        </div>
      </header>

      {activeView === "dashboard" && (
        <Dashboard
          data={dashboard}
          isLoading={isLoading}
          isWorking={isWorking}
          language={language}
          onAnalyzeSample={handleAnalyzeSample}
          onAnalyzeVideo={handleAnalyzeVideo}
          onSyncChannel={handleSyncChannel}
          message={workspaceMessage}
          messageTone={workspaceMessageTone}
        />
      )}
      {activeView === "tasks" && <TaskCenter language={language} />}
      {activeView === "video-report" && <VideoReport language={language} />}
      {activeView === "sample-library" && <SampleLibrary language={language} />}
      {activeView === "idea-lab" && <IdeaLab language={language} />}
      {activeView === "style-library" && <StyleLibrary language={language} />}
      {activeView === "script-studio" && <ScriptStudio language={language} />}
      {activeView === "settings" && <Settings language={language} />}
    </>
  );
}
