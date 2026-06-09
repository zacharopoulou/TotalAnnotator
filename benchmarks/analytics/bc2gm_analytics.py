"""Per-split summary of the BC2GM corpus (IOB token format).

    uv run python benchmarks/analytics/bc2gm_analytics.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

SPLITS = ("train", "validation", "test")

# spyysalo/bc2gm_corpus tag mapping
TAG_NAMES = {0: "O", 1: "B-GENE", 2: "I-GENE"}


def _project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return here.parent


DATA_DIR = _project_root() / "benchmarks" / "data" / "bc2gm"


def load_split(split: str) -> pd.DataFrame:
    return pd.read_json(DATA_DIR / f"{split}.jsonl", lines=True)


def _tag_to_str(tag) -> str:
    if isinstance(tag, str):
        return tag
    try:
        return TAG_NAMES.get(int(tag), "O")
    except (ValueError, TypeError):
        return "O"


def reconstruct_mentions(df: pd.DataFrame) -> pd.DataFrame:
    """Walk IOB tags to extract one row per gene mention."""
    rows = []
    for _, row in df.iterrows():
        sentence_id = row.get("id")
        tokens = row.get("tokens") or []
        tags = row.get("ner_tags") or []
        if not isinstance(tokens, list) or not isinstance(tags, list):
            continue
        if len(tokens) != len(tags):
            continue

        current: list[str] = []
        for tok, tag in zip(tokens, tags):
            tag_str = _tag_to_str(tag)
            if tag_str == "B-GENE":
                if current:
                    rows.append({"id": sentence_id, "mention": " ".join(current), "n_tokens": len(current)})
                current = [tok]
            elif tag_str == "I-GENE":
                if current:
                    current.append(tok)
                else:
                    current = [tok]  # stray I-GENE, treat as start
            else:
                if current:
                    rows.append({"id": sentence_id, "mention": " ".join(current), "n_tokens": len(current)})
                    current = []
        if current:
            rows.append({"id": sentence_id, "mention": " ".join(current), "n_tokens": len(current)})
    return pd.DataFrame(rows)


def token_tag_counts(df: pd.DataFrame) -> pd.Series:
    counts: dict[str, int] = {"O": 0, "B-GENE": 0, "I-GENE": 0}
    for tags in df["ner_tags"]:
        if not isinstance(tags, list):
            continue
        for tag in tags:
            label = _tag_to_str(tag)
            counts[label] = counts.get(label, 0) + 1
    return pd.Series(counts, name="n_tokens")


def analyze_split(name: str, df: pd.DataFrame) -> str:
    mentions = reconstruct_mentions(df)
    tag_counts = token_tag_counts(df)
    per_sentence = mentions.groupby("id").size().reindex(df["id"], fill_value=0)

    parts: list[str] = []
    parts.append(f"## {name.upper()}\n")
    parts.append(f"- Sentences: **{len(df)}**")
    parts.append(f"- Tokens (total): **{int(tag_counts.sum())}**")
    parts.append(f"- Gene mentions: **{len(mentions)}**\n")

    parts.append("### Tag distribution\n")
    parts.append(tag_counts.to_markdown())
    parts.append("")

    parts.append("### Gene mentions per sentence\n")
    parts.append(
        per_sentence.describe()[["count", "mean", "min", "50%", "max"]]
        .round(2)
        .to_markdown()
    )
    parts.append("")

    parts.append("### Mention length (tokens)\n")
    parts.append(
        mentions["n_tokens"]
        .describe()[["count", "mean", "min", "50%", "max"]]
        .round(2)
        .to_markdown()
    )
    parts.append("")

    parts.append("### Top 10 mentions (case-insensitive)\n")
    top10 = mentions["mention"].str.lower().value_counts().head(10).rename("n")
    parts.append(top10.to_markdown())
    parts.append("")

    text = "\n".join(parts)
    print(text)
    return text


def main() -> None:
    print(f"BC2GM analytics, data dir: {DATA_DIR}\n")
    if not DATA_DIR.is_dir():
        raise SystemExit(
            f"Data directory not found: {DATA_DIR}\n"
            "Run benchmarks/scripts/bc2gm.py first to download the corpus."
        )

    chunks: list[str] = ["# BC2GM analytics\n"]
    for split in SPLITS:
        target = DATA_DIR / f"{split}.jsonl"
        if not target.exists():
            print(f"Skipping {split}: {target} not found.\n")
            continue
        df = load_split(split)
        chunks.append(analyze_split(split, df))

    summary_path = DATA_DIR / "BC2GM_ANALYTICS_SUMMARY.md"
    summary_path.write_text("\n".join(chunks), encoding="utf-8")
    print(f"\nSaved to: {summary_path}")


if __name__ == "__main__":
    main()
