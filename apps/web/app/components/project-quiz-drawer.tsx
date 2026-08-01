// Renders project quiz instructions, generation progress, and generated question review.
import type { FormEvent } from "react";
import type { QuizSet } from "../lib/api";

interface ProjectQuizDrawerProps {
  prompt: string;
  quiz: QuizSet | null;
  loading: boolean;
  onPromptChange: (prompt: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onClose: () => void;
  onReset: () => void;
}

/** Presents quiz generation without promising complete ready-resource coverage. */
export function ProjectQuizDrawer({
  prompt,
  quiz,
  loading,
  onPromptChange,
  onSubmit,
  onClose,
  onReset,
}: ProjectQuizDrawerProps) {
  return (
    <aside className="quiz-drawer" aria-label="Project quiz">
      <div className="quiz-drawer__header">
        <div><strong>Project quiz</strong><small>Uses available indexed project resources</small></div>
        <button type="button" onClick={onClose} aria-label="Close quiz">×</button>
      </div>
      {!quiz ? (
        <form onSubmit={onSubmit}>
          <textarea
            rows={3}
            value={prompt}
            onChange={(event) => onPromptChange(event.target.value)}
            placeholder="Optional instructions, topics, or difficulty"
          />
          <p>Default: 3 multiple choice, 2 fill-in, and 2 subjective questions.</p>
          <button type="submit" disabled={loading}>
            {loading ? "Generating…" : "Generate quiz"}
          </button>
        </form>
      ) : (
        <div className="quiz-drawer__questions">
          {quiz.questions.map((question, index) => (
            <details key={question.id}>
              <summary>{index + 1}. {question.question}</summary>
              {question.options && (
                <ol>{question.options.map((option) => <li key={option}>{option}</li>)}</ol>
              )}
              <p><strong>Answer:</strong> {question.answer}</p>
              <small>{question.explanation}</small>
            </details>
          ))}
          <button type="button" onClick={onReset}>Generate another</button>
        </div>
      )}
    </aside>
  );
}
