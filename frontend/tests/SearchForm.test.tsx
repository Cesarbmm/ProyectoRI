import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SearchForm } from "../src/components/SearchForm";
import { Ranking } from "../src/components/Results";
import type { ModelsInfo } from "../src/lib/types";
const models: ModelsInfo = {
  default_model: "bge",
  models: [
    { id: "hybrid", label: "Hybrid", score_type: "rrf" },
    { id: "bm25", label: "BM25", score_type: "bm25" },
    { id: "bge", label: "BGE", score_type: "cosine_embedding" },
    { id: "jaccard", label: "Jaccard", score_type: "jaccard" },
    { id: "tfidf", label: "TF-IDF", score_type: "cosine_tfidf" },
  ],
  lexical_configuration: { morphology: "stemming", bm25_k1: 0.8, bm25_b: 0.75 },
};
function form(connected = true) {
  const submit = vi.fn();
  const onChoice = vi.fn();
  render(
    <SearchForm
      choice="bge"
      onChoice={onChoice}
      connected={connected}
      busy={false}
      models={models}
      onSearch={submit}
    />,
  );
  return { submit, onChoice };
}
describe("Formulario accesible", () => {
  it("defaults to BGE and searches with Enter", async () => {
    const { submit } = form();
    const user = userEvent.setup();
    expect(screen.getByLabelText("Retrieval model")).toHaveTextContent(
      "Default (BGE + FAISS)",
    );
    await user.type(screen.getByLabelText("Query"), "retirement{Enter}");
    expect(submit).toHaveBeenCalledWith("retirement", "bge", 5, null);
  });
  it("offers exactly four models and excludes the historical hybrid from comparison", async () => {
    form();
    const user = userEvent.setup();
    await user.click(screen.getByLabelText("Retrieval model"));
    expect(
      within(screen.getByRole("listbox")).getAllByRole("option"),
    ).toHaveLength(4);
    expect(
      screen.queryByRole("option", { name: /hybrid|automatic/i }),
    ).not.toBeInTheDocument();
    await user.keyboard("{Escape}");
    await user.click(screen.getByLabelText("Compare models"));
    expect(screen.getAllByRole("checkbox")).toHaveLength(5);
    expect(
      screen.queryByRole("checkbox", { name: /hybrid/i }),
    ).not.toBeInTheDocument();
  });
  it("rechaza espacios vacíos y conserva el foco", async () => {
    const { submit } = form();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Query"), "   {Enter}");
    expect(screen.getByRole("alert")).toHaveTextContent("Enter a query");
    expect(submit).not.toHaveBeenCalled();
  });
  it("las sugerencias rellenan el campo sin inventar búsquedas", async () => {
    const { submit } = form();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "APR vs. APY" }));
    expect(screen.getByLabelText("Query")).toHaveValue(
      "What is the difference between APR and APY?",
    );
    expect(screen.getByLabelText("Query")).toHaveFocus();
    expect(submit).not.toHaveBeenCalled();
  });
  it("permite Top-K 3, 5, 10 y 20 y notifica el cambio de modelo", async () => {
    const { submit, onChoice } = form();
    const user = userEvent.setup();
    const topK = screen.getByLabelText("Results");
    expect(
      Array.from(topK.querySelectorAll("option")).map((o) => o.value),
    ).toEqual(["3", "5", "10", "20"]);
    await user.selectOptions(topK, "20");
    await user.click(screen.getByLabelText("Retrieval model"));
    await user.click(screen.getByRole("option", { name: "BM25" }));
    expect(onChoice).toHaveBeenCalledWith("bm25");
    await user.type(screen.getByLabelText("Query"), "banks{Enter}");
    expect(submit.mock.calls[0][2]).toBe(20);
  });
  it("deshabilita la búsqueda si el motor está desconectado", () => {
    const { submit } = form(false);
    expect(screen.getByRole("button", { name: "Search" })).toBeDisabled();
    expect(submit).not.toHaveBeenCalled();
  });
  it("exige dos modelos para comparar", async () => {
    const { submit } = form();
    const user = userEvent.setup();
    await user.click(screen.getByLabelText("Compare models"));
    await user.click(screen.getByLabelText("BM25", { exact: true }));
    await user.type(screen.getByLabelText("Query"), "banks{Enter}");
    expect(screen.getByRole("alert")).toHaveTextContent("Select at least two");
    expect(submit).not.toHaveBeenCalled();
  });
  it("presenta el contenido recibido como texto seguro y expandible", async () => {
    render(
      <Ranking
        ranking={{
          query: "bank",
          model: "bm25",
          count: 1,
          elapsed_ms: 7,
          results: [
            {
              rank: 1,
              doc_id: "42",
              score: 2.5,
              preview: "<script>alert(1)</script>",
              text: "Full corpus document",
            },
          ],
        }}
      />,
    );
    expect(screen.getByText("<script>alert(1)</script>")).toBeVisible();
    await userEvent.click(screen.getByText("Read full document"));
    expect(screen.getByText("Full corpus document")).toBeVisible();
  });
});
