// Renders project quiz instructions, generation progress, and generated question review.
import type { FormEvent } from "react";
import type { QuizSet } from "../lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { GraduationCap, Loader2, RefreshCw, X } from "lucide-react";

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
    <aside
      className="fixed right-0 top-0 bottom-0 z-50 w-[min(430px,calc(100vw-68px))] overflow-y-auto border-l border-white/30 bg-white/80 p-5 backdrop-blur-xl shadow-xl scrollbar-thin"
      aria-label="Project quiz"
    >
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <strong className="text-sm font-semibold text-foreground">Project quiz</strong>
          <small className="mt-0.5 block text-xs text-muted-foreground">
            Uses available indexed project resources
          </small>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={onClose}
          aria-label="Close quiz"
          className="h-7 w-7 shrink-0 rounded-full"
        >
          <X strokeWidth={1.5} />
        </Button>
      </div>
      {!quiz ? (
        <form onSubmit={onSubmit} className="space-y-3">
          <Textarea
            rows={3}
            value={prompt}
            onChange={(event) => onPromptChange(event.target.value)}
            placeholder="Optional instructions, topics, or difficulty"
            className="resize-none text-sm"
          />
          <p className="text-xs text-muted-foreground">
            Default: 3 multiple choice, 2 fill-in, and 2 subjective questions.
          </p>
          <Button type="submit" disabled={loading} className="w-full">
            {loading ? (
              <>
                <Loader2 className="animate-spin" strokeWidth={1.5} />
                Generating…
              </>
            ) : (
              <>
                <GraduationCap strokeWidth={1.5} />
                Generate quiz
              </>
            )}
          </Button>
        </form>
      ) : (
        <div className="space-y-3">
          {quiz.questions.map((question, index) => (
            <details
              key={question.id}
              className="rounded-lg border border-border/60 bg-white/50 p-3 backdrop-blur-sm"
            >
              <summary className="cursor-pointer text-sm font-medium text-foreground">
                {index + 1}. {question.question}
              </summary>
              <div className="mt-2 space-y-2">
                {question.options && (
                  <ol className="ml-4 list-decimal space-y-1 text-xs text-muted-foreground">
                    {question.options.map((option) => (
                      <li key={option}>{option}</li>
                    ))}
                  </ol>
                )}
                <p className="text-xs text-foreground">
                  <strong>Answer:</strong> {question.answer}
                </p>
                <small className="block text-xs italic text-muted-foreground">
                  {question.explanation}
                </small>
              </div>
            </details>
          ))}
          <Button type="button" variant="outline" onClick={onReset} className="w-full">
            <RefreshCw strokeWidth={1.5} />
            Generate another
          </Button>
        </div>
      )}
    </aside>
  );
}
