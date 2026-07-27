// Configures browser-like unit tests and enforces the repository coverage baseline.
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    coverage: {
      provider: "v8",
      include: ["app/lib/**/*.ts"],
      reporter: ["text", "json-summary"],
      thresholds: {
        lines: 50,
        statements: 50,
      },
    },
  },
});
