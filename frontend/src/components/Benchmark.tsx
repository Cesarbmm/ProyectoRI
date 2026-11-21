import { useState } from "react";
import {
  benchmarkData,
  benchmarkLabel,
  METRICS,
  metricLabel,
  type Metric,
} from "../lib/benchmark";
import { DEFAULT_MODEL, number, type ModelId } from "../lib/types";

export function Evaluation() {
  const [metric, setMetric] = useState<Metric>("MAP@1000");
  const rows = benchmarkData.current;
  const maximum = Math.max(...rows.map((row) => row.metrics[metric]));
  return (
    <section
      className="evaluation page-section"
      aria-labelledby="evaluation-title"
    >
      <header className="page-heading">
        <div>
          <h1 id="evaluation-title">Evaluation</h1>
          <p>Four active models, the same 648 FiQA test queries.</p>
        </div>
      </header>
      <p className="evaluation-note">
        Final configuration: Snowball and BM25 k1=0.8, b=0.75. Selected on
        validation and checked on test without retuning. BGE remains unchanged.
        BGE + FAISS is the default. Hybrid results are retained as a historical
        reference.
      </p>
      <div className="evaluation-layout">
        <div className="chart-panel glass">
          <div className="chart-control">
            <label htmlFor="chart-metric">Compare by</label>
            <select
              id="chart-metric"
              value={metric}
              onChange={(e) => setMetric(e.target.value as Metric)}
            >
              {METRICS.map((key) => (
                <option key={key} value={key}>
                  {metricLabel(key)}
                </option>
              ))}
            </select>
          </div>
          <div
            className="bar-chart"
            role="img"
            aria-label={`Chart of ${metricLabel(metric)}. Exact values are in the table.`}
          >
            {rows.map((row) => (
              <div className="chart-row" key={row.model}>
                <span>{benchmarkLabel(row.model as ModelId)}</span>
                <div className="bar-track">
                  <div
                    className={
                      row.model === DEFAULT_MODEL
                        ? "bar recommended-bar"
                        : "bar"
                    }
                    style={{
                      width: `${(row.metrics[metric] / maximum) * 100}%`,
                    }}
                  />
                </div>
                <strong>{number(row.metrics[metric])}</strong>
              </div>
            ))}
          </div>
          <p className="muted chart-caption">
            Bar lengths are relative to the highest value of the selected
            metric.
          </p>
        </div>
        <div className="evaluation-context">
          <h2>Understanding the results</h2>
          <p>
            MAP@1000 summarises ranking quality and is the primary metric.
            NDCG@10 focuses on the top positions; Precision@10 and Recall@100
            measure precision and coverage.
          </p>
          <p>
            These are benchmark averages based on relevance judgments. Precision
            and MAP cannot be calculated for a free-text query without those
            judgments.
          </p>
          <p className="muted">
            BGE + FAISS is recommended for semantic retrieval. Evaluation depth:
            1,000 documents.
          </p>
        </div>
      </div>
      <div
        className="table-scroll"
        role="region"
        aria-label="Metrics comparison table"
        tabIndex={0}
      >
        <table>
          <caption>Final configuration · Snowball · FiQA test</caption>
          <thead>
            <tr>
              <th scope="col">Model</th>
              {METRICS.map((key) => (
                <th scope="col" key={key}>
                  {metricLabel(key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.model}
                className={row.model === DEFAULT_MODEL ? "highlight-row" : ""}
              >
                <th scope="row">{benchmarkLabel(row.model as ModelId)}</th>
                {METRICS.map((key) => (
                  <td key={key}>{number(row.metrics[key])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
