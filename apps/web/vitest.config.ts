// Configures browser-like unit tests and enforces the repository coverage baseline.
import { defineConfig } from "vitest/config";

export default defineConfig({
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
