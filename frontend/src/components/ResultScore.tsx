import { useId, useState } from "react";
import { displayScore, SCORE_INFO } from "../lib/scores";
import { LABELS, type ModelId } from "../lib/types";

export function ResultScore({
  model,
  score,
}: {
  model: ModelId;
  score: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const explanationId = useId();
  const info = SCORE_INFO[model];
  return (
    <div className="result-score">
      <div className="score-label">
        <span>
          {info.label}:{" "}
          <span className="score-value">{displayScore(model, score)}</span>
        </span>
        <button
          type="button"
          className="score-info-toggle"
          aria-label={`Explain ${info.label.toLowerCase()}`}
          aria-expanded={expanded}
          aria-controls={explanationId}
          title={info.explanation}
          onClick={() => setExpanded((value) => !value)}
          onKeyDown={(event) => {
            if (event.key === "Escape") setExpanded(false);
          }}
        >
          <svg
            width="17"
            height="17"
            viewBox="0 0 20 20"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            aria-hidden="true"
          >
            <circle cx="10" cy="10" r="8" />
            <path d="M10 9v5" />
            <circle cx="10" cy="6" r=".9" fill="currentColor" stroke="none" />
          </svg>
        </button>
      </div>
      <p id={explanationId} className="score-explanation" hidden={!expanded}>
        {info.explanation} Scores are only meaningful within the same model.
      </p>
      <details className="technical-score">
        <summary>Technical score</summary>
        <p>
          Raw {LABELS[model]} score: <code>{String(score)}</code>. The displayed
          label is rounded for readability; the original score and ranking are
          unchanged.
        </p>
      </details>
    </div>
  );
}
