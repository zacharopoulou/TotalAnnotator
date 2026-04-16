from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Callable

from bio_annotation.io.readers import fetch_pubmed_record
from bio_annotation.pipeline_config import PipelineConfig
from bio_annotation.schemas.document import Document


PubMedFetcher = Callable[[str], dict[str, Any]]


def load_document_from_pmid(
    pmid: str,
    *,
    extra_metadata: dict[str, Any] | None = None,
    fetcher: PubMedFetcher | None = None,
) -> Document:
    record = (fetcher or fetch_pubmed_record)(pmid)
    normalized_pmid = str(record.get("pmid") or pmid).strip()
    metadata = extra_metadata.copy() if extra_metadata else {}
    metadata["pubmed_record"] = dict(record)

    return Document(
        document_id=f"PMID:{normalized_pmid}",
        pmid=normalized_pmid,
        title=str(record.get("title") or "").strip(),
        abstract=str(record.get("abstract") or "").strip(),
        full_text=None,
        source="pubmed",
        year=_clean_optional_text(record.get("year")),
        metadata=metadata,
    )


def load_document_from_text(
    document_id: str,
    *,
    title: str = "",
    abstract: str = "",
    source: str = "text_table",
    extra_metadata: dict[str, Any] | None = None,
) -> Document:
    cleaned_document_id = str(document_id).strip()
    if not cleaned_document_id:
        raise ValueError("document_id must not be empty.")

    metadata = extra_metadata.copy() if extra_metadata else {}
    return Document(
        document_id=cleaned_document_id,
        title=title.strip(),
        abstract=abstract.strip(),
        full_text=None,
        source=source,
        metadata=metadata,
    )


def load_documents_from_pmids(
    pmids: list[str],
    *,
    fetcher: PubMedFetcher | None = None,
) -> list[Document]:
    documents: list[Document] = []
    for pmid in _dedupe_pmids(pmids):
        documents.append(load_document_from_pmid(pmid, fetcher=fetcher))
    return documents


def load_documents_from_pmid_file(
    path: Path,
    *,
    fetcher: PubMedFetcher | None = None,
) -> list[Document]:
    pmids = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return load_documents_from_pmids(pmids, fetcher=fetcher)


def load_documents_from_text_table(
    path: Path,
    *,
    fmt: str,
    document_id_column: str,
    title_column: str,
    abstract_column: str,
) -> list[Document]:
    delimiter = _delimiter_for_format(fmt)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError(f"{path} must contain a header row.")
        _validate_columns(
            path,
            reader.fieldnames,
            [document_id_column, title_column, abstract_column],
        )

        documents: list[Document] = []
        for index, row in enumerate(reader, start=2):
            document_id = (row.get(document_id_column) or "").strip()
            if not document_id:
                raise ValueError(f"{path} row {index} is missing {document_id_column}.")
            title = (row.get(title_column) or "").strip()
            abstract = (row.get(abstract_column) or "").strip()
            metadata = {
                key: value
                for key, value in row.items()
                if key not in {document_id_column, title_column, abstract_column}
            }
            documents.append(
                load_document_from_text(
                    document_id,
                    title=title,
                    abstract=abstract,
                    source="text_table",
                    extra_metadata=metadata,
                )
            )
    return documents


def load_documents_from_config(
    config: PipelineConfig,
    *,
    pmid_fetcher: PubMedFetcher | None = None,
) -> list[Document]:
    mode = config.input_mode
    if mode == "pmids":
        return load_documents_from_pmids(config.pmids, fetcher=pmid_fetcher)
    if mode == "pmid_file":
        if config.pmid_file is None:
            raise ValueError("input.pmid_file must be set when input.mode = 'pmid_file'.")
        return load_documents_from_pmid_file(config.pmid_file, fetcher=pmid_fetcher)
    if mode == "text_table":
        if config.text_file is None:
            raise ValueError("input.text_file must be set when input.mode = 'text_table'.")
        return load_documents_from_text_table(
            config.text_file,
            fmt=config.text_format,
            document_id_column=config.document_id_column,
            title_column=config.title_column,
            abstract_column=config.abstract_column,
        )
    if mode == "corpus":
        if config.corpus_path is None:
            raise ValueError("input.corpus_path must be set when input.mode = 'corpus'.")
        return load_corpus_documents(config.corpus_path)
    raise ValueError(f"Unsupported input mode: {mode}")


