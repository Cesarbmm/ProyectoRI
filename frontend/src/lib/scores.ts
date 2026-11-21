import type { ModelId } from "./types";

export const SCORE_INFO: Record<
  ModelId,
  { label: string; explanation: string }
> = {
  jaccard: {
    label: "Term overlap",
    explanation:
      "How much the unique words in the query and document overlap. 100% means the same set of words; it is not a probability of relevance.",
  },
  tfidf: {
    label: "Text similarity",
    explanation:
      "Similarity based on shared words, with more distinctive words carrying more weight. Higher values indicate a stronger textual match.",
  },
  bm25: {
    label: "Lexical score",
    explanation:
      "Measures word matches using their frequency, rarity and the document's length. Higher values indicate a stronger match; there is no fixed maximum.",
  },
  bge: {
    label: "Semantic affinity",
    explanation:
      "Similarity between the meanings represented by BGE. It can match related ideas even when the words differ. It is not a probability.",
  },
  hybrid: {
    label: "Fusion score",
    explanation:
      "Combines the document's positions in the BM25 and BGE rankings. Higher values indicate stronger combined rankings, not a probability of relevance.",
  },
};

// Presentation only: never normalise, reorder or change the API's score.
export function displayScore(model: ModelId, score: number) {
  if (model === "jaccard")
    return `${(score * 100).toLocaleString("en-US", { maximumFractionDigits: 2 })}%`;
  return score.toLocaleString("en-US", { maximumSignificantDigits: 4 });
}
