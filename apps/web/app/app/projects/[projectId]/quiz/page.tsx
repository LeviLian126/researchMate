"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ProjectNav } from "../../../../components/project-nav";
import { apiFetch, QuizSet } from "../../../../lib/api";

interface QuizHistoryResponse {
  project_id: string;
  quiz_sets: QuizSet[];
}

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
      setError(err instanceof Error ? err.message : "Quiz history could not be loaded.");
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
      setError(err instanceof Error ? err.message : "Quiz generation could not be completed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <ProjectNav projectId={projectId} current="quiz" />
      <section className="workspace-header glass-panel">
        <div>
          <p className="eyebrow">Grounded quiz</p>
          <h1>Review local evidence</h1>
          <p>Every question must bind to source citations; single-choice questions contain exactly four options.</p>
        </div>
        <div className="row-actions">
          <Link href={`/app/projects/${projectId}`}>Evidence review</Link>
          <Link href={`/app/projects/${projectId}/library`}>Library</Link>
          <button className="primary-button" type="button" onClick={generateQuiz} disabled={loading}>
            {loading ? "Generating…" : "Generate quiz"}
          </button>
        </div>
      </section>
      {error && <p className="error-banner">{error}</p>}
      <section className="quiz-list">
        {quizSets.length === 0 && <div className="glass-panel empty-state">No quiz sets. Add an indexed source before generating one.</div>}
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
                <p><strong>Answer: </strong>{question.answer}</p>
                <p><strong>Explanation: </strong>{question.explanation}</p>
                <small>{question.source_citations.length} source citation(s)</small>
              </section>
            ))}
          </article>
        ))}
      </section>
    </main>
  );
}
