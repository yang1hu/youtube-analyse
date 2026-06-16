import { Layers, Star } from "lucide-react";
import { useEffect, useState } from "react";

import { fetchSampleLibrary, mergeSampleStyle, updateSampleLibraryItem } from "../api";
import type { Language, SampleAnalysis, StyleProfile } from "../types";

interface SampleLibraryProps {
  language: Language;
}

const copy = {
  zh: {
    empty: "还没有精品样本。先在视频报告或仪表盘触发前 5 分钟样本分析。",
    favorite: "收藏",
    intro: "沉淀爆款视频的脚本、前 5 分钟节奏、标签和可复用模板。",
    merge: "合并成风格",
    mergeName: "风格名称",
    loadFailed: "样本库加载失败，请检查后端服务。",
    notes: "备注",
    rules: "复用模板",
    saved: "已保存样本。",
    select: "选择",
    tags: "标签",
    title: "爆款样本库"
  },
  en: {
    empty: "No samples yet. Run a first-five-minute sample analysis from the dashboard or report page.",
    favorite: "Favorite",
    intro: "Organize viral scripts, first-five-minute rhythm, tags, and reusable templates.",
    merge: "Merge Style",
    mergeName: "Style name",
    loadFailed: "Sample library failed to load. Check the backend service.",
    notes: "Notes",
    rules: "Reusable rules",
    saved: "Sample saved.",
    select: "Select",
    tags: "Tags",
    title: "Viral Sample Library"
  }
} satisfies Record<Language, Record<string, string>>;

function parseTags(value: string) {
  return value
    .split(",")
    .map(tag => tag.trim())
    .filter(Boolean);
}

export default function SampleLibrary({ language }: SampleLibraryProps) {
  const t = copy[language];
  const [samples, setSamples] = useState<SampleAnalysis[]>([]);
  const [tagSuggestions, setTagSuggestions] = useState<string[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [styleName, setStyleName] = useState("");
  const [createdStyle, setCreatedStyle] = useState<StyleProfile | null>(null);
  const [message, setMessage] = useState("");

  const load = async () => {
    try {
      const result = await fetchSampleLibrary();
      setSamples(result.samples);
      setTagSuggestions(result.tag_suggestions);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t.loadFailed);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const toggleSelected = (sampleId: string) => {
    setSelectedIds(current =>
      current.includes(sampleId) ? current.filter(id => id !== sampleId) : [...current, sampleId]
    );
  };

  const updateSample = async (sample: SampleAnalysis, patch: { favorite?: boolean; tags?: string[]; notes?: string }) => {
    const updated = await updateSampleLibraryItem(sample.id, patch);
    setSamples(current => current.map(item => (item.id === updated.id ? updated : item)));
    setMessage(t.saved);
  };

  const merge = async () => {
    const style = await mergeSampleStyle(selectedIds, styleName || "Merged sample style");
    setCreatedStyle(style);
    setMessage("");
  };

  return (
    <main className="app-shell workspace-page">
      <section className="page-intro">
        <p className="eyebrow">{language === "zh" ? "资产层" : "Asset layer"}</p>
        <h1>{t.title}</h1>
        <p className="hero-summary">{t.intro}</p>
      </section>

      <section className="sample-library-layout">
        <article className="panel sample-merge-panel">
          <div className="settings-section-heading">
            <div>
              <p className="eyebrow">{language === "zh" ? "多样本学习" : "Multi-sample learning"}</p>
              <h2>{t.merge}</h2>
            </div>
            <span className="status-pill">{selectedIds.length}</span>
          </div>
          <label className="field-group">
            <span>{t.mergeName}</span>
            <input onChange={event => setStyleName(event.target.value)} placeholder="Fast System Opening" type="text" value={styleName} />
          </label>
          <button className="primary-action" disabled={selectedIds.length < 2} onClick={() => void merge()} type="button">
            <Layers aria-hidden="true" size={18} />
            {t.merge}
          </button>
          {tagSuggestions.length > 0 && <p className="panel-note">{tagSuggestions.join(" / ")}</p>}
          {createdStyle && <p className="form-message form-message-saved">{createdStyle.name}</p>}
          {message && <p className="form-message form-message-saved">{message}</p>}
        </article>

        <article className="panel sample-library-panel">
          {samples.length ? (
            <div className="sample-list">
              {samples.map(sample => (
                <div className="sample-card sample-library-card" key={sample.id}>
                  <div className="sample-card-header">
                    <div>
                      <p className="eyebrow">{sample.tags?.join(" / ") || sample.status}</p>
                      <h2>{sample.video_title}</h2>
                    </div>
                    <div className="sample-card-actions">
                      <label className="field-toggle compact-toggle">
                        <input checked={selectedIds.includes(sample.id)} onChange={() => toggleSelected(sample.id)} type="checkbox" />
                        <span>{t.select}</span>
                      </label>
                      <button
                        className="secondary-action compact-action"
                        onClick={() => void updateSample(sample, { favorite: !sample.favorite })}
                        type="button"
                      >
                        <Star aria-hidden="true" fill={sample.favorite ? "currentColor" : "none"} size={16} />
                        {t.favorite}
                      </button>
                    </div>
                  </div>
                  <p className="panel-note">{sample.visual_summary}</p>
                  <dl className="sample-fields">
                    <div>
                      <dt>脚本来源</dt>
                      <dd>
                        {sample.transcript_source ?? "-"} / {sample.transcript_language ?? "-"} / {sample.opening_transcript_length ?? 0} chars
                      </dd>
                    </div>
                    <div>
                      <dt>前 5 分钟脚本</dt>
                      <dd>{sample.opening_transcript ? sample.opening_transcript.slice(0, 220) + (sample.opening_transcript.length > 220 ? "..." : "") : "-"}</dd>
                    </div>
                    <div>
                      <dt>故事设定</dt>
                      <dd>{sample.story_setup || sample.opening_hook}</dd>
                    </div>
                    <div>
                      <dt>第一冲突</dt>
                      <dd>{sample.first_conflict || sample.opening_hook}</dd>
                    </div>
                    <div>
                      <dt>第一转折</dt>
                      <dd>{sample.first_turning_point || "-"}</dd>
                    </div>
                    <div>
                      <dt>{t.rules}</dt>
                      <dd>{sample.reuse_template.join(" / ")}</dd>
                    </div>
                    <div>
                      <dt>{t.tags}</dt>
                      <dd>
                        <input
                          className="inline-input"
                          onBlur={event => void updateSample(sample, { tags: parseTags(event.target.value) })}
                          defaultValue={(sample.tags ?? []).join(", ")}
                        />
                      </dd>
                    </div>
                    <div>
                      <dt>{t.notes}</dt>
                      <dd>
                        <textarea
                          className="inline-textarea"
                          onBlur={event => void updateSample(sample, { notes: event.target.value })}
                          defaultValue={sample.notes ?? ""}
                        />
                      </dd>
                    </div>
                  </dl>
                </div>
              ))}
            </div>
          ) : (
            <p className="panel-note">{t.empty}</p>
          )}
        </article>
      </section>
    </main>
  );
}
