// Verifies client API authorization, error mapping, streaming, and file metadata helpers.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  apiFetch,
  describeApiError,
  fileTypeFromName,
  getDevToken,
  idempotencyKey,
  mimeForFileType,
  setDevToken,
  streamRunEvents,
} from "./api";

beforeEach(() => {
  vi.stubEnv("NODE_ENV", "development");
  vi.stubEnv("NEXT_PUBLIC_APP_ENV", "local");
  vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "false");
  window.localStorage.clear();
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("local API identity", () => {
  it("uses and updates the local development token", () => {
    expect(getDevToken()).toBe("dev");
    setDevToken("researcher-token");
    expect(getDevToken()).toBe("researcher-token");
    setDevToken("");
    expect(getDevToken()).toBe("dev");
  });

  it("rejects a development token outside local development", () => {
    vi.stubEnv("NODE_ENV", "production");
    expect(() => getDevToken()).toThrowError(
      expect.objectContaining({ code: "AUTH_REQUIRED", status: 401 }),
    );
  });
});

describe("apiFetch", () => {
  it("adds JSON and bearer headers and returns the decoded body", async () => {
    setDevToken("local-user");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ project_id: "p1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(apiFetch("/projects", { method: "POST", body: "{}" })).resolves.toEqual({
      project_id: "p1",
    });
    const [, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer local-user");
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  it("maps structured and unstructured HTTP failures", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({
        error: { code: "PROJECT_LOCKED", message: "Project is locked.", request_id: "req-1" },
      }), { status: 409 }))
      .mockResolvedValueOnce(new Response("not-json", { status: 502 }));

    await expect(apiFetch("/projects/p1")).rejects.toEqual(
      expect.objectContaining({
        code: "PROJECT_LOCKED",
        message: "Project is locked.",
        requestId: "req-1",
        status: 409,
      }),
    );
    await expect(apiFetch("/projects/p1")).rejects.toEqual(
      expect.objectContaining({ code: "HTTP_502", status: 502 }),
    );
  });
});

describe("streamRunEvents", () => {
  it("emits valid SSE data frames and skips malformed frames", async () => {
    const encoder = new TextEncoder();
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode('data: {"sequence":1,"node_key":"retrieve"}\n\n'));
        controller.enqueue(encoder.encode("event: ping\n\ndata: invalid-json\n\n"));
        controller.close();
      },
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(body, { status: 200 }));
    const events: Array<Record<string, unknown>> = [];

    await streamRunEvents(
      "run-1",
      0,
      (event) => events.push(event as unknown as Record<string, unknown>),
      new AbortController().signal,
    );

    expect(events).toEqual([{ sequence: 1, node_key: "retrieve" }]);
  });

  it("reports a missing stream body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      body: null,
    } as Response);

    await expect(streamRunEvents(
      "run-1",
      0,
      () => undefined,
      new AbortController().signal,
    )).rejects.toEqual(expect.objectContaining({ code: "EVENT_STREAM_UNAVAILABLE" }));
  });
});

describe("presentation helpers", () => {
  it.each([
    [new ApiError("sign in", 401, "AUTH_REQUIRED"), "Authentication required", "auth"],
    [new ApiError("forbidden", 403, "FORBIDDEN"), "Developer access required", "permission"],
    [new ApiError("changed", 409, "CONFLICT"), "State changed", "conflict"],
    [new ApiError("limited", 429, "LIMIT"), "Usage limit reached", "limit"],
    [new ApiError("offline", 503, "OFFLINE"), "Provider or service unavailable", "provider"],
    [new ApiError("bad input", 422, "BAD_INPUT"), "BAD INPUT", "validation"],
  ])("describes status-specific API errors", (error, title, kind) => {
    expect(describeApiError(error)).toMatchObject({ title, kind });
  });

  it("describes ordinary and unknown client failures", () => {
    expect(describeApiError(new Error("network down"))).toEqual({
      title: "Request could not be completed",
      detail: "network down",
      kind: "error",
    });
    expect(describeApiError(null).detail).toBe("Unknown client error.");
  });

  it("maps filenames and MIME types without case sensitivity", () => {
    expect(fileTypeFromName("PAPER.DOCX")).toBe("docx");
    expect(fileTypeFromName("slides.pptx")).toBe("pptx");
    expect(fileTypeFromName("notes.txt")).toBe("pdf");
    expect(mimeForFileType("docx")).toContain("wordprocessingml");
    expect(mimeForFileType("pptx")).toContain("presentationml");
    expect(mimeForFileType("pdf")).toBe("application/pdf");
  });

  it("prefixes generated idempotency keys", () => {
    expect(idempotencyKey("upload")).toMatch(/^upload-.+/);
  });
});
