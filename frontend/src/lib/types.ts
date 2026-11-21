import { z } from "zod";
export const modelId = z.enum(["jaccard", "tfidf", "bm25", "bge", "hybrid"]);
export type ModelId = z.infer<typeof modelId>;
export const ACTIVE_MODEL_IDS = ["jaccard", "tfidf", "bm25", "bge"] as const;
export type ModelChoice = (typeof ACTIVE_MODEL_IDS)[number];
export const DEFAULT_MODEL: ModelChoice = "bge";
export const DEFAULT_MODEL_LABEL = "Default (BGE + FAISS)";
export const isActiveModel = (model: ModelId): model is ModelChoice =>
  ACTIVE_MODEL_IDS.some((active) => active === model);
export const modelsSchema = z.object({
  default_model: modelId,
  models: z
    .array(z.object({ id: modelId, label: z.string(), score_type: z.string() }))
    .min(1),
  lexical_configuration: z.object({
    morphology: z.string(),
    bm25_k1: z.number(),
    bm25_b: z.number(),
  }),
});
export type ModelsInfo = z.infer<typeof modelsSchema>;
export const healthSchema = z.object({
  status: z.literal("ok"),
  service: z.string(),
});
export const readySchema = z.object({
  status: z.literal("ready"),
  components: z.record(z.string(), z.boolean()),
});
const hitSchema = z.object({
  rank: z.number().int().positive(),
  doc_id: z.string(),
  score: z.number().finite(),
  text: z.string(),
  preview: z.string(),
});
export const searchSchema = z
  .object({
    query: z.string(),
    model: modelId,
    count: z.number().int().nonnegative(),
    elapsed_ms: z.number().nonnegative(),
    results: z.array(hitSchema),
  })
  .refine(
    (data) => data.count === data.results.length,
    "Inconsistent result count",
  );
export const compareSchema = z.object({
  query: z.string(),
  elapsed_ms: z.number().nonnegative(),
  rankings: z.array(searchSchema),
});
export type SearchResponse = z.infer<typeof searchSchema>;
export type SearchHit = z.infer<typeof hitSchema>;
export const LABELS: Record<ModelId, string> = {
  jaccard: "Jaccard",
  tfidf: "TF-IDF",
  bm25: "BM25",
  bge: "BGE + FAISS",
  hybrid: "Hybrid BM25 + BGE",
};
export function resolveModel(choice: ModelChoice): ModelId {
  if (!isActiveModel(choice))
    throw new Error("This model is not available for web searches.");
  return choice;
}
export const number = (value: number, digits = 6) =>
  value.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
