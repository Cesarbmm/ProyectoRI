import { defineConfig } from "vitest/config";
import { loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { requirePublicApiUrl } from "./scripts/deployment";

export default defineConfig(({ mode }) => {
  if (process.env.VERCEL === "1") {
    const env = loadEnv(mode, process.cwd(), "VITE_");
    requirePublicApiUrl(process.env.VITE_API_URL ?? env.VITE_API_URL);
  }
  return {
    plugins: [react()],
    server: { port: 5173, strictPort: true },
    test: {
      environment: "jsdom",
      setupFiles: ["./tests/setup.ts"],
      include: ["tests/**/*.test.{ts,tsx}"],
    },
  };
});
