"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch, QuizSet } from "../../../../lib/api";

interface QuizHistoryResponse {
  project_id: string;
  quiz_sets: QuizSet[];
}

// 渲染测验生成和历史列表。
export default function QuizPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const [quizSets, setQuizSets] = useState<QuizSet[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadHistory() {
    try {
      const history = await apiFetch<QuizHistoryResponse>(`/projects/${projectId}/quiz`);
      setQuizSets(history.quiz_sets);
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法加载 Quiz 历史");
    }
  }

  useEffect(() => {
    void loadHistory();
  }, [projectId]);

  async function generateQuiz() {
    setError(null);
    setLoading(true);
    try {
      await apiFetch("/quiz", {
        method: "POST",
        body: JSON.stringify({
          project_id: projectId,
          prompt: "/quiz generate a grounded review set",
          selected_mode: "local_only",
          single_choice_count: 3,
          short_answer_count: 2,
        }),
      });
      await loadHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成 Quiz 失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <section className="workspace-header glass-panel">
        <div>
          <p className="eyebrow">Quiz</p>
          <h1>本地资料测验</h1>
          <p>选择题恰好 4 个选项；每题必须绑定来源引用。</p>
        </div>
        <div className="row-actions">
          <Link href={`/app/projects/${projectId}`}>Ask</Link>
          <Link href={`/app/projects/${projectId}/library`}>Library</Link>
          <button className="primary-button" type="button" onClick={generateQuiz} disabled={loading}>
            {loading ? "生成中..." : "生成 Quiz"}
          </button>
        </div>
      </section>
      {error && <p className="error-banner">{error}</p>}
      <section className="quiz-list">
        {quizSets.length === 0 && <div className="glass-panel empty-state">暂无 Quiz。先上传资料，再生成题目。</div>}
        {quizSets.map((quizSet) => (
          <article className="glass-panel quiz-card" key={quizSet.id}>
            <div className="sources-header">
              <span>Mode: {quizSet.mode}</span>
              <span>{quizSet.sources.local_chunks} citations</span>
            </div>
            {quizSet.questions.map((question, index) => (
              <section className="question-card" key={question.id}>
                <h3>{index + 1}. {question.question}</h3>
                {question.options && (
                  <ol type="A">
                    {question.options.map((option) => <li key={option}>{option}</li>)}
                  </ol>
                )}
                <p><strong>答案：</strong>{question.answer}</p>
                <p><strong>解析：</strong>{question.explanation}</p>
                <small>{question.source_citations.length} source citation(s)</small>
              </section>
            ))}
          </article>
        ))}
      </section>
    </main>
  );
}
