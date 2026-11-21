import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { ResultScore } from "../src/components/ResultScore";
import { Ranking } from "../src/components/Results";
import { Evaluation } from "../src/components/Benchmark";
import type { ModelId, SearchResponse } from "../src/lib/types";

it.each<[ModelId, number, string]>([
  ["jaccard", 0.37678, "Term overlap: 37.68%"],
  ["tfidf", 0.876543, "Text similarity: 0.8765"],
  ["bm25", 12.34567, "Lexical score: 12.35"],
  ["bge", -0.123456, "Semantic affinity: -0.1235"],
  ["hybrid", 0.009876543, "Fusion score: 0.009877"],
])(
  "presents %s in its original scale and keeps the exact score in secondary details",
  async (model, score, label) => {
    const { container } = render(<ResultScore model={model} score={score} />);
    expect(container.querySelector(".score-label")).toHaveTextContent(label);
    expect(
      screen.getByText(String(score), { selector: "code" }),
    ).not.toBeVisible();
    await userEvent.click(screen.getByText("Technical score", { exact: true }));
    expect(screen.getByText(String(score), { selector: "code" })).toBeVisible();
  },
);

it("explains the score through a keyboard-accessible information control", async () => {
  const user = userEvent.setup();
  render(<ResultScore model="bge" score={0.72} />);
  const button = screen.getByRole("button", {
    name: "Explain semantic affinity",
  });
  await user.tab();
  expect(button).toHaveFocus();
  await user.keyboard("{Enter}");
  expect(button).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByText(/It is not a probability/)).toBeVisible();
  await user.keyboard("{Escape}");
  expect(button).toHaveAttribute("aria-expanded", "false");
});

it("preserves API order, positions, content and raw scores", () => {
  const ranking: SearchResponse = {
    query: "bank",
    model: "bm25",
    count: 2,
    elapsed_ms: 2,
    results: [
      {
        rank: 1,
        doc_id: "z",
        score: 1.23456789,
        preview: "First API document",
        text: "Complete first document",
      },
      {
        rank: 2,
        doc_id: "a",
        score: 40.123456789,
        preview: "Second API document",
        text: "Complete second document",
      },
    ],
  };
  const original = JSON.stringify(ranking);
  render(<Ranking ranking={ranking} />);
  const rows = screen.getAllByRole("listitem");
  expect(within(rows[0]).getByText("Document z")).toBeVisible();
  expect(within(rows[1]).getByText("Document a")).toBeVisible();
  expect(within(rows[0]).getByLabelText("Position 1")).toBeVisible();
  expect(JSON.stringify(ranking)).toBe(original);
});

it("keeps final evaluation metrics while removing their provenance disclosure", () => {
  render(<Evaluation />);
  expect(screen.getByRole("heading", { name: "Evaluation" })).toBeVisible();
  expect(screen.getByRole("cell", { name: "0.349604" })).toBeVisible();
  expect(document.querySelector(".provenance")).toBeNull();
});
