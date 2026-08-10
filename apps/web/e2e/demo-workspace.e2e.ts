// Proves the main workspace journey without credentials, providers, or backend services.
import { expect, test } from "@playwright/test";

test("completes the deterministic research workspace journey", async ({ page }) => {
  const browserErrors: string[] = [];
  const externalRequests: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") browserErrors.push(message.text());
  });
  page.on("pageerror", (error) => browserErrors.push(error.message));
  page.on("request", (request) => {
    if (new URL(request.url()).hostname !== "127.0.0.1") externalRequests.push(request.url());
  });
  await page.route("**/api/v1/healthz", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ status: "ok" }),
  }));

  await page.goto("/app?new=1");

  await expect(page.getByRole("heading", { name: "What can I help with?" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Welcome back" })).toHaveCount(0);
  await expect(page.getByRole("textbox", { name: "Message" })).toBeEnabled();

  const sidebar = page.locator(".app-sidebar");
  const resizeHandle = page.getByRole("separator", { name: "Resize sidebar" });
  await expect(resizeHandle).toBeVisible();
  const sidebarBeforeResize = await sidebar.boundingBox();
  const handleBounds = await resizeHandle.boundingBox();
  expect(sidebarBeforeResize).not.toBeNull();
  expect(handleBounds).not.toBeNull();
  await page.mouse.move(handleBounds!.x + handleBounds!.width / 2, handleBounds!.y + 40);
  await page.mouse.down();
  await page.mouse.move(handleBounds!.x + 72, handleBounds!.y + 40);
  await page.mouse.up();
  await expect.poll(async () => (await sidebar.boundingBox())?.width ?? 0).toBeGreaterThan(
    sidebarBeforeResize!.width + 40,
  );

  await page.getByRole("textbox", { name: "Message" }).fill("What makes retrieved evidence defensible?");
  await page.getByRole("button", { name: "Send message" }).click();

  await expect(page.getByText("What makes retrieved evidence defensible?", { exact: true })).toBeVisible();
  await expect(page.getByText(/retrieval is useful when evidence is relevant/)).toBeVisible();
  const citation = page.getByText("1. Project source, page 3", { exact: true });
  await expect(citation).toBeVisible();
  await citation.click();
  await expect(page.getByText(/Grounding and explicit source attribution/)).toBeVisible();
  await expect(page).toHaveURL(/\/app\?conversation=/);

  await page.getByRole("button", { name: "New project" }).click();
  await page.getByRole("textbox", { name: "Project name" }).fill("E2E evidence workspace");
  await page.getByRole("button", { name: "Create", exact: true }).click();

  await expect(page).toHaveURL(/\/app\/projects\/[^/]+\/chat\?new=1/);
  await expect(page.getByRole("heading", { name: "Chat in E2E evidence workspace" })).toBeVisible();
  await expect(page.getByRole("link", { name: "E2E evidence workspace" })).toBeVisible();

  await page.getByRole("button", { name: "Quiz", exact: true }).click();
  await expect(page.getByRole("complementary", { name: "Project quiz" })).toBeVisible();
  await page.getByRole("button", { name: "Generate quiz" }).click();
  await expect(page.getByText(/What makes a retrieved conclusion defensible/)).toBeVisible();

  expect(browserErrors, "unexpected browser console or runtime errors").toEqual([]);
  expect(externalRequests, "demo E2E must not call cloud services").toEqual([]);
});
