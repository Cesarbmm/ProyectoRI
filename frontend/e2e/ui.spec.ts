import { chooseModel, waitForMotion } from "./helpers";
import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
test.setTimeout(40_000);

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByText("Search engine connected", { exact: true }),
  ).toBeVisible();
});

test("pantalla inicial, navegación, benchmark y accesibilidad", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await expect(page).toHaveTitle("FiQA — Financial search");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator(".orbit")).toHaveCSS("border-radius", "50%");
  expect(
    await page
      .locator(".orbit")
      .evaluate((el) => getComputedStyle(el, "::after").animationName),
  ).toBe("orbit-travel");
  await expect(
    page.getByRole("heading", { name: "FiQA, back to home", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Retrieval model")).toHaveText(
    "Default (BGE + FAISS)",
  );
  await expect(page.locator(".brand-caption")).toHaveText("Financial Search");
  const logo = (await page.locator(".brand-home").boundingBox())!;
  const caption = (await page.locator(".brand-caption").boundingBox())!;
  expect(caption.x + caption.width).toBeLessThanOrEqual(
    logo.x + logo.width + 1,
  );
  expect(caption.y).toBeGreaterThan(logo.y + logo.height * 0.6);
  await expect(page.locator(".benchmark-panel, .site-header")).toHaveCount(0);
  await expect(page.getByText("Suggestions", { exact: true })).toBeVisible();
  await expect(page.getByText("0.350006", { exact: true })).toHaveCount(0);
  await page.getByLabel("Retrieval model").click();
  await expect(page.getByRole("listbox").getByRole("option")).toHaveCount(4);
  await expect(
    page.getByRole("option", { name: /hybrid|automatic/i }),
  ).toHaveCount(0);
  await page.keyboard.press("Escape");
  await page.getByRole("link", { name: "Evaluation", exact: true }).click();
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.locator(".provenance")).toHaveCount(0);
  await expect(
    page.getByRole("cell", { name: "0.349604", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/baseline/i)).toHaveCount(0);
  await page.getByLabel("Compare by").selectOption("Recall@100");
  await expect(
    page.getByRole("img", { name: /Chart of Recall/ }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "About the system", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "About the system" }),
  ).toBeVisible();
  await expect(
    page.getByRole("definition").filter({ hasText: "57,600" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Search", exact: true }).first().click();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await waitForMotion(page);
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  expect(errors).toEqual([]);
});

test("consulta real mediante Enter, Top-K, modelo y expansión", async ({
  page,
}) => {
  await chooseModel(page, "bm25");
  await page.getByLabel("Results", { exact: true }).selectOption("3");
  await page
    .getByLabel("Query", { exact: true })
    .fill("What is the difference between APR and APY?");
  const request = page.waitForRequest(
    (r) => r.url().endsWith("/search") && r.method() === "POST",
  );
  await page.getByLabel("Query", { exact: true }).press("Enter");
  expect((await request).postDataJSON()).toEqual({
    query: "What is the difference between APR and APY?",
    model: "bm25",
    top_k: 3,
  });
  await expect(page.locator(".result")).toHaveCount(3);
  const firstResult = page.locator(".result").first();
  await expect(firstResult.locator(".score-label")).toContainText(
    "Lexical score:",
  );
  const info = firstResult.getByRole("button", {
    name: "Explain lexical score",
  });
  await info.click();
  await expect(firstResult.locator(".score-explanation")).toBeVisible();
  await expect(info).toHaveAttribute("aria-expanded", "true");
  await expect(firstResult.locator(".technical-score code")).not.toBeVisible();
  await firstResult.getByText("Technical score", { exact: true }).click();
  await expect(firstResult.locator(".technical-score code")).toBeVisible();
  await page.getByText("Read full document", { exact: true }).first().click();
  await expect(page.locator(".document-full").first()).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await waitForMotion(page);
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze())
      .violations,
  ).toEqual([]);
});

test("error HTTP real de la capa de transporte, sin éxito falso", async ({
  page,
}) => {
  // Inyección de fallo solo en pruebas; no se fabrica ningún ranking.
  await page.route("**/search", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: '{"detail":"unavailable"}',
    }),
  );
  await page.getByRole("button", { name: "Index funds", exact: true }).click();
  await page
    .getByRole("button", { name: "Search", exact: true })
    .last()
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "The search engine is not ready",
  );
  await expect(page.locator(".result")).toHaveCount(0);
  await expect(page.getByText("Default model:", { exact: false })).toHaveCount(
    0,
  );
});

