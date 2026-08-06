// Configures browser-like unit tests and enforces the repository coverage baseline.
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const appDir = fileURLToPath(new URL("./app", import.meta.url)).replace(/\\/g, "/");

export default defineConfig({
  resolve: {
    alias: [{ find: "@/", replacement: `${appDir}/` }],
  },
  test: {
    environment: "jsdom",
    coverage: {
      provider: "v8",
      // Cover both orchestration and presentation code instead of reporting a
      // deceptively high number from utility modules alone.
      include: ["app/lib/**/*.ts", "app/components/**/*.{ts,tsx}"],
      exclude: ["app/**/*.test.{ts,tsx}"],
      reporter: ["text", "json-summary"],
      thresholds: {
        lines: 40,
        statements: 40,
      },
    },
  },
});
