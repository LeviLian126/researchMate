// Verifies the chat workspace hook orchestrates API calls, state, and recovery.
//
// A minimal renderHook helper drives the hook under jsdom; tests assert the
// state transitions and routing side effects without exercising real fetch.
import { act, createElement, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const apiFetchMock = vi.fn();

const routerMocks = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
}));

// Return a stable URLSearchParams singleton so useEffect dependencies that
// depend on searchParams do not re-run on every render (which the hook uses
// to detect actual route changes); a fresh instance each render would cause
// an infinite effect loop in the hermetic test environment.
const searchParamsSingleton = vi.hoisted(() => new URLSearchParams());

vi.mock("next/navigation", () => ({
  useRouter: () => routerMocks,
  useSearchParams: () => searchParamsSingleton,
}));

vi.mock("../lib/api", () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
  describeApiError: (error: unknown) => ({
    title: "Request failed",
    detail: error instanceof Error ? error.message : "Unknown error",
    kind: "error",
  }),
  fileTypeFromName: (filename: string) =>
    filename.toLowerCase().endsWith(".docx") ? "docx" : "pdf",
  idempotencyKey: (prefix: string) => `${prefix}-test`,
  mimeForFileType: (fileType: string) =>
    fileType === "docx"
      ? "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
      : "application/pdf",
}));

// Import after mocks so the module resolves the mocked dependencies.
import { useChatWorkspace } from "./use-chat-workspace";

interface HookHandle<T> {
  root: Root;
  container: HTMLDivElement;
  current: () => T;
  rerender: () => void;
  unmount: () => void;
}

/** Renders a hook through a tiny test harness so we can read its current return value. */
function renderHook<T>(hook: () => T): HookHandle<T> {
  let latest: T = undefined as unknown as T;
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);

  function HookProbe() {
    latest = hook();
    return null;
  }

  act(() => root.render(createElement(HookProbe)));

  const handle: HookHandle<T> = {
    root,
    container,
    current: () => latest,
    rerender: () => {
      act(() => root.render(createElement(HookProbe)));
    },
    unmount: () => {
      act(() => root.unmount());
      container.remove();
    },
  };
  return handle;
}

function bootstrapProject(
  name = "Climate review",
): { id: string; name: string; kind: "personal"; status: string } {
  return {
    id: "project-personal",
    name,
    kind: "personal",
    status: "active",
  };
}

function conversationRow(
  id = "conversation-1",
  title = "First chat",
): {
  id: string;
  project_id: string;
  title: string;
  created_at: string;
  updated_at: string;
} {
  return {
    id,
    project_id: "project-personal",
    title,
    created_at: "2026-08-04T00:00:00Z",
    updated_at: "2026-08-04T00:00:00Z",
  };
}

async function flushAsyncQueue(times = 20): Promise<void> {
  for (let step = 0; step < times; step += 1) {
    // eslint-disable-next-line no-await-in-loop
    await act(async () => { await Promise.resolve(); });
  }
}

