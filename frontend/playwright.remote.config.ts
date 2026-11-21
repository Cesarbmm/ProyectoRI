import { defineConfig } from "@playwright/test";
import { requirePublicApiUrl } from "./scripts/deployment";

const site = process.env.FIQA_FRONTEND_URL;
const api = process.env.FIQA_API_URL;
if (!site || !api) throw new Error("Set FIQA_FRONTEND_URL and FIQA_API_URL.");
if (process.env.FIQA_ALLOW_LOCAL_SMOKE !== "1") {
  requirePublicApiUrl(site);
  requirePublicApiUrl(api);
}

export default defineConfig({
  testDir: "./e2e",
  testMatch: "deployed.spec.ts",
  workers: 1,
  timeout: 180_000,
  expect: { timeout: 15_000 },
  reporter: "list",
  use: {
    baseURL: site,
    viewport: { width: 1440, height: 1000 },
    storageState: process.env.FIQA_BROWSER_STORAGE_STATE || undefined,
    screenshot: "off",
    trace: "off",
  },
});
