"""Download MACCROBAT into benchmarks/data/maccrobat/ as a JSONL test set.

    uv run python benchmarks/scripts/maccrobat.py

MACCROBAT is not part of BigBIO. It is pulled from the Hugging Face dataset
singh-aditya/MACCROBAT_biomedical_ner (200 clinical case reports, char-offset
NER spans) and converted here into the same bigbio_kb shape the other benchmarks
use, so the shared analytics works unchanged. The corpus ships as a single set,
committed as test.jsonl (there is no official train/test split).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

HF_DATASET = "singh-aditya/MACCROBAT_biomedical_ner"
HF_SPLIT = "train"  # the only split; used as the evaluation set


def _find_project_root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return None


def _default_data_dir() -> Path:
    root = _find_project_root()
    base = root if root is not None else Path.cwd()
    return base / "benchmarks" / "data" / "maccrobat"


def _split_file(data_dir: Path, split: str) -> Path:
    return data_dir / f"{split}.jsonl"


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str))
            handle.write("\n")


def _to_bigbio_kb(index: int, row: dict[str, Any]) -> dict[str, Any]:
    """Map one MACCROBAT record (full_text + ner_info) to the bigbio_kb shape."""
    text = row.get("full_text") or ""
    document_id = f"maccrobat_{index}"
    entities = []
    for j, span in enumerate(row.get("ner_info") or []):
        if not isinstance(span, dict):
            continue
        start = span.get("start")
        end = span.get("end")
        entities.append({
            "id": f"{document_id}_{j}",
            "type": span.get("label"),
            "text": [span.get("text")],
            "offsets": [[start, end]],
            "normalized": [],
        })
    return {
        "id": document_id,
        "document_id": document_id,
        "passages": [{
            "id": f"{document_id}_p0",
            "type": "case_report",
            "text": [text],
            "offsets": [[0, len(text)]],
        }],
        "entities": entities,
        "events": [],
        "coreferences": [],
        "relations": [],
    }


def download() -> Path:
    """Pull MACCROBAT from Hugging Face and persist it as bigbio_kb JSONL."""
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise ImportError(
            "Downloading MACCROBAT requires the optional 'datasets' dependency. "
            "Install with: uv sync --extra benchmarks"
        ) from exc

    ds = load_dataset(HF_DATASET, split=HF_SPLIT)
    data_dir = _default_data_dir()
    target = _split_file(data_dir, "test")
    _write_jsonl(target, (_to_bigbio_kb(i, dict(row)) for i, row in enumerate(ds)))
    return target


def main() -> None:
    data_dir = _default_data_dir()
    print(f"MACCROBAT target directory: {data_dir}")

    target = _split_file(data_dir, "test")
    if target.exists():
        count = sum(1 for _ in target.open(encoding="utf-8"))
        print(f"  test        already present ({count} docs) at {target}")
        return
    print(f"  test        downloading from {HF_DATASET} ...")
    path = download()
    count = sum(1 for _ in path.open(encoding="utf-8"))
    print(f"  test        wrote {count} docs to {path}")
    print("Done.")


if __name__ == "__main__":
    main()
