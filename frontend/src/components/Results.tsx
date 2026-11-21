import { LABELS, number, type SearchResponse } from "../lib/types";
import type { SearchState } from "../lib/useSearch";
import { ResultScore } from "./ResultScore";

export function Ranking({ ranking }: { ranking: SearchResponse }) {
  return (
    <section
      className="ranking"
      tabIndex={0}
      aria-label={`Ranking ${LABELS[ranking.model]}`}
    >
      <header className="ranking-header">
        <h3>{LABELS[ranking.model]}</h3>
        <span>
          {ranking.count} results · {number(ranking.elapsed_ms, 0)} ms
        </span>
      </header>
      {!ranking.results.length && (
        <p className="empty">
          No documents found. Try different terms or another model.
        </p>
      )}
      <ol className="result-list">
        {ranking.results.map((hit) => (
          <li
            key={hit.doc_id}
            className="result"
            style={{ "--rank": Math.min(hit.rank, 8) } as React.CSSProperties}
          >
            <span className="rank" aria-label={`Position ${hit.rank}`}>
              {String(hit.rank).padStart(2, "0")}
            </span>
            <article>
              <div className="document-meta">
                <span>Document {hit.doc_id}</span>
              </div>
              <p className="document-preview" lang="en">
                {hit.preview}
              </p>
              <details>
                <summary>Read full document</summary>
                <p className="document-full" lang="en">
                  {hit.text}
                </p>
              </details>
              <ResultScore model={ranking.model} score={hit.score} />
            </article>
          </li>
        ))}
      </ol>
    </section>
  );
}
export function Results({
  state,
  cancel,
}: {
  state: SearchState;
  cancel: () => void;
}) {
  if (state.status === "idle") return null;
  if (state.status === "loading")
    return (
      <section className="loading" role="status">
        <span className="spinner" aria-hidden="true" />
        <div>
          <h2>Searching FiQA…</h2>
          <p>
            The first semantic search may take longer while the model loads.
          </p>
        </div>
        <button type="button" onClick={cancel}>
          Cancel
        </button>
      </section>
    );
  if (state.status === "error")
    return (
      <section className="error-message" role="alert">
        <h2>The search could not be completed</h2>
        <p>{state.error}</p>
      </section>
    );
  return (
    <section
      className="results-section"
      aria-label="Search results"
      aria-live="polite"
    >
      <header className="results-heading">
        <div>
          <h2>
            {state.rankings!.length > 1 ? "Ranking comparison" : "Results"}
          </h2>
          <p>{state.isDefault ? "Default model: BGE + FAISS" : state.query}</p>
        </div>
        <span>
          {number(state.elapsed!, 0)} ms{" "}
          <span className="muted">on the server</span>
        </span>
      </header>
      <div
        className={
          state.rankings!.length > 1 ? "rankings comparison" : "rankings"
        }
      >
        {state.rankings!.map((ranking) => (
          <Ranking key={ranking.model} ranking={ranking} />
        ))}
      </div>
    </section>
  );
}
