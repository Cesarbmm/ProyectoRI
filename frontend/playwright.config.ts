import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
const localPython = resolve(
  "..",
  ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);
const python =
  process.env.FIQA_PYTHON || (existsSync(localPython) ? localPython : "python");
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 150_000,
  expect: { timeout: 12_000 },
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: { mode: "retain-on-failure", screenshots: false },
    screenshot: "off",
  },
  webServer: [
    {
      command: "npm run dev",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: !process.env.CI,
    },
    {
      command: `"${python}" -m uvicorn ri_fiqa.api:app --host 127.0.0.1 --port 8000`,
      cwd: "..",
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: !process.env.CI,
      env: { HF_HUB_OFFLINE: "1" },
      timeout: 60_000,
    },
  ],
  projects: [
    {
      name: "desktop",
      testMatch: "ui.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
      },
    },
    {
      name: "tablet",
      testMatch: "ui.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 820, height: 1180 },
        hasTouch: true,
      },
    },
    {
      name: "mobile",
      testMatch: "ui.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
    {
      name: "real-api",
      testMatch: "real.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
      },
    },
  ],
});
