// 渲染初始化阶段的前端占位页面。
export default function HomePage() {
  return (
    <main className="shell">
      <section className="panel">
        <p className="eyebrow">ResearchMate MVP scaffold</p>
        <h1>Ask, Library, Quiz and Admin Trace contracts are ready.</h1>
        <p>
          当前阶段只固定前后端契约、库表结构、安全边界和任务拆解。
          具体页面逻辑交给后续前端 agent 实现。
        </p>
      </section>
    </main>
  );
}

