import { useEffect, useState, type FormEvent, type Ref } from "react";
import {
  LABELS,
  DEFAULT_MODEL,
  DEFAULT_MODEL_LABEL,
  isActiveModel,
  type ModelChoice,
  type ModelId,
  type ModelsInfo,
} from "../lib/types";
import { SearchIcon } from "./Icon";
import { ModelSelect } from "./ModelSelect";

const EXAMPLES = [
  ["APR vs. APY", "What is the difference between APR and APY?"],
  ["Retirement savings", "How can I invest for retirement?"],
  ["Index funds", "How do index funds work?"],
];
type Props = {
  models?: ModelsInfo;
  connected: boolean;
  busy: boolean;
  choice: ModelChoice;
  compact?: boolean;
  resetToken?: number;
  barRef?: Ref<HTMLDivElement>;
  onChoice: (model: ModelChoice) => void;
  onSearch: (
    query: string,
    choice: ModelChoice,
    topK: number,
    comparison: ModelId[] | null,
  ) => void;
};
export function SearchForm({
  models,
  connected,
  busy,
  choice,
  onChoice,
  onSearch,
  compact = false,
  resetToken = 0,
  barRef,
}: Props) {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [compare, setCompare] = useState(false);
  const [compared, setCompared] = useState<ModelId[]>(["bm25", "bge"]);
  const [error, setError] = useState("");
  const [suggestionsOpen, setSuggestionsOpen] = useState(true);
  useEffect(() => {
    setSuggestionsOpen(!compact);
  }, [compact]);
  useEffect(() => {
    setQuery("");
    setCompare(false);
    setError("");
  }, [resetToken]);
  const available = (models?.models ?? []).filter((model) =>
    isActiveModel(model.id),
  );
  const availableIds = new Set(available.map((m) => m.id));
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) {
      setError("Enter a query to search.");
      return;
    }
    if (compare && compared.filter((m) => availableIds.has(m)).length < 2) {
      setError("Select at least two models to compare.");
      return;
    }
    setError("");
    onSearch(
      query,
      choice,
      topK,
      compare ? compared.filter((m) => availableIds.has(m)) : null,
    );
  }
  return (
    <form
      onSubmit={submit}
      aria-label="Document search"
      className="search-form"
    >
      <div ref={barRef} className="search-bar glass">
        <SearchIcon />
        <label className="sr-only" htmlFor="query">
          Query
        </label>
        <input
          id="query"
          value={query}
          maxLength={500}
          placeholder="What would you like to find?"
          disabled={busy}
          onChange={(e) => {
            setQuery(e.target.value);
            setError("");
          }}
          aria-describedby={error ? "form-error" : undefined}
          aria-invalid={!!error}
          autoComplete="off"
        />
        <div className="select-model">
          <ModelSelect
            value={choice}
            disabled={busy || compare}
            onChange={onChoice}
            options={[
              {
                value: DEFAULT_MODEL,
                label: DEFAULT_MODEL_LABEL,
                disabled: connected && !availableIds.has(DEFAULT_MODEL),
              },
              ...available
                .filter((model) => model.id !== DEFAULT_MODEL)
                .map((model) => ({
                  value: model.id as ModelChoice,
                  label: LABELS[model.id],
                })),
            ]}
          />
        </div>
        <button
          className="primary"
          type="submit"
          disabled={
            busy || !connected || (!compare && !availableIds.has(choice))
          }
        >
          {busy ? "Searching…" : "Search"}
        </button>
      </div>
      <div className="search-options">
        <div className="quantity">
          <label htmlFor="top-k">Results</label>
          <select
            id="top-k"
            value={topK}
            disabled={busy}
            onChange={(e) => setTopK(Number(e.target.value))}
          >
            {[3, 5, 10, 20].map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </div>
        <label className="switch-label" htmlFor="compare">
          Compare models{" "}
          <input
            id="compare"
            type="checkbox"
            checked={compare}
            disabled={busy}
            onChange={(e) => setCompare(e.target.checked)}
          />
          <span className="switch-track" aria-hidden="true" />
        </label>
      </div>
      {compare && (
        <fieldset className="comparison-models" disabled={busy}>
          <legend>Select 2 to 4 models</legend>
          {available.map(({ id }) => (
            <label key={id}>
              <input
                type="checkbox"
                checked={compared.includes(id)}
                onChange={(e) =>
                  setCompared((prev) =>
                    e.target.checked
                      ? [...prev, id]
                      : prev.filter((m) => m !== id),
                  )
                }
              />
              {LABELS[id]}
            </label>
          ))}
        </fieldset>
      )}
      {error && (
        <p id="form-error" role="alert" className="form-error">
          {error}
        </p>
      )}
      <section className="suggestions" aria-label="Suggestions">
        <h2>
          <button
            type="button"
            aria-expanded={suggestionsOpen}
            aria-controls="query-examples"
            onClick={() => setSuggestionsOpen((value) => !value)}
          >
            Suggestions
          </button>
        </h2>
        <div
          id="query-examples"
          className="examples"
          aria-label="Example queries"
          hidden={!suggestionsOpen}
        >
          {EXAMPLES.map(([label, text]) => (
            <button
              key={label}
              type="button"
              disabled={busy}
              onClick={() => {
                setQuery(text);
                setError("");
                document.getElementById("query")?.focus();
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </section>
    </form>
  );
}
