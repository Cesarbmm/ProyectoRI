"""Package the complete selected FiQA runtime without rebuilding its indexes."""

import argparse
import gzip
import hashlib
import json
import tarfile
from pathlib import Path

from ri_fiqa.config import SELECTED_CONFIG
from ri_fiqa.runtime import inspect_assets


def package_assets(root: Path, output: Path) -> dict:
    import faiss
    from datasets import load_from_disk

    root = root.resolve()
    if inspect_assets(root)["status"] != "ready":
        raise RuntimeError("The local runtime is incomplete.")
    corpus = load_from_disk(str(root / "data/raw/corpus"))
    semantic = root / "data/processed" / SELECTED_CONFIG.semantic_index
    index = faiss.read_index(str(semantic / "index.faiss"))
    if len(corpus) != 57_638 or index.ntotal != 57_600 or index.d != 768:
        raise RuntimeError("Unexpected corpus size or semantic index dimensions.")
    files = sorted((root / "data/raw/corpus").glob("*")) + [
        root / "data/processed" / SELECTED_CONFIG.lexical_index,
        semantic / "doc_ids.json",
        semantic / "index.faiss",
        semantic / "metadata.json",
    ]
    files = [path for path in files if path.is_file()]
    manifest = {
        "corpus_documents": len(corpus),
        "indexed_documents": index.ntotal,
        "dimension": index.d,
        "morphology": SELECTED_CONFIG.morphology,
        "files": [],
    }
    for path in files:
        with path.open("rb") as file:
            digest = hashlib.file_digest(file, "sha256").hexdigest()
        manifest["files"].append({
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": digest,
        })
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "runtime-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    archive = output / "fiqa-runtime.tar.gz"

    def clean(info):
        info.uid = info.gid = info.mtime = 0
        info.uname = info.gname = ""
        info.mode = 0o644
        return info

    with archive.open("wb") as target:
        with gzip.GzipFile(
            filename="", fileobj=target, mode="wb", mtime=0, compresslevel=1
        ) as zipped:
            with tarfile.open(fileobj=zipped, mode="w") as tar:
                tar.add(manifest_path, arcname="runtime-manifest.json", filter=clean)
                for path in files:
                    tar.add(path, arcname=path.relative_to(root).as_posix(), filter=clean)
    # Verify the bytes actually packaged, including the unchanged FAISS index.
    with tarfile.open(archive, "r:gz") as tar:
        for entry in manifest["files"]:
            with tar.extractfile(entry["path"]) as file:
                digest = hashlib.file_digest(file, "sha256").hexdigest()
            if digest != entry["sha256"]:
                raise RuntimeError(f"Archive checksum mismatch: {entry['path']}")
    with archive.open("rb") as file:
        digest = hashlib.file_digest(file, "sha256").hexdigest()
    return {
        "archive": str(archive), "bytes": archive.stat().st_size,
        "sha256": digest, "corpus_documents": len(corpus),
        "indexed_documents": index.ntotal,
        "note": "BGE encoder weights must also be installed separately.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(package_assets(
        args.project_root, args.output or args.project_root / "build/deployment"
    )))
