"""Download tmVar3 (bigbio_kb) into benchmarks/data/tmvar3/ as JSONL splits.

    uv run python benchmarks/scripts/tmvar3.py

tmVar3 ships as a single test set (no train/validation).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

HF_DATASET = "bigbio/tmvar_v3"
HF_CONFIG = "tmvar_v3_bigbio_kb"
SPLITS = ("test",)


def _find_project_root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return None


def _default_data_dir() -> Path:
    root = _find_project_root()
    base = root if root is not None else Path.cwd()
    return base / "benchmarks" / "data" / "tmvar3"


def _split_file(data_dir: Path, split: str) -> Path:
    return data_dir / f"{split}.jsonl"


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str))
            handle.write("\n")


def download_split(split: str, data_dir: Path) -> Path:
    """Pull one split from Hugging Face and persist it as JSONL on disk."""
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise ImportError(
            "Downloading tmVar3 requires the optional 'datasets' dependency. "
            "Install with: uv sync --extra benchmarks"
        ) from exc

    ds = load_dataset(
        HF_DATASET,
        name=HF_CONFIG,
        split=split,
        trust_remote_code=True,
    )
    target = _split_file(data_dir, split)
    _write_jsonl(target, (dict(row) for row in ds))
    return target


def main() -> None:
    data_dir = _default_data_dir()
    print(f"tmVar3 target directory: {data_dir}")

    for split in SPLITS:
        target = _split_file(data_dir, split)
        if target.exists():
            count = sum(1 for _ in target.open(encoding="utf-8"))
            print(f"  {split:11s} already present ({count} docs) at {target}")
            continue
        print(f"  {split:11s} downloading from {HF_DATASET} ...")
        path = download_split(split, data_dir)
        count = sum(1 for _ in path.open(encoding="utf-8"))
        print(f"  {split:11s} wrote {count} docs to {path}")

    print("Done.")


if __name__ == "__main__":
    main()
