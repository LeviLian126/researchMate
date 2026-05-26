import Link from "next/link";

// 渲染产品入口页，真实 OAuth 上线后可替换为 Supabase 登录按钮。
export default function HomePage() {
  return (
    <main className="landing-shell">
      <section className="hero-panel glass-panel">
        <p className="eyebrow">ResearchMate</p>
        <h1>可溯源 AI 研究学习工作台</h1>
        <p className="lead">
          上传本地资料，使用 Local-first 问答生成带引用的答案；按需切换 Web 或 Hybrid，
          并用 /quiz 生成带来源的复习题。
        </p>
        <div className="hero-actions">
          <Link className="primary-button" href="/app">
            进入工作台
          </Link>
          <a className="secondary-button" href="/dev/traces/demo">
            Developer Trace 仅管理员可见
          </a>
        </div>
        <div className="feature-grid">
          <article>
            <strong>Local-first</strong>
            <span>Auto 默认不联网，优先使用用户上传资料。</span>
          </article>
          <article>
            <strong>Sources</strong>
            <span>回答和测验都展示引用片段、页码或 URL。</span>
          </article>
          <article>
            <strong>Trace</strong>
            <span>开发者可查看脱敏路由、检索和校验过程。</span>
          </article>
        </div>
      </section>
    </main>
  );
}
