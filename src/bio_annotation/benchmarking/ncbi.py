from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from bio_annotation.schemas.document import Document


@dataclass(slots=True)
class GoldAnnotation:
    """Gold benchmark annotation in the canonical annotator text coordinate space."""

    annotation_id: str
    document_id: str
    span_text: str
    start: int
    end: int
    entity_type: str = "disease"
    normalized_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "annotation_id": self.annotation_id,
            "document_id": self.document_id,
            "span_text": self.span_text,
            "start": self.start,
            "end": self.end,
            "entity_type": self.entity_type,
            "normalized_ids": list(self.normalized_ids),
        }


@dataclass(slots=True)
class BenchmarkCase:
    """One benchmark document plus its gold annotations."""

    document: Document
    gold_annotations: list[GoldAnnotation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document": {
                "document_id": self.document.document_id,
                "pmid": self.document.pmid,
                "title": self.document.title,
                "abstract": self.document.abstract,
                "source": self.document.source,
            },
            "gold_annotations": [gold.to_dict() for gold in self.gold_annotations],
            "warnings": list(self.warnings),
        }


def default_ncbi_data_path(split: str = "test") -> Path:
    return _project_root() / "benchmarks" / "data" / "ncbi" / f"{split}.jsonl"


def load_ncbi_cases(path: str | Path | None = None, *, split: str = "test") -> list[BenchmarkCase]:
    """Load NCBI Disease JSONL rows as standalone benchmark cases.

    The returned documents use the same canonical text rule as the main
    annotator adapters: title, blank line, abstract. Gold offsets are shifted
    into that canonical text coordinate system when the source row has separate
    title and abstract passages.
    """

    source = Path(path) if path is not None else default_ncbi_data_path(split)
    if not source.exists():
        raise FileNotFoundError(
            f"NCBI Disease split not found: {source}. "
            "Run benchmarks/scripts/ncbi.py or provide --benchmark-path."
        )

    cases: list[BenchmarkCase] = []
    with source.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            cases.append(case_from_bigbio_row(row, row_index=line_number))
    return cases


def case_from_bigbio_row(row: dict[str, Any], *, row_index: int = 0) -> BenchmarkCase:
    document_id = str(row.get("document_id") or row.get("id") or f"ncbi:{row_index}")
    pmid = _first_publication_id(row)
    title, abstract, passage_shifts = _extract_title_abstract_and_shifts(row)

    document = Document(
        document_id=document_id,
        pmid=pmid,
        title=title,
        abstract=abstract,
        source="benchmark:ncbi_disease",
        metadata={"benchmark": "ncbi_disease", "row_index": row_index},
    )

    canonical_text = document.text
    gold, warnings = _extract_gold_annotations(
        row,
        document_id=document_id,
        canonical_text=canonical_text,
        passage_shifts=passage_shifts,
    )
    return BenchmarkCase(document=document, gold_annotations=gold, warnings=warnings)


def _project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


def _first_publication_id(row: dict[str, Any]) -> str | None:
    for key in ("pmid", "pmids", "document_id"):
        value = row.get(key)
        if isinstance(value, str) and value.strip().isdigit():
            return value.strip()
        if isinstance(value, list):
            for item in value:
                text = str(item).strip()
                if text.isdigit():
                    return text
    return None


def _extract_title_abstract_and_shifts(row: dict[str, Any]) -> tuple[str, str, dict[int, int]]:
    passages = row.get("passages")
    if not isinstance(passages, list) or not passages:
        text = str(row.get("text") or "")
        return "", text, {}

    title_parts: list[str] = []
    abstract_parts: list[str] = []
    passage_shifts: dict[int, int] = {}

    for passage_index, passage in enumerate(passages):
        if not isinstance(passage, dict):
            continue
        text = _join_text(passage.get("text"))
        kind = _passage_type(passage)
        if kind == "title":
            target_parts = title_parts
        else:
            target_parts = abstract_parts

        current_text = " ".join(target_parts)
        canonical_start = len(current_text) + (1 if current_text else 0)
        if kind != "title" and title_parts:
            canonical_start += len(" ".join(title_parts)) + 2
        offset = _first_offset(passage)
        if offset is not None:
            passage_shifts[offset] = canonical_start - offset
        target_parts.append(text)

    return " ".join(title_parts), " ".join(abstract_parts), passage_shifts


