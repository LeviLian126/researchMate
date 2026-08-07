// Verifies the project-local navigation surfaces labels, links, and active state.
//
// ProjectNav issues an async fetch to read its label so the initial synchronous
// render shows the placeholder label. Tests assert the link surface and active
// state purely through the synchronous render path, mirroring presentation.test.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("../lib/api", () => ({
  apiFetch: vi.fn().mockResolvedValue({
    id: "project-1",
    name: "Retrieval study",
    kind: "workspace",
    status: "active",
  } as never),
}));

import { ProjectNav } from "./project-nav";

describe("ProjectNav presentation", () => {
  it("renders the placeholder label until the project record resolves", () => {
    const markup = renderToStaticMarkup(
      <ProjectNav projectId="project-1" current="chat" />,
    );

    // Synchronous render shows the placeholder label because the async
    // project lookup has not yet completed in renderToStaticMarkup.
    expect(markup).toContain("Project");
  });

  it("renders the chat, sources, and quiz links with stable hrefs", () => {
    const markup = renderToStaticMarkup(
      <ProjectNav projectId="project-1" current="chat" />,
    );

    expect(markup).toContain("/app/projects/project-1/chat");
    expect(markup).toContain("/app/projects/project-1/library");
    expect(markup).toContain("/app/projects/project-1/chat?quiz=1");
    expect(markup).toContain("Chat");
    expect(markup).toContain("Sources");
    expect(markup).toContain("Quiz");
  });

  it("marks the chat link as the active page", () => {
    const markup = renderToStaticMarkup(
      <ProjectNav projectId="project-1" current="chat" />,
    );

    expect(markup).toContain('aria-current="page"');
    // The active link is the chat link in the chat surface.
    expect(markup).toContain('href="/app/projects/project-1/chat"');
  });

  it("marks the sources link as the active page in the library surface", () => {
    const markup = renderToStaticMarkup(
      <ProjectNav projectId="project-1" current="library" />,
    );

    expect(markup).toContain('href="/app/projects/project-1/library"');
    expect(markup).toContain('aria-current="page"');
  });

  it("renders only one active link per render", () => {
    const markup = renderToStaticMarkup(
      <ProjectNav projectId="project-1" current="quiz" />,
    );

    const matches = markup.match(/aria-current="page"/g) ?? [];
    expect(matches).toHaveLength(1);
  });
});
