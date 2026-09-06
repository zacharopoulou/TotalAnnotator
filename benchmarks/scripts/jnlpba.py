"""Download JNLPBA into benchmarks/data/jnlpba/ as JSONL splits.

    uv run python benchmarks/scripts/jnlpba.py

JNLPBA ships as sentence-level token / BIO-tag data. The bigbio_kb config for
this corpus is a broken conversion (empty passages, one entity per token, tag
indices as types), so it is not a usable NER benchmark. Instead we read the
source config (tokens + ner_tags) and convert it properly: reconstruct the
sentence text, walk the B-/I- tags to merge tokens into one entity per mention
with real character offsets and meaningful types (protein, DNA, RNA, cell_line,
cell_type). Each row is one document (sentence) with text in passages.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

HF_DATASET = "bigbio/jnlpba"
HF_CONFIG = "jnlpba_source"  # tokens + ner_tags; the _bigbio_kb config is malformed
SPLITS = ("train", "validation")  # JNLPBA has no test split; validation is the held-out set


def _find_project_root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return None


def _default_data_dir() -> Path:
    root = _find_project_root()
    base = root if root is not None else Path.cwd()
    return base / "benchmarks" / "data" / "jnlpba"


def _split_file(data_dir: Path, split: str) -> Path:
    return data_dir / f"{split}.jsonl"


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str))
            handle.write("\n")


def _reconstruct(tokens: list[str]) -> tuple[str, list[tuple[int, int]]]:
    """Join tokens into a sentence and return per-token (start, end) char offsets."""
    text = ""
    offsets: list[tuple[int, int]] = []
    for i, tok in enumerate(tokens):
        if i > 0:
            text += " "
        start = len(text)
        text += tok
        offsets.append((start, len(text)))
    return text, offsets


def _entities_from_bio(
    tokens: list[str], tags: list[str], offsets: list[tuple[int, int]], document_id: str
) -> list[dict[str, Any]]:
    """Merge consecutive B-/I- tokens into one entity per mention with char spans."""
    entities: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if current is not None:
            entities.append({
                "id": f"{document_id}_{len(entities)}",
                "type": current["type"],
                "text": [current["text"]],
                "offsets": [[current["start"], current["end"]]],
                "normalized": [],
            })
            current = None

    for token, tag, (start, end) in zip(tokens, tags, offsets):
        if tag == "O":
            flush()
            continue
        prefix, _, etype = tag.partition("-")
        if prefix == "B" or current is None or current["type"] != etype:
            flush()
            current = {"type": etype, "text": token, "start": start, "end": end}
        else:  # I- continuing the same entity type
            current["text"] += " " + token
            current["end"] = end
    flush()
    return entities


def _to_bigbio_kb(index: int, row: dict[str, Any], tag_names: list[str]) -> dict[str, Any]:
    tokens = list(row.get("tokens") or [])
    tags = [tag_names[t] for t in (row.get("ner_tags") or [])]
    document_id = f"jnlpba_{row.get('id', index)}"
    text, offsets = _reconstruct(tokens)
    return {
        "id": str(index),
        "document_id": document_id,
        "passages": [{
            "id": f"{document_id}_p0",
            "type": "sentence",
            "text": [text],
            "offsets": [[0, len(text)]],
        }],
        "entities": _entities_from_bio(tokens, tags, offsets, document_id),
        "events": [],
        "coreferences": [],
        "relations": [],
    }


def download_split(split: str, data_dir: Path) -> Path:
    """Pull one source split from Hugging Face, convert it, and persist as JSONL."""
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise ImportError(
            "Downloading JNLPBA requires the optional 'datasets' dependency. "
            "Install with: uv sync --extra benchmarks"
        ) from exc

    ds = load_dataset(HF_DATASET, name=HF_CONFIG, split=split, trust_remote_code=True)
    tag_names = ds.features["ner_tags"].feature.names
    target = _split_file(data_dir, split)
    _write_jsonl(target, (_to_bigbio_kb(i, dict(row), tag_names) for i, row in enumerate(ds)))
    return target


def main() -> None:
    data_dir = _default_data_dir()
    print(f"JNLPBA target directory: {data_dir}")

    for split in SPLITS:
        target = _split_file(data_dir, split)
        if target.exists():
            count = sum(1 for _ in target.open(encoding="utf-8"))
            print(f"  {split:11s} already present ({count} docs) at {target}")
            continue
        print(f"  {split:11s} downloading from {HF_DATASET} ({HF_CONFIG}) ...")
        path = download_split(split, data_dir)
        count = sum(1 for _ in path.open(encoding="utf-8"))
        print(f"  {split:11s} wrote {count} docs to {path}")

    print("Done.")


if __name__ == "__main__":
    main()
