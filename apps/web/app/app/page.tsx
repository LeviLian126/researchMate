"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { apiFetch, ProjectRecord, setDevToken } from "../lib/api";

// 渲染项目列表和本地开发 token 设置。
export default function ProjectListPage() {
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [name, setName] = useState("Research workspace");
  const [token, setToken] = useState("dev");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadProjects() {
    setError(null);
    setLoading(true);
    try {
      setProjects(await apiFetch<ProjectRecord[]>("/projects"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法加载项目");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const saved = window.localStorage.getItem("researchmate_token") || "dev";
    setToken(saved);
    void loadProjects();
  }, []);

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
      setError(err instanceof Error ? err.message : "创建项目失败");
    }
  }

  function saveToken() {
    setDevToken(token);
    void loadProjects();
  }

  return (
    <main className="app-shell">
      <section className="workspace-header glass-panel">
        <div>
          <p className="eyebrow">Workspace</p>
          <h1>项目列表</h1>
          <p>本地开发默认使用 Bearer dev；可切换 dev-user-a、dev-user-b 测试用户隔离。</p>
        </div>
        <div className="token-box">
          <label htmlFor="token">开发 Token</label>
          <input id="token" value={token} onChange={(event) => setToken(event.target.value)} />
          <button type="button" onClick={saveToken}>应用</button>
        </div>
      </section>

      <section className="content-grid two-columns">
        <form className="glass-panel stack" onSubmit={createProject}>
          <h2>创建项目</h2>
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Project name" />
          <button className="primary-button" type="submit">创建</button>
          {error && <p className="error-banner">{error}</p>}
        </form>

        <div className="glass-panel stack">
          <h2>已有项目</h2>
          {loading && <p>正在加载...</p>}
          {!loading && projects.length === 0 && <p>还没有项目。先创建一个项目，再上传资料。</p>}
          <div className="card-list">
            {projects.map((project) => (
              <article className="resource-card" key={project.id}>
                <div>
                  <strong>{project.name}</strong>
                  <span>{project.status}</span>
                </div>
                <div className="row-actions">
                  <Link href={`/app/projects/${project.id}`}>Ask</Link>
                  <Link href={`/app/projects/${project.id}/library`}>Library</Link>
                  <Link href={`/app/projects/${project.id}/quiz`}>Quiz</Link>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
