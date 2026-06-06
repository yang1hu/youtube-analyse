import { Save } from "lucide-react";

export default function Settings() {
  return (
    <main className="app-shell workspace-page">
      <section className="page-intro" aria-labelledby="settings-title">
        <p className="eyebrow">Workspace setup</p>
        <h1 id="settings-title">Settings</h1>
        <p className="hero-summary">
          Save the source video and channel URLs that the analysis workflow should use first.
        </p>
      </section>

      <section className="settings-layout" aria-label="Source settings">
        <form className="panel settings-form">
          <label className="field-group">
            <span>Video URL</span>
            <input
              name="videoUrl"
              placeholder="https://www.youtube.com/watch?v=..."
              type="url"
            />
          </label>

          <label className="field-group">
            <span>Channel URL</span>
            <input
              name="channelUrl"
              placeholder="https://www.youtube.com/@channel"
              type="url"
            />
          </label>

          <button className="primary-action" type="button">
            <Save aria-hidden="true" size={18} />
            <span>Save Source</span>
          </button>
        </form>
      </section>
    </main>
  );
}
