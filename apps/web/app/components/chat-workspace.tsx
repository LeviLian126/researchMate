// Composes the personal or project chat surface from isolated state and presentation owners.
"use client";

import { ChatComposer } from "./chat-composer";
import { ConversationThread } from "./conversation-thread";
import { ProjectQuizDrawer } from "./project-quiz-drawer";
import { useChatWorkspace } from "./use-chat-workspace";

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
    <main className="conversation-shell">
      {projectMode && (
        <header className="conversation-topbar">
          <strong>{projectName ?? "Project"}</strong>
          <nav aria-label="Project tools">
            <button type="button" onClick={workspace.startNewProjectChat}>New chat</button>
            <button type="button" onClick={() => workspace.setQuizOpen((current) => !current)}>
              Quiz
            </button>
            <a href={`/app/projects/${workspace.projectId}/library`}>Sources</a>
          </nav>
        </header>
      )}

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
