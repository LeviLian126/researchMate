// Verifies the workspace sidebar renders navigation and orchestrates create/rename.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const apiFetchMock = vi.fn();
const routerMocks = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
}));
const navigationMocks = vi.hoisted(() => ({
  pathname: "/app",
  searchParams: new URLSearchParams(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => navigationMocks.pathname,
  useRouter: () => routerMocks,
  useSearchParams: () => navigationMocks.searchParams,
}));

vi.mock("../lib/api", () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
  describeApiError: (error: unknown) => ({
    title: "Request failed",
    detail: error instanceof Error ? error.message : "Unknown error",
    kind: "error",
  }),
}));

vi.mock("./brand-logo", () => ({
  BrandLogo: ({ withName }: { withName?: boolean }) => (
    <span>{withName ? "ResearchMate" : "RM"}</span>
  ),
}));

import { AppSidebar } from "./app-sidebar";

const projectsFixture = [
  {
    id: "project-alpha",
    name: "Alpha review",
    kind: "workspace",
    status: "active",
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
  },
  {
    id: "project-beta",
    name: "Beta review",
    kind: "workspace",
    status: "active",
    created_at: "2026-08-02T00:00:00Z",
    updated_at: "2026-08-02T00:00:00Z",
  },
];

const personalProject = {
  id: "project-personal",
  name: "Personal",
  kind: "personal",
  status: "active",
  created_at: "2026-07-30T00:00:00Z",
  updated_at: "2026-07-30T00:00:00Z",
};

function setupNavigation({ ok = true }: { ok?: boolean } = {}) {
  apiFetchMock.mockImplementation(async (path: string) => {
    if (!ok) throw new Error("navigation unavailable");
    if (path === "/projects") return projectsFixture;
    if (path === "/conversations") return { items: [] };
    if (path === "/chat/bootstrap") return personalProject;
    return undefined;
  });
}

async function flushAsyncQueue(times = 8): Promise<void> {
  for (let step = 0; step < times; step += 1) {
    // eslint-disable-next-line no-await-in-loop
    await act(async () => { await Promise.resolve(); });
  }
}

describe("AppSidebar navigation", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(async () => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    navigationMocks.pathname = "/app";
    navigationMocks.searchParams = new URLSearchParams();
    apiFetchMock.mockReset();
    routerMocks.push.mockReset();
    routerMocks.replace.mockReset();
    // Reset sidebar persistence between tests so the initial collapsed
    // state reflects the (default narrow) jsdom viewport every time.
    window.localStorage.removeItem("researchmate_sidebar_collapsed");
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    window.localStorage.removeItem("researchmate_sidebar_collapsed");
    vi.clearAllMocks();
  });

  it("loads and lists owned workspace projects after bootstrap", async () => {
    setupNavigation({ ok: true });

    await act(async () => root.render(<AppSidebar />));
    await flushAsyncQueue();

    expect(apiFetchMock).toHaveBeenCalledWith("/projects");
    expect(apiFetchMock).toHaveBeenCalledWith("/conversations");
    expect(apiFetchMock).toHaveBeenCalledWith("/chat/bootstrap", { method: "POST" });

    // Project names are rendered in the desktop sidebar body.
    expect(container.textContent).toContain("Alpha review");
    expect(container.textContent).toContain("Beta review");
  });

  it("renders the New chat and New project actions", async () => {
    setupNavigation({ ok: true });

    await act(async () => root.render(<AppSidebar />));
    await flushAsyncQueue();

    expect(container.textContent).toContain("New chat");
    expect(container.textContent).toContain("New project");
  });

  it("marks New chat as the active page on /app when no project is selected", async () => {
    setupNavigation({ ok: true });

    await act(async () => root.render(<AppSidebar />));
    await flushAsyncQueue();

    const newChatLink = [...container.querySelectorAll("a")]
      .find((link) => link.getAttribute("href") === "/app?new=1");
    expect(newChatLink).toBeTruthy();
    expect(newChatLink?.getAttribute("aria-current")).toBe("page");
  });

  it("shows the bootstrap error notice when navigation fails to load", async () => {
    setupNavigation({ ok: false });

    await act(async () => root.render(<AppSidebar />));
    await flushAsyncQueue();

    // The sidebar surfaces the recoverable error notice to users.
    const status = container.querySelector('[role="status"]');
    expect(status?.textContent).toContain("navigation unavailable");
  });

  it("persists collapsed state to localStorage on toggle", async () => {
    setupNavigation({ ok: true });

    await act(async () => root.render(<AppSidebar />));
    await flushAsyncQueue();

    const collapseButton = [...container.querySelectorAll("button")]
      .find((button) => button.getAttribute("aria-label") === "Collapse sidebar");
    expect(collapseButton).toBeTruthy();

    act(() => collapseButton?.click());
    await act(async () => { await Promise.resolve(); });

    // The toggle stores the new collapsed value so subsequent renders are durable.
    expect(window.localStorage.getItem("researchmate_sidebar_collapsed")).toBe(
      "true",
    );
  });

  it("navigates to the new project chat after creating a project", async () => {
    setupNavigation({ ok: true });
    apiFetchMock.mockImplementation(async (path: string, init?: { method?: string }) => {
      if (path === "/projects" && init?.method === "POST") {
        return {
          id: "project-new",
          name: "Fresh project",
          kind: "workspace",
          status: "active",
          created_at: "2026-08-05T00:00:00Z",
          updated_at: "2026-08-05T00:00:00Z",
        };
      }
      if (path === "/projects") return projectsFixture;
      if (path === "/conversations") return { items: [] };
      if (path === "/chat/bootstrap") return personalProject;
      return undefined;
    });

    await act(async () => root.render(<AppSidebar />));
    await flushAsyncQueue();

    const newProjectButton = [...container.querySelectorAll("button")]
      .find((button) => button.textContent?.includes("New project"));
    expect(newProjectButton).toBeTruthy();
    act(() => newProjectButton?.click());

    await act(async () => { await Promise.resolve(); });

    const nameInput = container.querySelector<HTMLInputElement>(
      'input[aria-label="Project name"]',
    );
    expect(nameInput).toBeTruthy();
    act(() => {
      // React controlled input uses a native setter; trigger the change event manually.
      const setter = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value",
      )?.set;
      setter?.call(nameInput, "Fresh project");
      nameInput?.dispatchEvent(new Event("input", { bubbles: true }));
    });

    const form = nameInput?.closest("form");
    expect(form).toBeTruthy();
    const submit = [...(form?.querySelectorAll("button") ?? [])]
      .find((button) => button.type === "submit");
    expect(submit).toBeTruthy();

    await act(async () => submit?.click());
    await flushAsyncQueue();

    expect(routerMocks.push).toHaveBeenCalledWith(
      "/app/projects/project-new/chat?new=1",
    );
  });
});