describe("useChatWorkspace orchestration", () => {
  let handle: HookHandle<ReturnType<typeof useChatWorkspace>>;

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    apiFetchMock.mockReset();
    routerMocks.push.mockReset();
    routerMocks.replace.mockReset();
  });

  afterEach(() => {
    if (handle) handle.unmount();
    vi.clearAllMocks();
  });

  it("bootstraps a personal project when no suppliedProjectId is provided", async () => {
    apiFetchMock.mockResolvedValueOnce(bootstrapProject());

    handle = renderHook(() => useChatWorkspace({ projectMode: false }));

    expect(apiFetchMock).toHaveBeenCalledWith("/chat/bootstrap", {
      method: "POST",
    });

    await flushAsyncQueue();

    expect(handle.current().projectId).toBe("project-personal");
  });

  it("loads the existing conversation when bootstrap lists conversations", async () => {
    apiFetchMock.mockImplementation(async (path: string) => {
      if (path === "/chat/bootstrap") return bootstrapProject();
      if (path === "/projects/project-personal/conversations") {
        return { items: [conversationRow()] };
      }
      if (path === "/conversations/conversation-1/messages") {
        return {
          messages: [
            {
              id: "message-1",
              conversation_id: "conversation-1",
              role: "assistant",
              content: "Local evidence explains the answer.",
              citations: [],
              created_at: "2026-08-04T00:00:00Z",
            },
          ],
        };
      }
      if (path === "/conversations/conversation-1/documents") return [];
      return null;
    });

    handle = renderHook(() => useChatWorkspace({ projectMode: false }));

    await flushAsyncQueue();

    // The conversation list returns the persisted conversation, and the
    // hook loads its messages, marks history loading complete, and replaces
    // the route to include the conversation id.
    expect(handle.current().projectId).toBe("project-personal");
    expect(handle.current().messages).toHaveLength(1);
    expect(handle.current().messages[0].content).toBe(
      "Local evidence explains the answer.",
    );
    expect(routerMocks.replace).toHaveBeenCalledWith(
      "/app?conversation=conversation-1",
    );
    expect(handle.current().historyLoading).toBe(false);
  });

  it("records the bootstrap failure as a recoverable error", async () => {
    apiFetchMock.mockImplementation(async () => {
      throw new Error("bootstrap failed");
    });

    handle = renderHook(() => useChatWorkspace({ projectMode: false }));

    await flushAsyncQueue();

    expect(handle.current().projectId).toBeNull();
    expect(handle.current().historyLoading).toBe(false);
    expect(handle.current().error?.kind).toBe("error");
    expect(handle.current().error?.detail).toBe("bootstrap failed");
  });

  it("uses the supplied project id in project mode without bootstrapping", async () => {
    apiFetchMock.mockResolvedValue({ items: [] });

    handle = renderHook(() =>
      useChatWorkspace({
        suppliedProjectId: "project-supplied",
        projectMode: true,
      }),
    );

    expect(handle.current().projectId).toBe("project-supplied");
    expect(apiFetchMock).not.toHaveBeenCalledWith("/chat/bootstrap", {
      method: "POST",
    });
  });

  it("startNewProjectChat resets local state and pushes a new-project route", async () => {
    apiFetchMock.mockResolvedValue({ items: [] });
    handle = renderHook(() =>
      useChatWorkspace({
        suppliedProjectId: "project-supplied",
        projectMode: true,
      }),
    );

    await flushAsyncQueue();

    act(() => {
      handle.current().setMessage("draft");
    });

    act(() => {
      handle.current().startNewProjectChat();
    });

    expect(handle.current().messages).toEqual([]);
    expect(routerMocks.push).toHaveBeenCalledWith(
      "/app/projects/project-supplied/chat?new=1",
    );
  });

  it("startNewProjectChat in personal mode routes to /app?new=1", async () => {
    apiFetchMock.mockResolvedValue(bootstrapProject());
    handle = renderHook(() => useChatWorkspace({ projectMode: false }));

    await flushAsyncQueue();

    act(() => {
      handle.current().startNewProjectChat();
    });

    expect(routerMocks.push).toHaveBeenCalledWith("/app?new=1");
  });

  it("dismissError clears the error state", async () => {
    apiFetchMock.mockImplementation(async () => {
      throw new Error("bootstrap failed");
    });

    handle = renderHook(() => useChatWorkspace({ projectMode: false }));

    await flushAsyncQueue();

    expect(handle.current().error).not.toBeNull();
    act(() => {
      handle.current().dismissError();
    });
    expect(handle.current().error).toBeNull();
  });

  it("quizOpen is initialized to false when search params omit it", async () => {
    apiFetchMock.mockResolvedValue(bootstrapProject());
    handle = renderHook(() => useChatWorkspace({ projectMode: false }));

    await flushAsyncQueue();

    expect(handle.current().quizOpen).toBe(false);
  });
});
