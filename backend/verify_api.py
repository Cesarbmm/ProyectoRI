"""Verify the full real API over HTTP or Vercel's authenticated Preview transport."""

import argparse
import json
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

MODELS = ["jaccard", "tfidf", "bm25", "bge", "hybrid"]
QUERY = "What is the difference between APR and APY?"


def verify(base, cli=None, scope="fonfini123-1060", diagnostics=True):
    requests = []

    def request(path, body=None):
        started = time.perf_counter()
        encoded = json.dumps(body).encode() if body is not None else None
        if cli:
            command = [shutil.which("node"), str(cli.resolve()), "curl", path,
                       "--deployment", base, "--scope", scope, "--",
                       "--silent", "--show-error", "--fail-with-body",
                       "--max-time", "285"]
            temporary = None
            try:
                if encoded is not None:
                    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as file:
                        file.write(encoded)
                        temporary = Path(file.name)
                    command += ["--request", "POST", "--header", "Content-Type: application/json",
                                "--data-binary", "@" + str(temporary)]
                result = subprocess.run(command, cwd=Path(__file__).parent,
                                        capture_output=True, text=True,
                                        encoding="utf-8", timeout=300)
                if result.returncode:
                    raise RuntimeError(f"{path}: {result.stdout[-800:]} {result.stderr[-800:]}")
                data = json.loads(result.stdout)
            finally:
                if temporary:
                    temporary.unlink(missing_ok=True)
        else:
            req = urllib.request.Request(base.rstrip("/") + path, data=encoded,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=285) as response:
                data = json.load(response)
        requests.append({"path": path, "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)})
        return data

    assert request("/health")["service"] == "fiqa-ir"
    ready = request("/ready")
    assert ready["status"] == "ready" and all(ready["components"].values()), ready
    assert ready["corpus_documents"] == 57638 and ready["indexed_documents"] == 57600
    catalog = request("/models")
    assert sorted(row["id"] for row in catalog["models"]) == sorted(MODELS)
    assert catalog["lexical_configuration"] == {
        "morphology": "stemming", "bm25_k1": 0.8, "bm25_b": 0.75,
    }
    rankings = []
    for model in MODELS:
        result = request("/search", {"query": QUERY, "model": model, "top_k": 3})
        assert result["model"] == model and result["count"] == 3
        assert [hit["rank"] for hit in result["results"]] == [1, 2, 3]
        assert all(hit["text"] and hit["doc_id"] for hit in result["results"])
        if model == "bge":
            assert result["results"][0]["doc_id"] == "263225", result
        rankings.append({"model": model, "elapsed_ms": result["elapsed_ms"],
                         "document_ids": [hit["doc_id"] for hit in result["results"]]})
    comparison = request("/search/compare", {"query": QUERY, "models": MODELS, "top_k": 3})
    assert [row["model"] for row in comparison["rankings"]] == MODELS
    for ranking, direct in zip(comparison["rankings"], rankings):
        assert [hit["doc_id"] for hit in ranking["results"]] == direct["document_ids"]
    measured = None
    if diagnostics:
        measured = request("/runtime/measure", {})
        assert measured["torch_cuda"] is None and measured["device"] == "cpu"
        assert measured["loaded_corpus_documents"] == 57638 and measured["semantic_loaded"]
        assert measured["loaded_lexical_models"] == ["bm25", "jaccard", "tfidf"]
        assert measured["configuration"] == {
            "morphology": "stemming", "bm25_k1": 0.8, "bm25_b": 0.75,
            "rrf_k": 10, "bge_weight": 0.9,
        }
        assert measured["peak_rss_bytes"] < 2048 * 1024 * 1024, measured
    return {"base_url": base, "transport": "vercel curl" if cli else "HTTP",
            "passed": True, "rankings": rankings, "requests": requests,
            "comparison_models": len(comparison["rankings"]), "runtime": measured}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--cli", type=Path, help="Path to the pinned Vercel CLI dist/vc.js")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--no-diagnostics", action="store_true")
    args = parser.parse_args()
    report = verify(args.url, args.cli, diagnostics=not args.no_diagnostics)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "rankings": report["rankings"],
                      "runtime": report["runtime"]}), flush=True)
