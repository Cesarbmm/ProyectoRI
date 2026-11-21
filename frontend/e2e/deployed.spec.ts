import { expect, test } from "@playwright/test";
import { chooseModel } from "./helpers";
import { readFileSync } from "node:fs";
import { ACTIVE_MODEL_IDS, type ModelId, LABELS } from "../src/lib/types";

const benchmarkData = JSON.parse(
  readFileSync(new URL("../src/data/benchmark.json", import.meta.url), "utf8"),
) as { current: { model: ModelId; metrics: Record<string, number> }[] };

test("public site searches four active systems, defaults to BGE and keeps historical evaluation", async ({
  page,
  request,
  baseURL,
}) => {
  const api = process.env.FIQA_API_URL!.replace(/\/+$/, "");
  const origin = new URL(baseURL!).origin;
  // Authenticate only this project's Preview, never API or third-party requests.
  // The short-lived token is injected by `vercel env run`, not bundled in Vite.
  if (process.env.VERCEL_OIDC_TOKEN) {
    await page.route(`${origin}/**`, (route) =>
      route.continue({
        headers: {
          ...route.request().headers(),
          "x-vercel-trusted-oidc-idp-token": process.env.VERCEL_OIDC_TOKEN!,
        },
      }),
    );
  }
  const health = await request.get(`${api}/health`, {
    headers: { Origin: origin },
  });
  expect(health.status()).toBe(200);
  expect(health.headers()["access-control-allow-origin"]).toBe(origin);
  expect((await health.json()).service).toBe("fiqa-ir");
  const ready = await request.get(`${api}/ready`);
  expect(ready.status()).toBe(200);
  expect((await ready.json()).lexical_preprocessing).toBe("stemming");
  const models = [...ACTIVE_MODEL_IDS];
  const catalog = await request.get(`${api}/models`);
  expect(catalog.status()).toBe(200);
  const available = await catalog.json();
  expect(
    available.models
      .map((model: { id: string }) => model.id)
      .filter((id: string) => id !== "hybrid")
      .sort(),
  ).toEqual([...models].sort());
  expect(available.lexical_configuration).toEqual({
    morphology: "stemming",
    bm25_k1: 0.8,
    bm25_b: 0.75,
  });
  const cors = await request.fetch(`${api}/search/compare`, {
    method: "OPTIONS",
    headers: {
      Origin: origin,
      "Access-Control-Request-Method": "POST",
      "Access-Control-Request-Headers": "content-type",
    },
  });
  expect(cors.status()).toBe(200);
  expect(cors.headers()["access-control-allow-origin"]).toBe(origin);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByText("Search engine connected", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Results", { exact: true }).selectOption("3");
  await expect(page.getByLabel("Retrieval model")).toHaveText(
    "Default (BGE + FAISS)",
  );
  await expect(page.locator(".brand-caption")).toHaveText("Financial Search");
  await page.getByLabel("Retrieval model").click();
  await expect(page.getByRole("listbox").getByRole("option")).toHaveCount(4);
  await expect(
    page.getByRole("option", { name: /hybrid|automatic/i }),
  ).toHaveCount(0);
  await page.keyboard.press("Escape");
  await page
    .getByLabel("Query", { exact: true })
    .fill("What is the difference between APR and APY?");
  for (const model of [
    "bge",
    ...models.filter((model) => model !== "bge"),
  ] as const) {
    await chooseModel(page, model);
    const done = page.waitForResponse(
      (response) =>
        response.url() === `${api}/search` &&
        response.request().method() === "POST",
    );
    await page.getByLabel("Query", { exact: true }).press("Enter");
    const response = await done;
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.model).toBe(model);
    expect(data.count).toBe(3);
    await expect(page.locator(".result")).toHaveCount(3);
    await expect(page.locator(".document-preview").first()).toHaveText(
      data.results[0].preview,
    );
    await expect(page.locator(".technical-score code").first()).toHaveText(
      String(data.results[0].score),
    );
    if (model === "bge")
      await expect(
        page.getByText("Default model: BGE + FAISS", { exact: true }),
      ).toBeVisible();
    if (model === "bge") expect(data.results[0].doc_id).toBe("263225");
  }
  await page.getByLabel("Compare models", { exact: true }).check();
  await expect(page.getByRole("checkbox")).toHaveCount(5);
  await expect(page.getByRole("checkbox", { name: /hybrid/i })).toHaveCount(0);
  for (const model of models)
    await page.getByLabel(LABELS[model], { exact: true }).check();
  const done = page.waitForResponse(
    (response) => response.url() === `${api}/search/compare`,
  );
  await page.getByLabel("Query", { exact: true }).press("Enter");
  const compared = await done;
  expect(compared.status()).toBe(200);
  const comparison = await compared.json();
  expect(comparison.rankings).toHaveLength(4);
  await expect(page.locator(".ranking")).toHaveCount(4);
  for (const ranking of comparison.rankings) {
    const section = page.getByRole("region", {
      name: `Ranking ${LABELS[ranking.model as ModelId]}`,
      exact: true,
    });
    await expect(section.locator(".document-preview").first()).toHaveText(
      ranking.results[0].preview,
    );
  }
  await page.getByRole("link", { name: "Evaluation", exact: true }).click();
  await expect(page.getByRole("table").locator("tbody tr")).toHaveCount(5);
  for (const row of benchmarkData.current) {
    const tr = page.getByRole("row").filter({
      has: page.getByRole("rowheader", {
        name:
          row.model === "hybrid"
            ? `${LABELS.hybrid} (historical)`
            : LABELS[row.model as ModelId],
        exact: true,
      }),
    });
    await expect(tr.getByRole("cell").first()).toHaveText(
      row.metrics["MAP@1000"].toFixed(6),
    );
  }
  await expect(page.locator(".highlight-row")).toContainText("BGE + FAISS");
  await expect(page.locator(".recommended-bar")).toHaveCount(1);
  await expect(
    page
      .locator(".chart-row")
      .filter({ hasText: "Hybrid" })
      .locator(".recommended-bar"),
  ).toHaveCount(0);
  expect(errors).toEqual([]);
});
