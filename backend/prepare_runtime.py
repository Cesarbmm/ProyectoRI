"""Download and verify immutable full FiQA assets during the Linux build."""

import argparse
import hashlib
import importlib.metadata
import json
import shutil
import tarfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent


def verified(path, spec):
    if not path.is_file() or path.stat().st_size != spec["bytes"]:
        return False
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest() == spec["sha256"]


def download(url, destination, spec):
    if not url.startswith("https://"):
        raise ValueError("Runtime downloads require HTTPS.")
    if verified(destination, spec):
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "ProyectoRI-build/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as file:
                shutil.copyfileobj(response, file, length=1024 * 1024)
            if not verified(partial, spec):
                raise ValueError(f"Checksum mismatch: {destination.name}")
            partial.replace(destination)
            return
        except Exception:
            partial.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def unpack(archive, root, specs):
    expected = {entry["path"]: entry for entry in specs}
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        if {item.name for item in members} != set(expected) | {"runtime-manifest.json"}:
            raise ValueError("Unexpected files in the runtime archive.")
        for item in members:
            destination = (root / item.name).resolve()
            if not item.isfile() or not destination.is_relative_to(root.resolve()):
                raise ValueError("Unsafe runtime archive member.")
            if item.name == "runtime-manifest.json":
                continue
            spec = expected[item.name]
            if item.size != spec["bytes"]:
                raise ValueError("Runtime archive file size mismatch.")
            if not verified(destination, spec):
                destination.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(item) as source, destination.open("wb") as target:
                    shutil.copyfileobj(source, target, length=1024 * 1024)
            if not verified(destination, spec):
                raise ValueError(f"Extracted file checksum mismatch: {item.name}")


def prepare(runtime, archive_file=None, encoder_source=None):
    started = time.perf_counter()
    manifest = json.loads((HERE / "assets-manifest.json").read_text(encoding="utf-8"))
    runtime.mkdir(parents=True, exist_ok=True)
    archive = archive_file or runtime / "fiqa-runtime.tar.gz"
    if archive_file:
        if not verified(archive, manifest["archive"]):
            raise ValueError("Local runtime archive checksum mismatch.")
    else:
        download(manifest["archive"]["url"], archive, manifest["archive"])
    unpack(archive, runtime, manifest["files"])
    if not archive_file:
        archive.unlink()  # The uncompressed verified assets are the function payload.

    encoder = manifest["encoder"]
    cache = runtime / "hf/hub" / ("models--" + encoder["model_id"].replace("/", "--"))
    snapshot = cache / "snapshots" / encoder["revision"]

    def model_file(spec):
        destination = snapshot / spec["path"]
        if encoder_source:
            source = encoder_source / spec["path"]
            if not verified(source, spec):
                raise ValueError("Local encoder checksum mismatch.")
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not verified(destination, spec):
                shutil.copyfile(source, destination)
        else:
            url = f"https://huggingface.co/{encoder['model_id']}/resolve/{encoder['revision']}/{spec['path']}"
            download(url, destination, spec)

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(model_file, encoder["files"]))
    (cache / "refs").mkdir(exist_ok=True)
    (cache / "refs/main").write_text(encoder["revision"], encoding="utf-8")
    shutil.copytree(HERE.parent / "src/ri_fiqa", HERE / "ri_fiqa", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    import faiss
    import torch
    from datasets import load_from_disk

    if torch.version.cuda is not None:
        raise RuntimeError("The production runtime must use PyTorch CPU.")
    corpus = load_from_disk(str(runtime / "data/raw/corpus"))
    index = faiss.read_index(str(runtime / "data/processed/semantic_bge/index.faiss"))
    if len(corpus) != 57638 or index.ntotal != 57600 or index.d != 768:
        raise RuntimeError("The complete corpus or FAISS index is inconsistent.")
    report = {
        "corpus_documents": len(corpus), "indexed_documents": index.ntotal,
        "dimension": index.d, "encoder_revision": encoder["revision"],
        "archive_sha256": manifest["archive"]["sha256"],
        "torch_cuda": torch.version.cuda, "download_on_request": False,
        "asset_bytes": sum(item["bytes"] for item in manifest["files"] + encoder["files"]),
        "build_seconds": round(time.perf_counter() - started, 3),
        "versions": {name: importlib.metadata.version(name) for name in
                     ("torch", "faiss-cpu", "sentence-transformers", "datasets", "numpy")},
    }
    (runtime / "build-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, default=HERE / "runtime")
    parser.add_argument("--archive-file", type=Path)
    parser.add_argument("--encoder-source", type=Path)
    args = parser.parse_args()
    prepare(args.runtime_dir.resolve(), args.archive_file, args.encoder_source)
