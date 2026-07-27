// Verifies the public demo's deterministic state transitions and supported API surface.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { demoFetch, demoRunEvents, isPublicDemo } from "./demo";

beforeEach(() => {
  vi.stubEnv("NODE_ENV", "development");
  vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "true");
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("demo mode selection", () => {
  it("honors an explicit setting and defaults production builds to demo mode", () => {
    expect(isPublicDemo()).toBe(true);
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "false");
    expect(isPublicDemo()).toBe(false);
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "");
    vi.stubEnv("NODE_ENV", "production");
    expect(isPublicDemo()).toBe(true);
  });
});

describe("demoFetch", () => {
  it("returns copied project records and creates a normalized project", async () => {
    const first = await demoFetch<Array<Record<string, unknown>>>("/projects");
    first[0].name = "mutated by caller";
    const second = await demoFetch<Array<Record<string, unknown>>>("/projects");
    expect(second[0].name).not.toBe("mutated by caller");

    const created = await demoFetch<Record<string, unknown>>("/projects", {
      method: "POST",
      body: JSON.stringify({ name: "  New review  " }),
    });
    expect(created).toMatchObject({ name: "New review", status: "active" });
  });

  it("moves an uploaded document from uploading to ready", async () => {
    const upload = await demoFetch<{ document_id: string }>("/documents/upload-url", {
      method: "POST",
      body: JSON.stringify({
        project_id: "project-upload",
        filename: "source.docx",
        file_type: "docx",
        mime_type: "application/docx",
        size_bytes: 42,
      }),
    });
    await expect(demoFetch(`/documents/${upload.document_id}/complete`, {
      method: "POST",
    })).resolves.toMatchObject({ document_id: upload.document_id, status: "ready" });
    const documents = await demoFetch<Array<Record<string, unknown>>>(
      "/projects/project-upload/documents",
    );
    expect(documents).toContainEqual(expect.objectContaining({
      id: upload.document_id,
      filename: "source.docx",
      status: "ready",
    }));
  });

  it("creates runs and exposes their canonical state", async () => {
    const accepted = await demoFetch<{ run_id: string; status: string }>("/research-runs", {
      method: "POST",
      body: JSON.stringify({ project_id: "project-run" }),
    });
    expect(accepted.status).toBe("pending");
    await expect(demoFetch(`/runs/${accepted.run_id}`)).resolves.toMatchObject({
      run_id: accepted.run_id,
      project_id: "project-run",
      status: "succeeded",
    });
    await expect(demoFetch(`/runs/${accepted.run_id}/decisions`, {
      method: "POST",
    })).resolves.toMatchObject({ status: "accepted" });
  });

  it("serves evidence, report, quiz, evaluation, and developer views", async () => {
    await expect(demoFetch("/projects/demo/claims")).resolves.toMatchObject({
      items: [expect.objectContaining({ review_status: "accepted" })],
    });
    await expect(demoFetch("/projects/demo/claim-relations")).resolves.toMatchObject({
      items: [expect.objectContaining({ relation: "contradicts" })],
    });
    await expect(demoFetch("/ask", { method: "POST" })).resolves.toMatchObject({
      validation_status: "passed",
      citations: [expect.any(Object)],
    });
    await expect(demoFetch("/reports/report-1")).resolves.toMatchObject({
      sections: [expect.objectContaining({ validation_status: "passed" })],
    });
    await expect(demoFetch("/quiz", { method: "POST" })).resolves.toMatchObject({
      questions: [expect.objectContaining({ type: "single_choice" })],
    });
    await expect(demoFetch("/evaluation-datasets")).resolves.toMatchObject({
      items: [expect.objectContaining({ case_count: 3 })],
    });
    const evaluation = await demoFetch<{ evaluation_run_id: string }>("/evaluation-runs", {
      method: "POST",
    });
    await expect(demoFetch(`/evaluation-runs/${evaluation.evaluation_run_id}`)).resolves.toMatchObject({
      evaluation_run_id: evaluation.evaluation_run_id,
      status: "succeeded",
    });
    await expect(demoFetch("/dev/reliability?window_hours=12")).resolves.toMatchObject({
      window_hours: 12,
      success_rate: 1,
    });
    await expect(demoFetch("/dev/fault-scenarios", { method: "POST" })).resolves.toMatchObject({
      expected_recovery_state: expect.stringContaining("canonical state unchanged"),
    });
    await expect(demoFetch("/dev/traces/trace-1")).resolves.toMatchObject({
      trace_id: "trace-1",
      router_reason: "No external provider called.",
    });
  });

  it("fails clearly for an unsupported route", async () => {
    await expect(demoFetch("/missing")).rejects.toThrow(
      "Static demo does not implement GET /missing.",
    );
  });
});

describe("demoRunEvents", () => {
  it("emits the deterministic event sequence unless already aborted", async () => {
    const events: Array<{ sequence: number }> = [];
    await demoRunEvents(
      (event) => events.push(event),
      new AbortController().signal,
    );
    expect(events.map((event) => event.sequence)).toEqual([1, 2]);

    const controller = new AbortController();
    controller.abort();
    await demoRunEvents(() => {
      throw new Error("an aborted stream must not emit");
    }, controller.signal);
  });
});
