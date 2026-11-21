import { afterEach, describe, expect, it, vi } from "vitest";
import { createApi } from "../src/lib/api";
import { resolveModel } from "../src/lib/types";
import { benchmark, benchmarkData } from "../src/lib/benchmark";
afterEach(() => vi.unstubAllGlobals());
describe("Contrato API y benchmark", () => {
  it("Automatic resuelve exclusivamente a hybrid", () => {
    expect(resolveModel("automatic")).toBe("hybrid");
    expect(resolveModel("bge")).toBe("bge");
  });
  it("envía modelo, consulta y Top-K a la API real configurada", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          query: "banks",
          model: "hybrid",
          count: 0,
          results: [],
          elapsed_ms: 21,
        }),
      ),
    );
    vi.stubGlobal("fetch", fetcher);
    const response = await createApi("http://localhost:8123").search(
      "banks",
      resolveModel("automatic"),
      20,
    );
    expect(response.count).toBe(0);
    expect(fetcher.mock.calls[0][0]).toBe("http://localhost:8123/search");
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({
      query: "banks",
      model: "hybrid",
      top_k: 20,
    });
  });
  it("envía la selección múltiple al endpoint de comparación", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ query: "banks", elapsed_ms: 10, rankings: [] }),
        ),
      );
    vi.stubGlobal("fetch", fetcher);
    await createApi("http://localhost:8123").compare(
      "banks",
      ["tfidf", "bm25"],
      3,
    );
    expect(fetcher.mock.calls[0][0]).toBe(
      "http://localhost:8123/search/compare",
    );
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({
      query: "banks",
      models: ["tfidf", "bm25"],
      top_k: 3,
    });
  });
  it.each([422, 500, 503])(
    "rechaza HTTP %s sin results de respaldo",
    async (status) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(new Response("{}", { status })),
      );
      await expect(
        createApi().search("banks", "bm25", 5),
      ).rejects.toMatchObject({ status });
    },
  );
  it("rechaza una respuesta incompleta o inconsistente", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            query: "banks",
            model: "bm25",
            results: [],
            count: 8,
            elapsed_ms: 1,
          }),
        ),
      ),
    );
    await expect(createApi().search("banks", "bm25", 5)).rejects.toThrow(
      "incompatible response",
    );
  });
  it("informa una desconexión y no fabrica un ranking", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );
    await expect(createApi().search("banks", "bm25", 5)).rejects.toThrow(
      "Could not connect",
    );
  });
  it("rechaza invalid JSON sin confundirlo con results vacíos", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("invalid-json")),
    );
    await expect(createApi().search("banks", "bm25", 5)).rejects.toThrow(
      "invalid JSON",
    );
  });
  it("diferencia cancelación voluntaria de fallo de conexión", async () => {
    const controller = new AbortController();
    controller.abort();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new DOMException("aborted", "AbortError")),
    );
    await expect(
      createApi().search("banks", "bm25", 5, controller.signal),
    ).rejects.toMatchObject({ name: "AbortError" });
  });
  it("cierra una comprobación de salud que excede el timeout", async () => {
    vi.useFakeTimers();
    try {
      vi.stubGlobal(
        "fetch",
        vi.fn(
          (_url, init) =>
            new Promise((_resolve, reject) => {
              init.signal.addEventListener("abort", () =>
                reject(new DOMException("aborted", "AbortError")),
              );
            }),
        ),
      );
      const expectation = expect(createApi().health()).rejects.toThrow(
        "took too long",
      );
      await vi.advanceTimersByTimeAsync(10_000);
      await expectation;
    } finally {
      vi.useRealTimers();
    }
  });
  it("distingue las dos series reales y las cifras del corpus", () => {
    expect(benchmark("historical", "hybrid").metrics["MAP@1000"]).toBe(
      0.3500060424200144,
    );
    expect(benchmark("current", "hybrid").metrics["MAP@1000"]).toBe(
      0.3496038993782638,
    );
    expect(benchmarkData.corpus.documents).toBe(57638);
    expect(benchmarkData.corpus.vectors).toBe(57600);
    expect(
      benchmarkData.sources.every((source) => source.sha256.length === 64),
    ).toBe(true);
  });
});