test("desconexión, reconexión y búsqueda vacía real", async ({ page }) => {
  await page.route("**/health", (route) => route.abort("failed"));
  await page.reload();
  await expect(
    page.getByText("Server disconnected", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Search", exact: true }).last(),
  ).toBeDisabled();
  await page.unroute("**/health");
  await page.getByRole("button", { name: "Reconnect" }).click();
  await expect(
    page.getByText("Search engine connected", { exact: true }),
  ).toBeVisible();
  await chooseModel(page, "bm25");
  await page
    .getByLabel("Query", { exact: true })
    .fill("zzzxqv987654321unmatched");
  await page
    .getByRole("button", { name: "Search", exact: true })
    .last()
    .click();
  await expect(page.getByText(/No documents found/)).toBeVisible();
});

test("teclado, carga y cancelación conservan estados coherentes", async ({
  page,
}) => {
  await page.keyboard.press("Tab"); // El enlace para saltar al contenido es alcanzable.
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  await page.route("**/search", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1500));
    await route.continue().catch(() => {});
  });
  await chooseModel(page, "bm25");
  await page.getByLabel("Query", { exact: true }).fill("bank");
  await page.getByLabel("Query", { exact: true }).press("Enter");
  await expect(
    page.getByRole("heading", { name: "Searching FiQA…" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Searching FiQA…" }),
  ).toHaveCount(0);
  await expect(page.locator(".result")).toHaveCount(0);
});

test("menú oscuro legible, selección por teclado y cierre sin cambiar el modelo", async ({
  page,
}) => {
  if (page.viewportSize()!.width === 390)
    await page.setViewportSize({ width: 320, height: 844 });
  const trigger = page.getByLabel("Retrieval model");
  await trigger.click();
  const menu = page.getByRole("listbox");
  await expect(menu).toHaveCSS("background-color", "rgb(32, 34, 40)");
  const selectedOption = page.getByRole("option", {
    name: "Default (BGE + FAISS)",
    exact: true,
  });
  expect(
    await selectedOption.evaluate((el) => {
      const rect = el.getBoundingClientRect();
      return [0.15, 0.25, 0.5, 0.75, 0.9].every((fraction) =>
        el.contains(
          document.elementFromPoint(
            rect.left + rect.width * fraction,
            rect.top + rect.height / 2,
          ),
        ),
      );
    }),
  ).toBe(true);
  await expect(
    page.getByRole("option", { name: "Default (BGE + FAISS)", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("End");
  await page.keyboard.press("Enter");
  await expect(trigger).toHaveText("BM25");
  await trigger.click();
  await page.keyboard.press("Escape");
  await expect(menu).toHaveCount(0);
  await expect(trigger).toHaveText("BM25");
  await chooseModel(page, "bge");
  expect(await trigger.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(
    true,
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze())
      .violations,
  ).toEqual([]);
});

test("transición, barra fija, búsquedas sucesivas y retorno suave al inicio", async ({
  page,
}) => {
  await chooseModel(page, "bm25");
  await page.getByLabel("Results", { exact: true }).selectOption("3");
  const logo = page.getByRole("button", {
    name: "FiQA, back to home",
    exact: true,
  });
  const before = (await logo.boundingBox())!;
  await page.evaluate(() => {
    (window as unknown as { originalQuery: Element | null }).originalQuery =
      document.getElementById("query");
  });
  await page.getByLabel("Query", { exact: true }).fill("bank interest");
  await page.getByLabel("Query", { exact: true }).press("Enter");
  await expect(page.locator(".result")).toHaveCount(3);
  await waitForMotion(page);
  const after = (await logo.boundingBox())!;
  expect(after.width).toBeLessThan(before.width * 0.55);
  expect(after.y).toBeLessThan(before.y);
  await expect(page.locator(".search-stage")).toHaveCSS("position", "sticky");
  await page.evaluate(() => window.scrollTo(0, 300));
  expect(
    (await page.locator(".search-bar").boundingBox())!.y,
  ).toBeGreaterThanOrEqual(0);
  const response = page.waitForResponse((r) => r.url().endsWith("/search"));
  await page.getByLabel("Query", { exact: true }).fill("index funds");
  await page.getByLabel("Query", { exact: true }).press("Enter");
  expect((await (await response).json()).model).toBe("bm25");
  await expect(page.getByText("index funds", { exact: true })).toBeVisible();
  await expect(page.locator(".app-shell")).toHaveClass(/is-compact/);
  expect(
    await page.evaluate(
      () =>
        (window as unknown as { originalQuery: Element | null })
          .originalQuery === document.getElementById("query"),
    ),
  ).toBe(true);
  await logo.click();
  await expect(page.locator(".app-shell")).toHaveClass(/is-home/);
  await waitForMotion(page);
  await expect(page.locator(".result")).toHaveCount(0);
  await expect(page.getByLabel("Query", { exact: true })).toHaveValue("");
  expect(await page.evaluate(() => window.scrollY)).toBeLessThan(2);
});

test("prefers-reduced-motion omite desplazamientos animados", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  expect(
    await page
      .locator(".orbit")
      .evaluate((el) => getComputedStyle(el, "::after").animationName),
  ).toBe("none");
  await chooseModel(page, "bm25");
  await page.getByLabel("Query", { exact: true }).fill("bank");
  await page.getByLabel("Query", { exact: true }).press("Enter");
  await expect(page.locator(".result").first()).toBeVisible();
  expect(
    await page
      .locator(".brand-home")
      .evaluate((el) => el.getAnimations().length),
  ).toBe(0);
  expect(
    await page
      .locator(".ambient span")
      .first()
      .evaluate((el) => el.getAnimations().length),
  ).toBe(0);
  await page
    .getByRole("button", { name: "FiQA, back to home", exact: true })
    .click();
  await expect(page.locator(".app-shell")).toHaveClass(/is-home/);
});
