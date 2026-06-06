import { AlertTriangle, ClipboardList, Lightbulb, Sparkles } from "lucide-react";

export default function IdeaLab() {
  return (
    <main className="app-shell workspace-page">
      <section className="page-intro" aria-labelledby="idea-lab-title">
        <p className="eyebrow">Idea pipeline</p>
        <h1 id="idea-lab-title">Idea Lab</h1>
        <p className="hero-summary">
          Shape generated concepts into video candidates with clear angles, risks, and next steps.
        </p>
      </section>

      <section className="idea-layout" aria-label="Idea lab preview">
        <article className="panel idea-empty">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Empty state</p>
              <h2>Waiting for ideas</h2>
            </div>
            <Lightbulb aria-hidden="true" size={22} />
          </div>
          <p className="panel-note">
            Generated ideas will appear with an angle, why it matters, outline, risk, score, and
            production status.
          </p>
        </article>

        <article className="idea-preview" aria-label="Generated idea preview">
          <div className="idea-preview-header">
            <div>
              <p className="eyebrow">Generated card</p>
              <h2>Turn audience objections into a teardown series</h2>
            </div>
            <span className="status-pill">Draft</span>
          </div>

          <dl className="idea-fields">
            <div>
              <dt>Angle</dt>
              <dd>Use real comments as the spine for each episode.</dd>
            </div>
            <div>
              <dt>Why</dt>
              <dd>It answers visible demand and gives viewers a reason to comment.</dd>
            </div>
            <div>
              <dt>Outline</dt>
              <dd>Open with the objection, test it, show the fix, then ask for the next case.</dd>
            </div>
            <div>
              <dt>Risk</dt>
              <dd>Needs careful selection so the premise stays useful instead of reactive.</dd>
            </div>
          </dl>

          <div className="idea-footer">
            <span>
              <Sparkles aria-hidden="true" size={16} />
              Score 84
            </span>
            <span>
              <ClipboardList aria-hidden="true" size={16} />
              Ready for outline
            </span>
            <span>
              <AlertTriangle aria-hidden="true" size={16} />
              Medium risk
            </span>
          </div>
        </article>
      </section>
    </main>
  );
}
