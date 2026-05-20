"""Per-split summary of the BC5CDR corpus (entities, normalization, relations, top mentions).

    uv run python benchmarks/analytics/bc5cdr_analytics.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

SPLITS = ("train", "validation", "test")


def _project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return here.parent


DATA_DIR = _project_root() / "benchmarks" / "data" / "bc5cdr"


def load_split(split: str) -> pd.DataFrame:
    return pd.read_json(DATA_DIR / f"{split}.jsonl", lines=True)


def entities_table(df: pd.DataFrame) -> pd.DataFrame:
    ent = (
        df[["document_id", "entities"]]
        .explode("entities")
        .dropna(subset=["entities"])
        .reset_index(drop=True)
    )
    ent = ent.join(pd.json_normalize(ent["entities"])).drop(columns=["entities"])
    ent["text_joined"] = ent["text"].apply(lambda xs: " ".join(xs) if isinstance(xs, list) else "")
    ent["span_length"] = ent["text_joined"].str.len()
    ent["norm_count"] = ent["normalized"].apply(lambda xs: len(xs) if isinstance(xs, list) else 0)
    return ent


def relations_table(df: pd.DataFrame) -> pd.DataFrame:
    """One row per CID relation with chemical and disease info joined in."""
    rows: list[dict] = []
    for _, doc_row in df.iterrows():
        entities = doc_row.get("entities")
        relations = doc_row.get("relations")
        if not isinstance(entities, list) or not isinstance(relations, list):
            continue

        ent_by_id: dict[str, dict] = {}
        for ent in entities:
            if not isinstance(ent, dict):
                continue
            ent_id = ent.get("id")
            if not ent_id:
                continue
            text_list = ent.get("text") or []
            mention = " ".join(text_list) if isinstance(text_list, list) else str(text_list)
            normalized = ent.get("normalized") or []
            db_id = ""
            if isinstance(normalized, list) and normalized and isinstance(normalized[0], dict):
                db_id = str(normalized[0].get("db_id", ""))
            ent_by_id[ent_id] = {
                "type": ent.get("type", ""),
                "mention": mention,
                "db_id": db_id,
            }

        for rel in relations:
            if not isinstance(rel, dict):
                continue
            rel_type = rel.get("type", "")
            arg1 = ent_by_id.get(rel.get("arg1_id"), {})
            arg2 = ent_by_id.get(rel.get("arg2_id"), {})
            # BC5CDR CID: arg1 is Chemical, arg2 is Disease (per the bigbio mapping).
            chemical = arg1 if arg1.get("type") == "Chemical" else arg2
            disease = arg2 if arg2.get("type") == "Disease" else arg1
            rows.append({
                "document_id": doc_row.get("document_id"),
                "type": rel_type,
                "chemical_mention": chemical.get("mention", ""),
                "chemical_id": chemical.get("db_id", ""),
                "disease_mention": disease.get("mention", ""),
                "disease_id": disease.get("db_id", ""),
            })
    return pd.DataFrame(rows)


def analyze_split(name: str, df: pd.DataFrame) -> str:
    ent = entities_table(df)
    rel = relations_table(df)

    parts: list[str] = []
    parts.append(f"## {name.upper()}\n")
    parts.append(f"- Documents: **{len(df)}**")
    parts.append(
        f"- Entity mentions: **{len(ent)}** across **{ent['document_id'].nunique()}** documents"
    )
    parts.append(f"- Relations: **{len(rel)}**\n")

    parts.append("### Entity counts by type\n")
    parts.append(ent.groupby("type").size().rename("n_mentions").to_markdown())
    parts.append("")

    parts.append("### Entities per document\n")
    parts.append(
        ent.groupby("document_id")
        .size()
        .describe()[["count", "mean", "min", "50%", "max"]]
        .round(1)
        .to_markdown()
    )
    parts.append("")

    parts.append("### Span length (chars)\n")
    parts.append(
        ent["span_length"]
        .describe()[["count", "mean", "min", "50%", "max"]]
        .round(1)
        .to_markdown()
    )
    parts.append("")

    with_norm = int((ent["norm_count"] > 0).sum())
    pct = with_norm / len(ent) * 100 if len(ent) else 0.0
    parts.append(f"### Normalization: {with_norm} / {len(ent)} ({pct:.1f}%)\n")
    if with_norm > 0:
        norm_long = (
            ent.loc[ent["norm_count"] > 0, ["normalized"]]
            .explode("normalized")
            .reset_index(drop=True)
            .pipe(lambda d: d.join(pd.json_normalize(d["normalized"])).drop(columns=["normalized"]))
        )
        parts.append(norm_long.groupby("db_name").size().rename("n_ids").to_markdown())
        parts.append("")

    parts.append("### Top 5 mentions per entity type (case-insensitive)\n")
    for type_name, group in ent.groupby("type"):
        top5 = group["text_joined"].str.lower().value_counts().head(5).rename("n")
        parts.append(f"#### {type_name}\n")
        parts.append(top5.to_markdown())
        parts.append("")

    # Relations (BC5CDR-specific)
    if len(rel) > 0:
        parts.append("### Relations (CID = Chemical-Induced-Disease)\n")
        parts.append(rel.groupby("type").size().rename("n_relations").to_markdown())
        parts.append("")

        parts.append("#### Relations per document\n")
        parts.append(
            rel.groupby("document_id")
            .size()
            .describe()[["count", "mean", "min", "50%", "max"]]
            .round(1)
            .to_markdown()
        )
        parts.append("")

        parts.append("#### Top 10 chemical to disease pairs (case-insensitive)\n")
        pair_counts = (
            rel.assign(
                pair=rel["chemical_mention"].str.lower()
                + " -> "
                + rel["disease_mention"].str.lower()
            )["pair"]
            .value_counts()
            .head(10)
            .rename("n")
        )
        parts.append(pair_counts.to_markdown())
        parts.append("")

    text = "\n".join(parts)
    print(text)
    return text


def main() -> None:
    print(f"BC5CDR analytics, data dir: {DATA_DIR}\n")
    if not DATA_DIR.is_dir():
        raise SystemExit(
            f"Data directory not found: {DATA_DIR}\n"
            "Run benchmarks/scripts/bc5cdr.py first to download the corpus."
        )

    chunks: list[str] = ["# BC5CDR analytics\n"]
    for split in SPLITS:
        target = DATA_DIR / f"{split}.jsonl"
        if not target.exists():
            print(f"Skipping {split}: {target} not found.\n")
            continue
        df = load_split(split)
        chunks.append(analyze_split(split, df))

    summary_path = DATA_DIR / "BC5CDR_ANALYTICS_SUMMARY.md"
    summary_path.write_text("\n".join(chunks), encoding="utf-8")
    print(f"\nSaved to: {summary_path}")


if __name__ == "__main__":
    main()
