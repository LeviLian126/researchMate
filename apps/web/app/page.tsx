import Link from "next/link";

export default function HomePage() {
  return (
    <main className="landing-shell">
      <section className="hero-panel glass-panel">
        <p className="eyebrow">Personal AI engineering portfolio</p>
        <h1>Evidence you can inspect, not just an answer.</h1>
        <p className="lead">
          ResearchMate is a public engineering demo of a production-oriented Agentic RAG system:
          ingest mixed sources, reconcile claims, pause for human review, evaluate versions, and inspect recovery evidence.
        </p>
        <div className="hero-actions">
          <Link className="primary-button" href="/app">
            Open the demo workspace
          </Link>
          <a className="secondary-button" href="/docs/">Read the engineering documentation</a>
        </div>
        <div className="feature-grid">
          <article>
            <strong>Evidence workflow</strong>
            <span>Durable runs, claim relations, approval checkpoints, and incremental report revisions.</span>
          </article>
          <article>
            <strong>Evaluation</strong>
            <span>Frozen datasets compare pipeline versions with deterministic and model-judged metrics.</span>
          </article>
          <article>
            <strong>Reliability</strong>
            <span>Latency, retries, cost, failure exercises, and recovery are visible engineering evidence.</span>
          </article>
        </div>
        <p className="portfolio-note">This is a personal portfolio demo, not a commercial SaaS. There is no billing, sales funnel, or customer acquisition goal.</p>
      </section>
    </main>
  );
}