def _extract_gold_annotations(
    row: dict[str, Any],
    *,
    document_id: str,
    canonical_text: str,
    passage_shifts: dict[int, int],
) -> tuple[list[GoldAnnotation], list[str]]:
    entities = row.get("entities")
    if not isinstance(entities, list):
        return [], ["row has no entities list"]

    gold: list[GoldAnnotation] = []
    warnings: list[str] = []
    for index, entity in enumerate(entities):
        if not isinstance(entity, dict):
            continue
        entity_type = _normalize_entity_type(entity.get("type"))
        if entity_type != "disease":
            continue
        span_text = _join_text(entity.get("text"))
        start, end = _entity_offsets(entity)
        if start is None or end is None:
            warnings.append(f"entity {index} has no usable offsets")
            continue
        start, end = _shift_offsets(start, end, passage_shifts)
        observed = canonical_text[start:end]
        if span_text and observed != span_text:
            warnings.append(
                f"entity {index} text mismatch at {start}:{end}: "
                f"expected {span_text!r}, observed {observed!r}"
            )
        gold.append(
            GoldAnnotation(
                annotation_id=str(entity.get("id") or f"{document_id}:gold:{index}"),
                document_id=document_id,
                span_text=span_text or observed,
                start=start,
                end=end,
                entity_type=entity_type,
                normalized_ids=_normalized_ids(entity.get("normalized")),
            )
        )
    return gold, warnings


def _join_text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value if item is not None).strip()
    return str(value or "").strip()


def _passage_type(passage: dict[str, Any]) -> str:
    raw = passage.get("type") or passage.get("section_type") or passage.get("infons", {}).get("type")
    text = str(raw or "").lower()
    if "title" in text:
        return "title"
    return "abstract"


def _first_offset(passage: dict[str, Any]) -> int | None:
    offsets = passage.get("offsets")
    if isinstance(offsets, list) and offsets:
        try:
            return int(offsets[0])
        except (TypeError, ValueError):
            return None
    try:
        return int(passage["offset"])
    except (KeyError, TypeError, ValueError):
        return None


def _entity_offsets(entity: dict[str, Any]) -> tuple[int | None, int | None]:
    offsets = entity.get("offsets")
    if isinstance(offsets, list) and offsets:
        first = offsets[0]
        if isinstance(first, list) and len(first) >= 2:
            return _to_int(first[0]), _to_int(first[1])
        if isinstance(first, dict):
            start = _to_int(first.get("start") or first.get("begin"))
            end = _to_int(first.get("end"))
            return start, end
    start = _to_int(entity.get("start") or entity.get("begin"))
    end = _to_int(entity.get("end"))
    return start, end


def _shift_offsets(start: int, end: int, passage_shifts: dict[int, int]) -> tuple[int, int]:
    if not passage_shifts:
        return start, end
    candidate_offsets = [offset for offset in passage_shifts if offset <= start]
    if not candidate_offsets:
        return start, end
    shift = passage_shifts[max(candidate_offsets)]
    return start + shift, end + shift


def _normalize_entity_type(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"disease", "diseases"}:
        return "disease"
    return text


def _normalized_ids(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    ids: list[str] = []
    for item in value:
        if isinstance(item, dict):
            db_name = str(item.get("db_name") or "").strip()
            db_id = str(item.get("db_id") or item.get("id") or "").strip()
            if db_name and db_id:
                ids.append(f"{db_name}:{db_id}")
            elif db_id:
                ids.append(db_id)
        elif item is not None:
            ids.append(str(item).strip())
    return tuple(identifier for identifier in ids if identifier)


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "BenchmarkCase",
    "GoldAnnotation",
    "case_from_bigbio_row",
    "default_ncbi_data_path",
    "load_ncbi_cases",
]
