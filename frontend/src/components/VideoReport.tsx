import { ChartNoAxesCombined, ListChecks, MessageSquareText, Sparkles } from "lucide-react";

const reportSections = [
  {
    title: "Hook",
    label: "Opening read",
    body: "Strong first question, then a quick proof clip before the title card.",
    icon: Sparkles
  },
  {
    title: "Structure",
    label: "Retention map",
    body: "Three-part build: problem, failed attempts, then practical resolution.",
    icon: ListChecks
  },
  {
    title: "Growth Judgement",
    label: "Channel fit",
    body: "Likely repeatable because the format creates a clear viewer promise.",
    icon: ChartNoAxesCombined
  },
  {
    title: "Comment Insights",
    label: "Audience signal",
    body: "Early comments ask for templates, follow-up examples, and pricing context.",
    icon: MessageSquareText
  }
];

export default function VideoReport() {
  return (
    <main className="app-shell workspace-page">
      <section className="page-intro" aria-labelledby="video-report-title">
        <p className="eyebrow">Video workbench</p>
        <h1 id="video-report-title">Video Report</h1>
        <p className="hero-summary">
          Preview the report sections that will turn a single upload into editorial and growth
          decisions.
        </p>
      </section>

      <section className="report-layout" aria-label="Report preview">
        <article className="panel report-summary">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">MVP preview</p>
              <h2>Report Snapshot</h2>
            </div>
            <ChartNoAxesCombined aria-hidden="true" size={22} />
          </div>
          <p className="panel-note">
            This workbench is built for review, not chat. Each section is a compact readout that
            can later connect to the analysis pipeline.
          </p>
          <div className="score-strip" aria-label="Report scores">
            <span>Clarity 82</span>
            <span>Retention 76</span>
            <span>Novelty 68</span>
          </div>
        </article>

        <div className="report-section-list">
          {reportSections.map(section => {
            const Icon = section.icon;

            return (
              <article className="panel report-section" key={section.title}>
                <div className="section-icon">
                  <Icon aria-hidden="true" size={20} />
                </div>
                <div>
                  <p className="eyebrow">{section.label}</p>
                  <h2>{section.title}</h2>
                  <p>{section.body}</p>
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </main>
  );
}