def resolve_input_description(config: PipelineConfig) -> dict[str, Any]:
    if config.input_mode == "pmids":
        return {
            "mode": "pmids",
            "pmid_count": len(_dedupe_pmids(config.pmids)),
            "pmid_file": None,
            "text_file": None,
            "corpus_path": None,
        }
    if config.input_mode == "pmid_file":
        return {
            "mode": "pmid_file",
            "pmid_count": None,
            "pmid_file": str(config.pmid_file) if config.pmid_file is not None else None,
            "text_file": None,
            "corpus_path": None,
        }
    if config.input_mode == "text_table":
        return {
            "mode": "text_table",
            "pmid_count": None,
            "pmid_file": None,
            "text_file": str(config.text_file) if config.text_file is not None else None,
            "corpus_path": None,
        }
    return {
        "mode": "corpus",
        "pmid_count": None,
        "pmid_file": None,
        "text_file": None,
        "corpus_path": str(config.corpus_path) if config.corpus_path is not None else None,
    }


def summarize_ingestion(documents: list[Document]) -> dict[str, Any]:
    pmid_documents = sum(1 for document in documents if document.pmid)
    documents_with_pmcid = sum(
        1
        for document in documents
        if isinstance(document.metadata.get("pubmed_record"), dict)
        and document.metadata["pubmed_record"].get("pmcid")
    )
    return {
        "document_count": len(documents),
        "pmid_documents": pmid_documents,
        "documents_with_pmcid": documents_with_pmcid,
    }


def load_corpus_documents(path: Path) -> list[Document]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        records = payload.get("documents", [])
    elif isinstance(payload, list):
        records = payload
    else:
        raise ValueError(f"{path} must contain a list of documents or a top-level documents list.")

    documents: list[Document] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"{path} contains a non-object record at index {index}.")
        documents.append(_build_document_from_record(record, index=index))
    return documents


def _delimiter_for_format(fmt: str) -> str:
    cleaned = fmt.strip().lower()
    if cleaned == "csv":
        return ","
    if cleaned == "tsv":
        return "\t"
    raise ValueError(f"Unsupported text table format: {fmt}")


def _validate_columns(path: Path, fieldnames: list[str], required: list[str]) -> None:
    missing = [column for column in required if column not in fieldnames]
    if missing:
        raise ValueError(f"{path} is missing required columns: {', '.join(missing)}")


def _dedupe_pmids(pmids: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for pmid in pmids:
        cleaned = str(pmid).strip()
        if cleaned.upper().startswith("PMID:"):
            cleaned = cleaned.split(":", 1)[1].strip()
        if not cleaned:
            continue
        if cleaned not in seen:
            seen.add(cleaned)
            out.append(cleaned)
    return out


def _clean_optional_text(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _build_document_from_record(record: dict[str, Any], *, index: int) -> Document:
    metadata = record.get("metadata")
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise ValueError(f"Corpus record at index {index} has non-object metadata.")

    pmid = _clean_optional_text(record.get("pmid"))
    document_id = _clean_optional_text(record.get("document_id")) or (f"PMID:{pmid}" if pmid else f"CORPUS:{index}")
    return Document(
        document_id=document_id,
        pmid=pmid,
        title=_clean_optional_text(record.get("title")) or "",
        abstract=_clean_optional_text(record.get("abstract")) or "",
        full_text=_clean_optional_text(record.get("full_text")),
        source=_clean_optional_text(record.get("source")) or "corpus",
        year=_clean_optional_text(record.get("year")),
        metadata=metadata,
    )
