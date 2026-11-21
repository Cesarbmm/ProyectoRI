import { z } from "zod";
import {
  compareSchema,
  healthSchema,
  modelsSchema,
  readySchema,
  searchSchema,
  type ModelId,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
export const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000")
  .trim()
  .replace(/\/+$/, "");

export function createApi(base = API_URL) {
  async function request<T>(
    path: string,
    schema: z.ZodType<T>,
    init: RequestInit = {},
    timeout = 130_000,
  ): Promise<T> {
    const controller = new AbortController();
    const cancel = () => controller.abort();
    if (init.signal?.aborted) controller.abort();
    init.signal?.addEventListener("abort", cancel, { once: true });
    const timer = setTimeout(cancel, timeout);
    try {
      const response = await fetch(`${base}${path}`, {
        ...init,
        signal: controller.signal,
      });
      if (!response.ok) {
        const messages: Record<number, string> = {
          422: "The API rejected the query. Check the text, models and number of results.",
          503: "The search engine is not ready. Check the indexes and reconnect.",
        };
        throw new ApiError(
          messages[response.status] ||
            `The request could not be completed (HTTP ${response.status}).`,
          response.status,
        );
      }
      let payload: unknown;
      try {
        payload = await response.json();
      } catch {
        throw new ApiError(
          "The API returned invalid JSON. No results are displayed.",
        );
      }
      const data = schema.safeParse(payload);
      if (!data.success)
        throw new ApiError(
          "The API returned an incompatible response. No results are displayed.",
        );
      return data.data;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (init.signal?.aborted)
        throw new DOMException("Request cancelled", "AbortError");
      if (controller.signal.aborted)
        throw new ApiError(
          "The API took too long to respond. Please try again.",
        );
      throw new ApiError(
        "Could not connect to the server. Check your API connection.",
      );
    } finally {
      clearTimeout(timer);
      init.signal?.removeEventListener("abort", cancel);
    }
  }
  return {
    health: (signal?: AbortSignal) =>
      request("/health", healthSchema, { signal }, 10_000),
    ready: (signal?: AbortSignal) =>
      request("/ready", readySchema, { signal }, 10_000),
    models: (signal?: AbortSignal) =>
      request("/models", modelsSchema, { signal }, 10_000),
    search: (
      query: string,
      model: ModelId,
      top_k: number,
      signal?: AbortSignal,
    ) =>
      request("/search", searchSchema, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, model, top_k }),
        signal,
      }),
    compare: (
      query: string,
      models: ModelId[],
      top_k: number,
      signal?: AbortSignal,
    ) =>
      request("/search/compare", compareSchema, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, models, top_k }),
        signal,
      }),
  };
}
export const api = createApi();
