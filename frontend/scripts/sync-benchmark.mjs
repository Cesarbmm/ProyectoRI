// Genera solo métricas de benchmark. Nunca contiene respuestas de búsqueda.
import { readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
const root = fileURLToPath(new URL("../../", import.meta.url));
const models = ["jaccard", "tfidf", "bm25", "bge", "hybrid"];
const sources = [];
async function read(path) {
  const bytes = await readFile(resolve(root, path));
  // Canonicalizar saltos de línea para conservar la procedencia en Windows/Linux.
  const text = bytes.toString("utf8").replace(/\r\n/g, "\n");
  sources.push({
    path,
    sha256: createHash("sha256").update(text).digest("hex"),
  });
  return JSON.parse(text);
}
async function row(path, model) {
  const report = await read(path);
  if (report.split !== "test" || report.queries_evaluated !== 648)
    throw new Error(`Benchmark incompatible: ${path}`);
  const metrics = Object.fromEntries(
    ["MAP@1000", "P@10", "Recall@100", "NDCG@10"].map((key) => {
      const value = report.aggregate[key];
      if (typeof value !== "number" || value < 0 || value > 1)
        throw new Error(`Métrica inválida: ${path}/${key}`);
      return [key, value];
    }),
  );
  return { model, metrics, source: path };
}
const historical = await Promise.all(
  models.map((m) => row(`results/service_${m}_test_metrics.json`, m)),
);
const current = await Promise.all(
  models.map((m) =>
    row(
      m === "bge"
        ? "results/service_bge_test_metrics.json"
        : `results/preprocessing_v1/final_test/stemming_${m}_test.json`,
      m,
    ),
  ),
);
const frozen = await read("results/preprocessing_v1/selection_frozen.json");
if (
  frozen.winner !== "stemming" ||
  frozen.bm25.k1 !== 0.8 ||
  frozen.bm25.b !== 0.75
)
  throw new Error("La selección congelada cambió. Revisar la integración.");
const audit = await read("results/auditoria_fiqa.json");
if (audit.corpus.total !== 57638 || audit.corpus.textos_vacios !== 38)
  throw new Error("La auditoría del corpus cambió.");
const data = {
  dataset: "BeIR/fiqa",
  split: "test",
  queries: 648,
  corpus: {
    documents: audit.corpus.total,
    vectors: audit.corpus.total - audit.corpus.textos_vacios,
    empty: audit.corpus.textos_vacios,
    evidence:
      "Verificados con datasets.load_from_disk(data/raw/corpus), semantic_bge/metadata.json y FAISS ntotal; ver docs/FRONTEND.md.",
  },
  configuration: {
    morphology: frozen.winner,
    bm25_k1: frozen.bm25.k1,
    bm25_b: frozen.bm25.b,
  },
  historical,
  current,
  sources: sources.sort((a, b) => a.path.localeCompare(b.path)),
};
const destination = resolve(root, "frontend/src/data/benchmark.json");
const output = JSON.stringify(data, null, 2) + "\n";
if (process.argv.includes("--check")) {
  const existing = (await readFile(destination, "utf8")).replace(/\r\n/g, "\n");
  if (existing !== output)
    throw new Error(
      "Benchmark desactualizado: ejecutar npm run benchmark:sync",
    );
  console.log("Benchmark coincide con los resultados reales del repositorio.");
} else {
  await writeFile(destination, output);
  console.log(destination);
}
