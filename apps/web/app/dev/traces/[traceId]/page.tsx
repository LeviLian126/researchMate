"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch, DeveloperTrace } from "../../../lib/api";

// 渲染开发者可见的脱敏 Trace 页面。
export default function TracePage() {
  const params = useParams<{ traceId: string }>();
  const traceId = params.traceId;
  const [trace, setTrace] = useState<DeveloperTrace | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadTrace() {
      try {
        setTrace(await apiFetch<DeveloperTrace>(`/dev/traces/${traceId}`));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Trace 不存在或无权限");
      }
    }
    void loadTrace();
  }, [traceId]);

  return (
    <main className="app-shell">
      <section className="workspace-header glass-panel">
        <div>
          <p className="eyebrow">Developer Trace</p>
          <h1>脱敏执行链路</h1>
          <p>普通用户 token 无法访问本页；页面不展示 API key、OAuth token 或 signed secret。</p>
        </div>
        <Link className="secondary-button" href="/app">返回项目</Link>
      </section>
      {error && <p className="error-banner">{error}</p>}
      {trace && (
        <section className="content-grid two-columns">
          <article className="glass-panel stack">
            <h2>Plan</h2>
            <pre>{JSON.stringify(trace.execution_plan, null, 2)}</pre>
            <h2>Validation</h2>
            <pre>{JSON.stringify(trace.validation_result, null, 2)}</pre>
          </article>
          <article className="glass-panel stack">
            <h2>Retrieved chunks</h2>
            <pre>{JSON.stringify(trace.retrieved_chunks, null, 2)}</pre>
            <h2>Tool calls</h2>
            <pre>{JSON.stringify(trace.tool_calls, null, 2)}</pre>
          </article>
        </section>
      )}
    </main>
  );
}
