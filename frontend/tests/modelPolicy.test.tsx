import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../src/lib/api";
import {
  ACTIVE_MODEL_IDS,
  DEFAULT_MODEL,
  resolveModel,
  type ModelChoice,
} from "../src/lib/types";
import { useSearch } from "../src/lib/useSearch";

afterEach(() => vi.restoreAllMocks());

it("keeps the four original active models and BGE as the default", () => {
  expect(ACTIVE_MODEL_IDS).toEqual(["jaccard", "tfidf", "bm25", "bge"]);
  expect(DEFAULT_MODEL).toBe("bge");
  expect(ACTIVE_MODEL_IDS.map(resolveModel)).toEqual(ACTIVE_MODEL_IDS);
  expect(() => resolveModel("hybrid" as ModelChoice)).toThrow("not available");
});

it("rejects a stale hybrid comparison before contacting the API", async () => {
  const compare = vi
    .spyOn(api, "compare")
    .mockRejectedValue(new Error("Unexpected API call"));
  const { result } = renderHook(useSearch);
  await act(async () =>
    result.current.run("bank", "bge", 3, ["bge", "hybrid"]),
  );
  expect(compare).not.toHaveBeenCalled();
  expect(result.current.state.status).toBe("error");
  expect(result.current.state.error).toContain("Historical models");
});
