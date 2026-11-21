import { type Page } from "@playwright/test";
import { LABELS, type ModelChoice } from "../src/lib/types";
export async function waitForMotion(page: Page) {
  await page.evaluate(async () => {
    await Promise.allSettled(
      document
        .getAnimations()
        .filter(
          (animation) =>
            animation.effect?.getComputedTiming().iterations !== Infinity,
        )
        .map((animation) => animation.finished),
    );
  });
}
export async function chooseModel(page: Page, model: ModelChoice) {
  await page.getByRole("combobox", { name: "Retrieval model" }).click();
  await page
    .getByRole("option", {
      name: model === "bge" ? "Default (BGE + FAISS)" : LABELS[model],
      exact: true,
    })
    .click();
}
