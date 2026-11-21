import { chooseModel } from "./helpers";
import { test, expect } from "@playwright/test";
import { resolve } from "node:path";
import { mkdir } from "node:fs/promises";

test("flujo completo contra FastAPI y corpus reales; capturas de entrega", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  const ready = await request.get("http://127.0.0.1:8000/ready");
  expect(ready.ok()).toBe(true);
  expect((await ready.json()).lexical_preprocessing).toBe("stemming");
  const shots = resolve("../docs/capturas");
  await mkdir(shots, { recursive: true });
  await page.setViewportSize({ width: 1488, height: 1057 });
  await page.goto("/");
  await expect(
    page.getByText("Search engine connected", { exact: true }),
  ).toBeVisible();
  if (process.env.FIQA_CAPTURE === "1")
    await page.screenshot({
      animations: "disabled",
      path: resolve(shots, "inicio.png"),
      fullPage: true,
    });
  await page.getByLabel("Retrieval model").click();
  if (process.env.FIQA_CAPTURE === "1")
    await page.screenshot({
      animations: "disabled",
      path: resolve(shots, "selector-modelos.png"),
      fullPage: true,
    });
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "APR vs. APY", exact: true }).click();
  const responsePromise = page.waitForResponse(
    (r) => r.url().endsWith("/search") && r.request().method() === "POST",
  );
  await page.getByLabel("Query", { exact: true }).press("Enter");
  const response = await responsePromise;
  expect(response.ok()).toBe(true);
  const body = await response.json();
  expect(body.model).toBe("hybrid");
  expect(body.count).toBe(5);
  await expect(
    page.getByText("Automatic selected Hybrid BM25 + BGE", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".result")).toHaveCount(5);
  await expect(page.locator(".document-preview").first()).toHaveText(
    body.results[0].preview,
  );
  if (process.env.FIQA_CAPTURE === "1")
    await page.screenshot({
      animations: "disabled",
      path: resolve(shots, "results.png"),
      fullPage: true,
    });
  for (const model of ["jaccard", "tfidf", "bm25", "bge", "hybrid"] as const) {
    await chooseModel(page, model);
    const done = page.waitForResponse(
      (r) => r.url().endsWith("/search") && r.request().method() === "POST",
    );
    await page
      .getByRole("button", { name: "Search", exact: true })
      .last()
      .click();
    const data = await (await done).json();
    expect(data.model).toBe(model);
    await expect(page.locator(".document-preview").first()).toHaveText(
      data.results[0].preview,
    );
    if (model === "bge") expect(data.results[0].doc_id).toBe("263225");
  }
  await page.getByLabel("Compare models", { exact: true }).check();
  // Comparación real con los cinco modelos del motor.
  await page.getByLabel("Jaccard", { exact: true }).check();
  await page.getByLabel("TF-IDF", { exact: true }).check();
  const comparison = page.waitForResponse((r) =>
    r.url().endsWith("/search/compare"),
  );
  await page
    .getByRole("button", { name: "Search", exact: true })
    .last()
    .click();
  const compared = await (await comparison).json();
  expect(compared.rankings).toHaveLength(5);
  await expect(
    page.getByRole("heading", { name: "Ranking comparison" }),
  ).toBeVisible();
  await expect(page.locator(".ranking")).toHaveCount(5);
  if (process.env.FIQA_CAPTURE === "1")
    await page.screenshot({
      animations: "disabled",
      path: resolve(shots, "comparacion.png"),
      fullPage: true,
    });
  await page.getByRole("link", { name: "Evaluation", exact: true }).click();
  if (process.env.FIQA_CAPTURE === "1")
    await page.screenshot({
      animations: "disabled",
      path: resolve(shots, "evaluacion.png"),
      fullPage: true,
    });
  await page
    .getByRole("link", { name: "About the system", exact: true })
    .click();
  if (process.env.FIQA_CAPTURE === "1")
    await page.screenshot({
      animations: "disabled",
      path: resolve(shots, "acerca.png"),
      fullPage: true,
    });
  await page.getByRole("link", { name: "Search", exact: true }).first().click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(
    page.getByText("Search engine connected", { exact: true }),
  ).toBeVisible();
  if (process.env.FIQA_CAPTURE === "1")
    await page.screenshot({
      animations: "disabled",
      path: resolve(shots, "movil.png"),
      fullPage: true,
    });
  await chooseModel(page, "bm25");
  await page.getByLabel("Results", { exact: true }).selectOption("3");
  await page.getByRole("button", { name: "Index funds", exact: true }).click();
  await page.getByLabel("Query", { exact: true }).press("Enter");
  await expect(page.locator(".result")).toHaveCount(3);
  if (process.env.FIQA_CAPTURE === "1")
    await page.screenshot({
      animations: "disabled",
      path: resolve(shots, "movil-results.png"),
      fullPage: true,
    });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.route("**/health", (route) => route.abort("failed"));
  await page.reload();
  await expect(
    page.getByText("Server disconnected", { exact: true }),
  ).toBeVisible();
  if (process.env.FIQA_CAPTURE === "1")
    await page.screenshot({
      animations: "disabled",
      path: resolve(shots, "desconectado.png"),
      fullPage: true,
    });
  expect(errors).toEqual([]);
  // El único fallo de red esperado es el inyectado al comprobar la desconexión.
  expect(
    consoleErrors.filter(
      (error) =>
        !error.includes("net::ERR_FAILED") &&
        !error.includes("Failed to fetch"),
    ),
  ).toEqual([]);
});
