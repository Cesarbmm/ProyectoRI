import { expect, it } from "vitest";
import { requirePublicApiUrl } from "../scripts/deployment";

it.each([
  undefined,
  "",
  "http://api.example.org",
  "https://localhost:8000",
  "https://127.0.0.1:8000",
  "https://192.168.1.20",
  "https://[::1]",
  "https://user:password@api.example.org",
  "https://api.example.org?token=example",
])("rejects an unusable public deployment backend: %s", (value) => {
  expect(() => requirePublicApiUrl(value)).toThrow();
});

it("accepts a public HTTPS backend with a path prefix", () => {
  expect(requirePublicApiUrl(" https://fiqa.example.org/api ").href).toBe(
    "https://fiqa.example.org/api",
  );
});
