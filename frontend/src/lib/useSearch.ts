import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import {
  resolveModel,
  DEFAULT_MODEL,
  isActiveModel,
  type ModelChoice,
  type ModelId,
  type SearchResponse,
} from "./types";

export type SearchState = {
  status: "idle" | "loading" | "success" | "error";
  error?: string;
  query?: string;
  isDefault?: boolean;
  rankings?: SearchResponse[];
  elapsed?: number;
};
export function useSearch() {
  const [state, setState] = useState<SearchState>({ status: "idle" });
  const active = useRef<AbortController | null>(null);
  useEffect(() => () => active.current?.abort(), []);
  async function run(
    query: string,
    choice: ModelChoice,
    topK: number,
    comparison: ModelId[] | null,
  ) {
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    const context = {
      query: query.trim(),
      isDefault: !comparison && choice === DEFAULT_MODEL,
    };
    setState({ status: "loading", ...context });
    try {
      const selected = resolveModel(choice);
      let rankings: SearchResponse[], elapsed: number;
      if (comparison) {
        if (comparison.some((model) => !isActiveModel(model)))
          throw new Error(
            "Historical models are not available for web comparison.",
          );
        const result = await api.compare(
          context.query,
          comparison,
          topK,
          controller.signal,
        );
        if (
          result.query !== context.query ||
          result.rankings.length !== comparison.length ||
          new Set(result.rankings.map((r) => r.model)).size !==
            comparison.length ||
          result.rankings.some(
            (r) => !comparison.includes(r.model) || r.query !== context.query,
          )
        )
          throw new Error(
            "The returned comparison does not match the request.",
          );
        rankings = result.rankings;
        elapsed = result.elapsed_ms;
      } else {
        const result = await api.search(
          context.query,
          selected,
          topK,
          controller.signal,
        );
        if (result.model !== selected || result.query !== context.query)
          throw new Error("The response does not match the requested model.");
        rankings = [result];
        elapsed = result.elapsed_ms;
      }
      if (!controller.signal.aborted)
        setState({ status: "success", rankings, elapsed, ...context });
    } catch (error) {
      if (!controller.signal.aborted)
        setState({
          status: "error",
          error: (error as Error).message,
          ...context,
        });
    }
  }
  return {
    state,
    run,
    cancel: () => {
      active.current?.abort();
      setState({ status: "idle" });
    },
  };
}
