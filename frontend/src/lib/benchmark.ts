import data from "../data/benchmark.json";
import type { ModelId } from "./types";
export type Series = "historical" | "current";
export const METRICS = ["MAP@1000", "P@10", "Recall@100", "NDCG@10"] as const;
export type Metric = (typeof METRICS)[number];
export const metricLabel = (metric: Metric) =>
  metric === "P@10" ? "Precision@10" : metric;
export function benchmark(series: Series, model: ModelId) {
  return data[series].find((row) => row.model === model)!;
}
export { data as benchmarkData };
