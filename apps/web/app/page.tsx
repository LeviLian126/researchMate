// Presents the public portfolio entry point and its evidence-first product positioning.
import Link from "next/link";

/** Introduces the bounded demo and routes visitors to the workspace or technical evidence. */
export default function HomePage() {
  return (
    <main className="landing-shell">
      <header className="landing-nav">
        <Link className="landing-brand" href="/"><span className="landing-brand__mark">R</span><span>ResearchMate</span></Link>
        <span className="landing-nav__meta">Inspectable AI engineering portfolio</span>
      </header>
      <section className="hero-panel">
        <div className="hero-copy">
          <p className="eyebrow">Personal AI engineering portfolio</p>
          <h1>Evidence you can inspect, not just an answer.</h1>
          <p className="lead">
            ResearchMate is a public engineering demo of a production-oriented Agentic RAG system:
            ingest mixed sources, reconcile claims, pause for human review, evaluate versions, and inspect recovery evidence.
          </p>
          <div className="hero-actions">
            <Link className="primary-button" href="/app">Open the demo workspace</Link>
            <a className="secondary-button" href="https://github.com/LeviLian126/researchMate/tree/main/docs">Read the engineering record</a>
          </div>
        </div>
        <aside className="hero-aside"><strong>ResearchMate keeps</strong><p>the conclusion, source excerpt, validation state, and system boundary together—so every important claim stays traceable.</p></aside>
        <div className="feature-grid">
          <article><strong>Evidence workflow</strong><span>Durable runs, claim relations, approval checkpoints, and incremental report revisions.</span></article>
          <article><strong>Evaluation</strong><span>Frozen datasets compare pipeline versions with deterministic and model-judged metrics.</span></article>
          <article><strong>Reliability</strong><span>Latency, retries, cost, failure exercises, and recovery are visible engineering evidence.</span></article>
        </div>
        <p className="portfolio-note">This is a personal portfolio demo, not a commercial SaaS. There is no billing, sales funnel, or customer acquisition goal.</p>
      </section>
    </main>
  );
}
