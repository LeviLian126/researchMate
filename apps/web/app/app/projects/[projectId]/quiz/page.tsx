// Implements grounded quiz generation and answer review against the authenticated quiz API.
"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ProjectNav } from "../../../../components/project-nav";
import { StateNotice } from "../../../../components/state-notice";
import { apiFetch, describeApiError, QuizSet } from "../../../../lib/api";

interface QuizHistoryResponse {
  project_id: string;
  quiz_sets: QuizSet[];
}

interface QuizGenerationResponse {
  quiz_set: QuizSet;
  run_id: string;
  trace_id: string;
  validation_status: "passed" | "failed" | "retrying";
}

/** Coordinates quiz history, generation, answer drafts, and citation-backed review. */
export default function QuizPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const [quizSets, setQuizSets] = useState<QuizSet[]>([]);
  const [activeQuizId, setActiveQuizId] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [reviewed, setReviewed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  const activeQuiz = useMemo(
    () => quizSets.find((quizSet) => quizSet.id === activeQuizId) ?? quizSets[0] ?? null,
    [activeQuizId, quizSets],
  );

  /** Reloads quiz history while preserving a still-valid active selection. */
  async function loadHistory() {
    setLoading(true);
    try {
      const history = await apiFetch<QuizHistoryResponse>(`/projects/${projectId}/quiz`);
      setQuizSets(history.quiz_sets);
      setActiveQuizId((current) => history.quiz_sets.some((quizSet) => quizSet.id === current) ? current : history.quiz_sets[0]?.id ?? null);
      setError(null);
    } catch (err) {
      setError(describeApiError(err).detail);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadHistory();
  }, [projectId]);

  /** Requests one source-grounded review set and selects it when the API commits it. */
  async function generateQuiz() {
    setError(null);
    setGenerating(true);
    try {
      const response = await apiFetch<QuizGenerationResponse | QuizSet>("/quiz", {
        method: "POST",
        body: JSON.stringify({
          project_id: projectId,
          prompt: "/quiz generate a grounded review set",
          selected_mode: "local_only",
          single_choice_count: 3,
          short_answer_count: 2,
        }),
      });
      const quiz = "quiz_set" in response ? response.quiz_set : response;
      await loadHistory();
      setActiveQuizId(quiz.id);
      setAnswers({});
      setReviewed(false);
    } catch (err) {
      setError(describeApiError(err).detail);
    } finally {
      setGenerating(false);
    }
  }

  /** Switches the visible quiz and clears drafts that belong to the previous set. */
  function chooseQuiz(quizId: string) {
    setActiveQuizId(quizId);
    setAnswers({});
    setReviewed(false);
  }

  return (
    <main className="app-shell workspace-shell">
      <ProjectNav projectId={projectId} current="quiz" />
      <header className="product-header quiz-header">
        <div><p className="eyebrow">Citation-backed learning</p><h1>Grounded quizzes</h1><p>Test your recall without losing the evidence behind each answer.</p></div>
        <button className="primary-button" type="button" onClick={generateQuiz} disabled={generating}>{generating ? "Generating…" : "Generate quiz"}</button>
      </header>

      {error && <StateNotice state={{ title: "Quiz needs attention", detail: error, kind: "error" }} action={<button type="button" onClick={() => void loadHistory()}>Retry</button>} />}

      <section className="quiz-workspace" aria-label="Quiz workspace">
        <aside className="quiz-history" aria-labelledby="quiz-history-heading">
          <div className="section-heading"><h2 id="quiz-history-heading">Quiz sets</h2><span>{quizSets.length}</span></div>
          {loading && <div className="empty-state" role="status">Loading quiz history…</div>}
          {!loading && quizSets.length === 0 && <div className="empty-state">No quiz sets yet. Add a ready source in the Library, then generate one.</div>}
          {quizSets.map((quizSet, index) => (
            <button className="quiz-history-card" aria-pressed={activeQuiz?.id === quizSet.id} key={quizSet.id} type="button" onClick={() => chooseQuiz(quizSet.id)}>
              <small>Set {quizSets.length - index} · {quizSet.mode.replaceAll("_", " ")}</small>
              <strong>{quizSet.questions[0]?.question || "Grounded review"}</strong>
              <span>{quizSet.questions.length} questions · {quizSet.sources.local_chunks} local sources</span>
            </button>
          ))}
        </aside>

        <section className="quiz-stage" aria-live="polite">
          {!activeQuiz ? <div className="quiz-empty"><span aria-hidden="true">?</span><h2>Build a quiz from your research</h2><p>Questions, answers, explanations, and citations are generated from ready project sources.</p><button className="primary-button" type="button" onClick={generateQuiz} disabled={generating}>{generating ? "Generating…" : "Generate the first quiz"}</button></div> : (
            <>
              <div className="quiz-stage__header">
                <div><p className="eyebrow">Active review set</p><h2>Evidence comprehension check</h2><p>{activeQuiz.questions.length} questions · {activeQuiz.sources.local_chunks} local chunks · {activeQuiz.sources.web_pages} web pages</p></div>
                <button type="button" onClick={() => { setAnswers({}); setReviewed(false); }}>Reset answers</button>
              </div>
              <div className="question-list">
                {activeQuiz.questions.map((question, index) => {
                  const currentAnswer = answers[question.id] ?? "";
                  const isCorrect = currentAnswer.trim().toLowerCase() === question.answer.trim().toLowerCase();
                  return (
                    <article className="interactive-question" key={question.id}>
                      <div className="interactive-question__meta"><span>Question {index + 1}</span><span>{question.type === "single_choice" ? "Multiple choice" : "Short answer"}</span><span>{question.difficulty}</span></div>
                      <h3>{question.question}</h3>
                      {question.options ? (
                        <fieldset className="answer-options"><legend className="sr-only">Answer question {index + 1}</legend>{question.options.map((option) => (
                          <label className="answer-option" key={option}><input type="radio" name={question.id} value={option} checked={currentAnswer === option} onChange={(event) => setAnswers((current) => ({ ...current, [question.id]: event.target.value }))} /><span>{option}</span></label>
                        ))}</fieldset>
                      ) : <label><span className="sr-only">Your answer</span><textarea rows={3} value={currentAnswer} onChange={(event) => setAnswers((current) => ({ ...current, [question.id]: event.target.value }))} placeholder="Write a concise answer…" /></label>}
                      {reviewed && <div className={`answer-review ${isCorrect ? "answer-review--correct" : "answer-review--incorrect"}`}><strong>{isCorrect ? "Correct" : "Review the source-backed answer"}</strong><p><b>Answer:</b> {question.answer}</p><p>{question.explanation}</p><small>{question.source_citations.length} source citation{question.source_citations.length === 1 ? "" : "s"}</small></div>}
                    </article>
                  );
                })}
              </div>
              <div className="quiz-submit"><button className="primary-button" type="button" onClick={() => setReviewed(true)}>Check answers</button><span>{Object.keys(answers).length} of {activeQuiz.questions.length} answered</span></div>
            </>
          )}
        </section>
      </section>
    </main>
  );
}
