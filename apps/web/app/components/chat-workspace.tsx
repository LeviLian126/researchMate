// Composes the personal or project chat surface from isolated state and presentation owners.
"use client";

import { ChatComposer } from "./chat-composer";
import { ConversationThread } from "./conversation-thread";
import { ProjectQuizDrawer } from "./project-quiz-drawer";
import { useChatWorkspace } from "./use-chat-workspace";
import { Button } from "@/components/ui/button";
import { FileText, Plus, ListChecks, Library } from "lucide-react";

interface ChatWorkspaceProps {
  projectId?: string;
  projectName?: string;
  projectMode?: boolean;
}

/** Composes chat navigation, conversation, composer, and optional project quiz jobs. */
export function ChatWorkspace({
  projectId: suppliedProjectId,
  projectName,
  projectMode = false,
}: ChatWorkspaceProps) {
  const workspace = useChatWorkspace({ suppliedProjectId, projectMode });

  return (
    <main className="flex h-full min-h-0 flex-col overflow-hidden">
      <header className="sticky top-0 z-12 flex items-center justify-between border-b border-white/30 bg-white/50 px-6 py-3 backdrop-blur-md">
        <strong className="text-sm font-semibold text-foreground">
          {projectName ?? "ResearchMate"}
        </strong>
        <nav className="flex items-center gap-1" aria-label={projectMode ? "Project tools" : "Workspace tools"}>
          <Button variant="ghost" size="sm" onClick={workspace.startNewProjectChat}>
            <Plus strokeWidth={1.5} />
            New chat
          </Button>
          {!projectMode && workspace.projectId && (
            <Button variant="ghost" size="sm" asChild>
              <a href={`/app/projects/${workspace.projectId}/library`}>
                <Library strokeWidth={1.5} />
                Sources
              </a>
            </Button>
          )}
          {projectMode && (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => workspace.setQuizOpen((current) => !current)}
              >
                <ListChecks strokeWidth={1.5} />
                Quiz
              </Button>
              <Button variant="ghost" size="sm" asChild>
                <a href={`/app/projects/${workspace.projectId}/library`}>
                  <Library strokeWidth={1.5} />
                  Sources
                </a>
              </Button>
              <Button variant="ghost" size="sm" asChild>
                <a href={`/app/projects/${workspace.projectId}/research`}>
                  <FileText strokeWidth={1.5} />
                  Research report
                </a>
              </Button>
            </>
          )}
        </nav>
      </header>

      <ConversationThread
        messages={workspace.messages}
        historyLoading={workspace.historyLoading}
        sending={workspace.sending}
        slowResponse={workspace.slowResponse}
        error={workspace.error}
        degradedNotice={workspace.degradedNotice}
        projectMode={projectMode}
        projectName={projectName}
        threadEnd={workspace.threadEnd}
        onDismissError={workspace.dismissError}
        onSelectPrompt={workspace.setMessage}
        onSubmitFeedback={workspace.submitAnswerFeedback}
      />

      <ChatComposer
        documents={workspace.documents}
        projectMode={projectMode}
        uploading={workspace.uploading}
        fileInput={workspace.fileInput}
        message={workspace.message}
        webEnabled={workspace.webEnabled}
        sending={workspace.sending}
        historyLoading={workspace.historyLoading}
        hasReadyAttachments={workspace.readyAttachments.length > 0}
        onUpload={workspace.uploadFiles}
        onSubmit={workspace.submitQuestion}
        onMessageChange={workspace.setMessage}
        onWebEnabledChange={workspace.setWebEnabled}
      />

      {projectMode && workspace.quizOpen && (
        <ProjectQuizDrawer
          prompt={workspace.quizPrompt}
          quiz={workspace.quiz}
          loading={workspace.quizLoading}
          onPromptChange={workspace.setQuizPrompt}
          onSubmit={workspace.generateQuiz}
          onClose={() => workspace.setQuizOpen(false)}
          onReset={() => workspace.setQuiz(null)}
        />
      )}
    </main>
  );
}
