// Coordinates project discovery and creation for authenticated and public-demo workspaces.
"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { apiFetch, describeApiError, ProjectRecord, setDevToken } from "../lib/api";
import { isLocalDevelopment } from "../lib/supabase";
import { isPublicDemo } from "../lib/demo";

/** Renders the project list and its bounded create-project interaction. */
export default function ProjectListPage() {
  const local = isLocalDevelopment();
  const publicDemo = isPublicDemo();
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [name, setName] = useState("Research workspace");
  const [token, setToken] = useState("dev");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  /** Reloads projects for the active authenticated or demo identity. */
  async function loadProjects() {
    setError(null);
    setLoading(true);
    try {
      setProjects(await apiFetch<ProjectRecord[]>("/projects"));
    } catch (err) {
      setError(describeApiError(err).detail);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (local) setToken(window.localStorage.getItem("researchmate_token") || "dev");
    void loadProjects();
  }, [local]);

  /** Creates a project through the shared API client and prepends the committed result. */
  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      const project = await apiFetch<ProjectRecord>("/projects", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      setProjects((current) => [project, ...current]);
      setName("");
    } catch (err) {
      setError(describeApiError(err).detail);
    }
  }

  /** Persists a local-only development identity before reloading its isolated projects. */
  function saveToken() {
    setDevToken(token);
    void loadProjects();
  }

  return (
    <main className="app-shell">
      <section className="workspace-header glass-panel">
        <div>
          <p className="eyebrow">Portfolio demo workspace</p>
          <h1>Research projects</h1>
          <p>{local ? <>Use <code>dev</code> locally, or switch between isolated development identities.</> : publicDemo ? <>This browser-only walkthrough uses deterministic sample evidence. It does not create a cloud project or authenticate a user.</> : <>This workspace uses the verified Supabase session restored by the browser auth client.</>}</p>
        </div>
        {local && <div className="token-box">
          <label htmlFor="token">Bearer token</label>
          <input id="token" type="password" autoComplete="off" value={token} onChange={(event) => setToken(event.target.value)} />
          <button type="button" onClick={saveToken}>Apply identity</button>
        </div>}
      </section>

      <section className="content-grid two-columns">
        <form className="glass-panel stack" onSubmit={createProject}>
          <h2>Create a project</h2>
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Project name" />
          <button className="primary-button" type="submit">Create project</button>
          {error && <p className="error-banner">{error}</p>}
        </form>

        <div className="glass-panel stack">
          <h2>Available projects</h2>
          {loading && <p role="status">Loading owned projects…</p>}
          {!loading && projects.length === 0 && <p className="empty-state">No projects for this identity. Create one, then add sources.</p>}
          <div className="card-list">
            {projects.map((project) => (
              <article className="resource-card" key={project.id}>
                <div>
                  <strong>{project.name}</strong>
                  <span>{project.status}</span>
                </div>
                <div className="row-actions">
                  <Link href={`/app/projects/${project.id}/chat`}>Open workspace</Link>
                  <Link href={`/app/projects/${project.id}/library`}>Library</Link>
                  <Link href={`/app/projects/${project.id}/labs`}>Labs</Link>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
