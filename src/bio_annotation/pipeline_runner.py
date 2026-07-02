from __future__ import annotations

import ast
import csv
import json
import logging
from datetime import datetime
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Callable

from bio_annotation.annotators.aioner import annotate_with_aioner
from bio_annotation.annotators.bern2 import annotate_with_bern2
from bio_annotation.annotators.flair import annotate_with_flair
from bio_annotation.annotators.medcat import annotate_with_medcat
from bio_annotation.annotators.pubtator3 import annotate_with_pubtator3
from bio_annotation.entity_types import normalize_entity_type
from bio_annotation.pipeline_config import PipelineConfig, load_pipeline_config
from bio_annotation.report import write_html_report
from bio_annotation.preprocessing.document_loader import (
    load_documents_from_config,
    load_documents_from_pmid_file,
    load_documents_from_pmids,
    resolve_input_description,
    summarize_ingestion,
)
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation

SUPPORTED_ANNOTATORS = {"bern2", "flair", "pubtator3", "aioner", "medcat"}
FLAIR_INSTALL_HINT = (
    "The Flair annotator requires the optional Flair dependency. "
    "Install it with: uv sync --extra flair"
)
logger = logging.getLogger(__name__)


def run_pipeline_from_config(
    config_path: Path,
    *,
    orchestrator_factory: Callable[[], Any] | None = None,
    pmid_fetcher: Callable[[str], dict[str, Any]] | None = None,
    bern2_request_fn: Callable[[Document], Any] | None = None,
    pubtator3_request_fn: Callable[[Document], Any] | None = None,
    flair_spans_by_document: dict[str, list[Any]] | None = None,
    aioner_request_fn: Callable[[Document], Any] | None = None,
    medcat_request_fn: Callable[[Document], Any] | None = None,
) -> dict[str, Any]:
    config = load_pipeline_config(config_path)
    validate_optional_annotator_dependencies(
        config,
        flair_spans_by_document=flair_spans_by_document,
    )
    if pmid_fetcher is not None and config.input_mode == "pmids":
        documents = load_documents_from_pmids(
            config.pmids,
            fetcher=pmid_fetcher,
            enrichment_sources=config.enrichment_sources,
        )
    elif pmid_fetcher is not None and config.input_mode == "pmid_file":
        if config.pmid_file is None:
            raise ValueError("input.pmid_file must be set when input.mode = 'pmid_file'.")
        documents = load_documents_from_pmid_file(
            config.pmid_file,
            fetcher=pmid_fetcher,
            enrichment_sources=config.enrichment_sources,
        )
    else:
        documents = load_documents_from_config(
            config,
            orchestrator_factory=orchestrator_factory,
        )
    payload = build_pipeline_output(
        documents,
        config,
        bern2_request_fn=bern2_request_fn,
        pubtator3_request_fn=pubtator3_request_fn,
        flair_spans_by_document=flair_spans_by_document,
        aioner_request_fn=aioner_request_fn,
        medcat_request_fn=medcat_request_fn,
    )
    if config.output_path is not None:
        actual_output_path = timestamped_output_path(config.output_path)
        payload["output"] = {
            "configured_path": config.output_path.as_posix(),
            "path": actual_output_path.as_posix(),
            "run_dir": actual_output_path.parent.as_posix(),
        }
        write_pipeline_output(payload, actual_output_path)
    return payload


def build_pipeline_output(
    documents: list[Document],
    config: PipelineConfig,
    *,
    bern2_request_fn: Callable[[Document], Any] | None = None,
    pubtator3_request_fn: Callable[[Document], Any] | None = None,
    flair_spans_by_document: dict[str, list[Any]] | None = None,
    aioner_request_fn: Callable[[Document], Any] | None = None,
    medcat_request_fn: Callable[[Document], Any] | None = None,
) -> dict[str, Any]:
    enabled_annotators = list(config.annotators)
    annotator_settings = dict(config.annotator_settings)
    _validate_annotators(enabled_annotators)
    input_description = resolve_input_description(config)
    corpus_documents = [document_to_dict(document) for document in documents]
    bern2_options = _read_bern2_options(annotator_settings.get("bern2", {}))
    pubtator3_options = _read_pubtator3_options(annotator_settings.get("pubtator3", {}))
    flair_options = _read_flair_options(annotator_settings.get("flair", {}))
    aioner_options = _read_aioner_options(annotator_settings.get("aioner", {}))
    medcat_options = _read_medcat_options(annotator_settings.get("medcat", {}))

    flair_tagger = None
    if "flair" in enabled_annotators and flair_spans_by_document is None:
        try:
            flair_tagger = _load_flair_tagger(flair_options["model"] or "hunflair2")
        except Exception as exc:
            logger.warning("flair unavailable: %s", exc)
    document_annotations: list[dict[str, Any]] = []
    annotations_output: list[dict[str, Any]] = []
    keyword_output: list[dict[str, Any]] = []
    annotation_summary = {
        "annotators_enabled": enabled_annotators,
        "document_count": len(documents),
        "annotation_count": 0,
        "keyword_count": 0,
    }

    all_statuses: list[dict[str, Any]] = []

    for document in documents:
        results, statuses = run_selected_annotators_with_status(
            document,
            enabled_annotators,
            bern2_request_fn=bern2_request_fn,
            pubtator3_request_fn=pubtator3_request_fn,
            aioner_request_fn=aioner_request_fn,
            medcat_request_fn=medcat_request_fn,
            bern2_options=bern2_options,
            pubtator3_options=pubtator3_options,
            aioner_options=aioner_options,
            medcat_options=medcat_options,
            flair_spans=(
                flair_spans_by_document.get(document.document_id)
                if flair_spans_by_document is not None
                else None
            ),
            flair_tagger=flair_tagger,
        )
        all_statuses.extend(statuses)

        annotations = flatten_annotations(results)
        annotations = filter_annotations_by_type(annotations, config.entity_types)
        annotation_summary["annotation_count"] += len(annotations)
        document_keywords = build_keyword_annotations(document.document_id, annotations)
        annotation_summary["keyword_count"] += len(document_keywords)
        keyword_output.extend(document_keywords)
        if enabled_annotators:
            document_annotations.append(
                {
                    "document_id": document.document_id,
                    "sources": sorted(results),
                    "annotators": statuses,
                    "annotation_count": len(annotations),
                    "annotation_ids": [
                        annotation.annotation_id for annotation in annotations
                    ],
                }
            )
        annotations_output.extend(
            {
                "document_id": document.document_id,
                **annotation.to_dict(),
            }
            for annotation in annotations
        )

    return {
        "stage": "corpus",
        "input": input_description,
        "pipeline": {
            "mode": "ingestion_only" if not enabled_annotators else "ingestion_and_annotation",
            "annotators_enabled": enabled_annotators,
            "annotator_settings": {name: annotator_settings.get(name, {}) for name in enabled_annotators},
        },
        "document_count": len(corpus_documents),
        "corpus_summary": summarize_ingestion(documents),
        "entity_types": config.entity_types,
        "documents": corpus_documents,
        "annotation_summary": annotation_summary,
        "annotator_summary": _build_annotator_summary(
            enabled_annotators,
            all_statuses,
        ),
        "document_annotations": document_annotations,
        "keywords": keyword_output,
        "annotations": annotations_output,
    }


def write_pipeline_output(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_pipeline_tsv_outputs(payload, output_path)
    write_html_report(payload, output_path.with_suffix(".html"))


def timestamped_output_path(output_path: Path, *, now: datetime | None = None) -> Path:
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return output_path.parent / stamp / output_path.name


def write_pipeline_tsv_outputs(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    write_keywords_tsv(
        payload,
        output_path.with_name(f"{output_path.stem}.keywords.tsv"),
    )
    write_keyword_annotator_evidence_tsv(
        payload,
        output_path.with_name(f"{output_path.stem}.keyword_annotator_evidence.tsv"),
    )
    write_annotations_tsv(
        payload,
        output_path.with_name(f"{output_path.stem}.annotations.tsv"),
    )


def write_keywords_tsv(payload: dict[str, Any], output_path: Path) -> None:
    documents = _documents_by_id(payload)
    annotations = _annotations_by_id(payload)
    rows: list[dict[str, Any]] = []

    for keyword in payload.get("keywords", []):
        if not isinstance(keyword, dict):
            continue

        document_id = str(keyword.get("document_id") or "")
        document = documents.get(document_id, {})
        keyword_annotations = _resolve_annotations(
            annotations,
            keyword.get("annotation_ids"),
        )

        first_mention = _first_mention(keyword)
        rows.append(
            {
                "document_id": document_id,
                "pmid": document.get("pmid"),
                "title": document.get("title"),
                "keyword": keyword.get("keyword"),
                "start": first_mention.get("start"),
                "end": first_mention.get("end"),
                "annotation_count": keyword.get("annotation_count"),
                "annotator_count": keyword.get("annotator_count"),
                "labels": _join_values(keyword.get("labels")),
                "canonical_ids": _join_values(keyword.get("canonical_ids")),
                "sources": _join_values(
                    sorted(
                        {
                            annotation.get("source")
                            for annotation in keyword_annotations
                            if annotation.get("source")
                        }
                    )
                ),
            }
        )

    _write_tsv(
        output_path,
        [
            "document_id",
            "pmid",
            "title",
            "keyword",
            "start",
            "end",
            "annotation_count",
            "annotator_count",
            "labels",
            "canonical_ids",
            "sources",
        ],
        rows,
    )


def write_keyword_annotator_evidence_tsv(
    payload: dict[str, Any],
    output_path: Path,
) -> None:
    documents = _documents_by_id(payload)
    annotations = _annotations_by_id(payload)
    rows: list[dict[str, Any]] = []

    for keyword in payload.get("keywords", []):
        if not isinstance(keyword, dict):
            continue

        document_id = str(keyword.get("document_id") or "")
        document = documents.get(document_id, {})

        for mention in keyword.get("mentions", []):
            if not isinstance(mention, dict):
                continue
            for annotation in _resolve_annotations(
                annotations,
                mention.get("annotation_ids"),
            ):

                rows.append(
                    {
                        "document_id": document_id,
                        "pmid": document.get("pmid"),
                        "title": document.get("title"),
                        "keyword": keyword.get("keyword"),
                        "start": mention.get("start"),
                        "end": mention.get("end"),
                        "source": annotation.get("source"),
                        "label": annotation.get("entity_type"),
                        "annotation_id": annotation.get("annotation_id"),
                        "canonical_id": _join_values(annotation.get("canonical_id")),
                        "canonical_name": annotation.get("canonical_name"),
                        "confidence": annotation.get("confidence"),
                    }
                )

    _write_tsv(
        output_path,
        [
            "document_id",
            "pmid",
            "title",
            "keyword",
            "start",
            "end",
            "source",
            "label",
            "annotation_id",
            "canonical_id",
            "canonical_name",
            "confidence",
        ],
        rows,
    )


def write_annotations_tsv(payload: dict[str, Any], output_path: Path) -> None:
    documents = _documents_by_id(payload)
    rows: list[dict[str, Any]] = []

    for annotation in payload.get("annotations", []):
        if not isinstance(annotation, dict):
            continue

        document_id = str(annotation.get("document_id") or "")
        document = documents.get(document_id, {})

        rows.append(
            {
                "document_id": document_id,
                "pmid": document.get("pmid"),
                "title": document.get("title"),
                "source": annotation.get("source"),
                "span_text": annotation.get("span_text"),
                "start": annotation.get("start"),
                "end": annotation.get("end"),
                "entity_type": annotation.get("entity_type"),
                "annotation_id": annotation.get("annotation_id"),
                "canonical_id": _join_values(annotation.get("canonical_id")),
                "canonical_name": annotation.get("canonical_name"),
                "confidence": annotation.get("confidence"),
            }
        )

    _write_tsv(
        output_path,
        [
            "document_id",
            "pmid",
            "title",
            "source",
            "span_text",
            "start",
            "end",
            "entity_type",
            "annotation_id",
            "canonical_id",
            "canonical_name",
            "confidence",
        ],
        rows,
    )


def run_selected_annotators(
    document: Document,
    annotators: list[str],
    *,
    bern2_request_fn: Callable[[Document], Any] | None = None,
    pubtator3_request_fn: Callable[[Document], Any] | None = None,
    aioner_request_fn: Callable[[Document], Any] | None = None,
    medcat_request_fn: Callable[[Document], Any] | None = None,
    bern2_options: dict[str, Any] | None = None,
    pubtator3_options: dict[str, Any] | None = None,
    aioner_options: dict[str, Any] | None = None,
    medcat_options: dict[str, Any] | None = None,
    flair_spans: list[Any] | None = None,
    flair_tagger: Any = None,
    flair_options: dict[str, Any] | None = None,
) -> dict[str, list[Annotation]]:
    results, _ = run_selected_annotators_with_status(
        document,
        annotators,
        bern2_request_fn=bern2_request_fn,
        pubtator3_request_fn=pubtator3_request_fn,
        aioner_request_fn=aioner_request_fn,
        medcat_request_fn=medcat_request_fn,
        bern2_options=bern2_options,
        pubtator3_options=pubtator3_options,
        aioner_options=aioner_options,
        medcat_options=medcat_options,
        flair_spans=flair_spans,
        flair_tagger=flair_tagger,
        flair_options=flair_options,
    )
    return results


def run_selected_annotators_with_status(
    document: Document,
    annotators: list[str],
    *,
    bern2_request_fn: Callable[[Document], Any] | None = None,
    pubtator3_request_fn: Callable[[Document], Any] | None = None,
    aioner_request_fn: Callable[[Document], Any] | None = None,
    medcat_request_fn: Callable[[Document], Any] | None = None,
    bern2_options: dict[str, Any] | None = None,
    pubtator3_options: dict[str, Any] | None = None,
    aioner_options: dict[str, Any] | None = None,
    medcat_options: dict[str, Any] | None = None,
    flair_spans: list[Any] | None = None,
    flair_tagger: Any = None,
    flair_options: dict[str, Any] | None = None,
) -> tuple[dict[str, list[Annotation]], list[dict[str, Any]]]:
    results: dict[str, list[Annotation]] = {}
    statuses: list[dict[str, Any]] = []

    for annotator in annotators:
        try:
            if annotator == "bern2":
                results[annotator] = annotate_with_bern2(
                    document,
                    request_fn=bern2_request_fn,
                    endpoint=(
                        bern2_options.get("endpoint")
                        if bern2_options
                        else None
                    ),
                )
            elif annotator == "flair":
                results[annotator] = annotate_with_flair(
                    document,
                    spans=flair_spans,
                    tagger=flair_tagger,
                    model=flair_options.get("model") if flair_options else None,
                )
            elif annotator == "pubtator3":
                results[annotator] = annotate_with_pubtator3(
                    document,
                    request_fn=pubtator3_request_fn,
                    endpoint=pubtator3_options.get("endpoint")
                    if pubtator3_options
                    else None,
                    timeout=pubtator3_options.get("timeout", 60)
                    if pubtator3_options
                    else 60,
                    format=pubtator3_options.get("format", "biocjson")
                    if pubtator3_options
                    else "biocjson",
                    mode=pubtator3_options.get("mode", "auto")
                    if pubtator3_options
                    else "auto",
                    bioconcept=pubtator3_options.get("bioconcept", "All")
                    if pubtator3_options
                    else "All",
                    poll_interval_seconds=pubtator3_options.get(
                        "poll_interval_seconds",
                        2.0,
                    )
                    if pubtator3_options
                    else 2.0,
                    poll_backoff=pubtator3_options.get("poll_backoff", 1.5)
                    if pubtator3_options
                    else 1.5,
                    max_poll_interval_seconds=(
                        pubtator3_options.get(
                            "max_poll_interval_seconds",
                            15.0,
                        )
                        if pubtator3_options
                        else 15.0
                    ),
                    max_poll_attempts=pubtator3_options.get("max_poll_attempts", 15)
                    if pubtator3_options
                    else 15,
                    max_poll_seconds=pubtator3_options.get("max_poll_seconds", 180.0)
                    if pubtator3_options
                    else 180.0,
                    progress_callback=_pubtator3_progress,
                )
            elif annotator == "aioner":
                results[annotator] = annotate_with_aioner(
                    document,
                    request_fn=aioner_request_fn,
                    repo=aioner_options.get("repo") if aioner_options else None,
                    model=aioner_options.get("model") if aioner_options else None,
                    vocab=aioner_options.get("vocab") if aioner_options else None,
                    entity=aioner_options.get("entity", "ALL")
                    if aioner_options
                    else "ALL",
                    project=aioner_options.get("project", "tools/aioner")
                    if aioner_options
                    else "tools/aioner",
                    python=aioner_options.get("python") if aioner_options else None,
                    timeout=aioner_options.get("timeout", 600)
                    if aioner_options
                    else 600,
                )
            elif annotator == "medcat":
                results[annotator] = annotate_with_medcat(
                    document,
                    request_fn=medcat_request_fn,
                    endpoint=medcat_options.get("endpoint") if medcat_options else None,
                    min_acc=medcat_options.get("min_acc") if medcat_options else None,
                )
            else:
                raise ValueError(f"Unsupported annotator: {annotator}")
        except Exception as exc:
            logger.warning("%s unavailable: %s", annotator, exc)
            results[annotator] = []
            statuses.append(
                {
                    "name": annotator,
                    "status": "failed",
                    "annotation_count": 0,
                    "reason": str(exc),
                }
            )
            continue

        annotation_count = len(results[annotator])
        if annotation_count:
            status = "produced_annotations"
            reason = None
        else:
            status = "no_annotations"
            reason = _no_annotations_reason(annotator)
        statuses.append(
            {
                "name": annotator,
                "status": status,
                "annotation_count": annotation_count,
                "reason": reason,
            }
        )

    return results, statuses


def flatten_annotations(results: dict[str, list[Annotation]]) -> list[Annotation]:
    annotations: list[Annotation] = []
    for source in ("bern2", "flair", "pubtator3", "aioner", "medcat"):
        annotations.extend(results.get(source, []))
    return annotations


def build_keyword_annotations(
    document_id: str,
    annotations: list[Annotation],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}

    for annotation in annotations:
        keyword = annotation.span_text.strip()
        if not keyword:
            continue

        normalized = keyword.casefold()
        key = (document_id, normalized)

        if key not in groups:
            groups[key] = {
                "document_id": document_id,
                "keyword": keyword,
                "normalized_keyword": normalized,
                "variants": [],
                "mention_count": 0,
                "annotation_count": 0,
                "annotator_count": 0,
                "labels": [],
                "canonical_ids": [],
                "mentions": [],
                "annotation_ids": [],
            }

        group = groups[key]
        group["annotation_count"] += 1
        group["annotation_ids"].append(annotation.annotation_id)
        if keyword not in group["variants"]:
            group["variants"].append(keyword)

        mention_key = (annotation.start, annotation.end)
        mention = next(
            (
                item
                for item in group["mentions"]
                if (item["start"], item["end"]) == mention_key
            ),
            None,
        )
        if mention is None:
            mention = {
                "text": keyword,
                "start": annotation.start,
                "end": annotation.end,
                "annotation_count": 0,
                "annotator_count": 0,
                "annotation_ids": [],
            }
            group["mentions"].append(mention)
        mention["annotation_count"] += 1
        mention["annotation_ids"].append(annotation.annotation_id)

    for group in groups.values():
        annotations_by_id = {
            annotation.annotation_id: annotation
            for annotation in annotations
            if annotation.annotation_id in set(group["annotation_ids"])
        }
        group["variants"] = sorted(group["variants"])
        group["annotation_ids"] = sorted(group["annotation_ids"])
        group["mention_count"] = len(group["mentions"])
        group["mentions"] = [
            _finalize_mention(item, annotations_by_id) for item in group["mentions"]
        ]
        group["mentions"] = sorted(
            group["mentions"],
            key=lambda item: (
                item["start"] is None,
                item["start"] if item["start"] is not None else -1,
                item["end"] is None,
                item["end"] if item["end"] is not None else -1,
                item["text"].casefold(),
            ),
        )
        group["annotator_count"] = len(
            {
                annotation.source
                for annotation in annotations_by_id.values()
            }
        )
        group["labels"] = sorted(
            {
                annotation.entity_type
                for annotation in annotations_by_id.values()
                if annotation.entity_type is not None
            }
        )
        group["canonical_ids"] = sorted(
            {
                canonical_id
                for annotation in annotations_by_id.values()
                for canonical_id in _flatten_values(
                    _normalize_scalar_id(annotation.canonical_id)
                )
                if canonical_id
            }
        )

    return sorted(
        groups.values(),
        key=lambda item: (
            item["document_id"],
            item["mentions"][0]["start"] is None,
            item["mentions"][0]["start"] if item["mentions"][0]["start"] is not None else -1,
            item["mentions"][0]["end"] is None,
            item["mentions"][0]["end"] if item["mentions"][0]["end"] is not None else -1,
            item["keyword"].casefold(),
        ),
    )


def filter_annotations_by_type(
    annotations: list[Annotation],
    entity_types: list[str],
) -> list[Annotation]:
    if not entity_types:
        return annotations
    allowed = {normalize_entity_type(entity_type) for entity_type in entity_types}
    return [
        annotation
        for annotation in annotations
        if normalize_entity_type(annotation.entity_type) in allowed
    ]


def document_to_dict(document: Document) -> dict[str, Any]:
    return {
        "document_id": document.document_id,
        "pmid": document.pmid,
        "title": document.title,
        "abstract": document.abstract,
        "full_text": document.full_text,
        "source": document.source,
        "year": document.year,
        "metadata": document.metadata,
    }


def _build_annotator_summary(
    configured: list[str],
    statuses: list[dict[str, Any]],
) -> dict[str, Any]:
    produced = sorted(
        {
            str(status["name"])
            for status in statuses
            if status.get("status") == "produced_annotations"
        }
    )
    failed = sorted(
        {
            str(status["name"])
            for status in statuses
            if status.get("status") == "failed"
        }
    )
    not_produced = [
        name
        for name in configured
        if name not in produced and name not in failed
    ]
    return {
        "configured": configured,
        "produced": produced,
        "not_produced": not_produced,
        "failed": failed,
        "annotators": statuses,
    }


def _no_annotations_reason(annotator: str) -> str:
    if annotator == "bern2":
        return (
            "No annotations returned. Verify the Bern2 service is reachable "
            "and returned entities for this document."
        )
    if annotator == "flair":
        return (
            "No annotations returned. The Flair model may be unavailable/not "
            "cached, or it found no entities."
        )
    if annotator == "pubtator3":
        return (
            "No annotations returned. Verify PubTator3 is reachable and "
            "returned entities for this document."
        )
    if annotator == "aioner":
        return (
            "No annotations returned. Ensure AIONER is installed "
            "(tools/aioner/setup.sh) and annotators.aioner.repo/model are set, "
            "or it found no entities."
        )
    if annotator == "medcat":
        return (
            "No annotations returned. Verify the MedCAT service is reachable "
            "(set annotators.medcat.endpoint or MEDCAT_API_URL) and returned "
            "entities for this document."
        )
    return "No annotations returned."


def _pubtator3_progress(
    session_id: str,
    attempt: int,
    max_attempts: int,
    sleep_seconds: float,
) -> None:
    logger.info(
        "pubtator3 pending: "
        "session=%s attempt=%s/%s; sleeping %.1fs",
        session_id,
        attempt,
        max_attempts,
        sleep_seconds,
    )


def _finalize_mention(
    mention: dict[str, Any],
    annotations_by_id: dict[str, Annotation],
) -> dict[str, Any]:
    mention["annotation_ids"] = sorted(mention["annotation_ids"])
    mention["annotator_count"] = len(
        {
            annotation.source
            for annotation_id in mention["annotation_ids"]
            if (annotation := annotations_by_id.get(annotation_id)) is not None
        }
    )
    return mention


def _documents_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    for document in payload.get("documents", []):
        if not isinstance(document, dict):
            continue
        document_id = document.get("document_id")
        if document_id is not None:
            documents[str(document_id)] = document
    return documents


def _annotations_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    annotations: dict[str, dict[str, Any]] = {}
    for annotation in payload.get("annotations", []):
        if not isinstance(annotation, dict):
            continue
        annotation_id = annotation.get("annotation_id")
        if annotation_id is not None:
            annotations[str(annotation_id)] = annotation
    return annotations


def _resolve_annotations(
    annotations: dict[str, dict[str, Any]],
    annotation_ids: object,
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for annotation_id in _flatten_values(annotation_ids):
        annotation = annotations.get(str(annotation_id))
        if annotation is not None:
            resolved.append(annotation)
    return resolved


def _first_mention(keyword: dict[str, Any]) -> dict[str, Any]:
    mentions = keyword.get("mentions")
    if isinstance(mentions, list):
        for mention in mentions:
            if isinstance(mention, dict):
                return mention
    return {}


def _normalize_scalar_id(value: object) -> object:
    flattened = [_normalize_identifier_text(item) for item in _flatten_values(value)]
    if not flattened:
        return None
    if len(flattened) == 1:
        return flattened[0]
    return flattened


def _flatten_values(values: object) -> list[object]:
    if values is None:
        return []
    if isinstance(values, list | tuple | set):
        flattened: list[object] = []
        for value in values:
            flattened.extend(_flatten_values(value))
        return flattened
    if isinstance(values, str):
        parsed = _parse_stringified_list(values)
        if parsed is not None:
            return _flatten_values(parsed)
    return [values]


def _normalize_identifier_text(value: object) -> object:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if stripped.lower().startswith("mesh:"):
        return f"MESH:{stripped.split(':', 1)[1]}"
    return stripped


def _parse_stringified_list(value: str) -> object | None:
    stripped = value.strip()
    if not stripped.startswith("[") or not stripped.endswith("]"):
        return None
    try:
        parsed = ast.literal_eval(stripped)
    except (SyntaxError, ValueError):
        return None
    return parsed if isinstance(parsed, list | tuple | set) else None


def _join_values(values: object) -> str:
    if values is None:
        return ""
    return "|".join(
        str(_normalize_identifier_text(value))
        for value in _flatten_values(values)
        if value is not None
    )


def _write_tsv(
    output_path: Path,
    fieldnames: list[str],
    rows: list[dict[str, Any]],
) -> None:
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def _validate_annotators(annotators: list[str]) -> None:
    unsupported = [annotator for annotator in annotators if annotator not in SUPPORTED_ANNOTATORS]
    if unsupported:
        raise ValueError(f"Unsupported annotators requested: {', '.join(unsupported)}")


def validate_optional_annotator_dependencies(
    config: PipelineConfig,
    *,
    flair_spans_by_document: dict[str, list[Any]] | None = None,
) -> None:
    if "flair" not in config.annotators:
        return
    if flair_spans_by_document is not None:
        return
    if find_spec("flair") is None:
        raise ValueError(FLAIR_INSTALL_HINT)


def _read_bern2_options(settings: dict[str, object]) -> dict[str, Any]:
    endpoint = settings.get("endpoint")
    base_url = settings.get("base_url")

    cleaned_endpoint = None
    if isinstance(endpoint, str) and endpoint.strip():
        cleaned_endpoint = endpoint.strip()
    elif isinstance(base_url, str) and base_url.strip():
        cleaned_endpoint = base_url.strip()

    return {
        "endpoint": cleaned_endpoint,
    }


def _read_medcat_options(settings: dict[str, object]) -> dict[str, Any]:
    endpoint = settings.get("endpoint")
    base_url = settings.get("base_url")

    cleaned_endpoint = None
    if isinstance(endpoint, str) and endpoint.strip():
        cleaned_endpoint = endpoint.strip()
    elif isinstance(base_url, str) and base_url.strip():
        cleaned_endpoint = base_url.strip()

    min_acc_raw = settings.get("min_acc")
    min_acc = None
    if isinstance(min_acc_raw, (int, float)) and float(min_acc_raw) > 0.0:
        min_acc = float(min_acc_raw)

    return {
        "endpoint": cleaned_endpoint,
        "min_acc": min_acc,
    }


def _read_flair_options(settings: dict[str, object]) -> dict[str, Any]:
    model = settings.get("model")
    return {
        "model": model.strip()
        if isinstance(model, str) and model.strip()
        else None,
    }


def _read_aioner_options(settings: dict[str, object]) -> dict[str, Any]:
    def _clean_str(key: str, default: str | None = None) -> str | None:
        value = settings.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return default

    timeout = settings.get("timeout")
    return {
        "repo": _clean_str("repo"),
        "model": _clean_str("model"),
        "vocab": _clean_str("vocab"),
        "entity": _clean_str("entity", "ALL"),
        "project": _clean_str("project", "tools/aioner"),
        "python": _clean_str("python"),
        "timeout": int(timeout) if isinstance(timeout, int) and timeout > 0 else 600,
    }


def _load_flair_tagger(model: str) -> Any:
    try:
        import flair
        from flair.nn import Classifier
    except ImportError as exc:
        raise RuntimeError(FLAIR_INSTALL_HINT) from exc

    flair.logger.setLevel(logging.WARNING)
    return Classifier.load(model)


def _read_pubtator3_options(settings: dict[str, object]) -> dict[str, Any]:
    endpoint = settings.get("endpoint")
    timeout = settings.get("timeout")
    export_format = settings.get("format")
    mode = settings.get("mode")
    bioconcept = settings.get("bioconcept")
    poll_interval_seconds = settings.get("poll_interval_seconds")
    poll_backoff = settings.get("poll_backoff")
    max_poll_interval_seconds = settings.get("max_poll_interval_seconds")
    max_poll_attempts = settings.get("max_poll_attempts")
    max_poll_seconds = settings.get("max_poll_seconds")

    cleaned_mode = mode.strip().lower() if isinstance(mode, str) and mode.strip() else "auto"
    if cleaned_mode not in {"auto", "publication_only", "text_only"}:
        raise ValueError(
            "annotators.pubtator3.mode must be one of: "
            "'auto', 'publication_only', 'text_only'."
        )

    return {
        "endpoint": endpoint if isinstance(endpoint, str) and endpoint.strip() else None,
        "timeout": timeout if isinstance(timeout, int) and timeout > 0 else 60,
        "format": export_format if isinstance(export_format, str) and export_format.strip() else "biocjson",
        "mode": cleaned_mode,
        "bioconcept": bioconcept if isinstance(bioconcept, str) and bioconcept.strip() else "All",
        "poll_interval_seconds": (
            float(poll_interval_seconds)
            if isinstance(poll_interval_seconds, (int, float)) and poll_interval_seconds > 0
            else 2.0
        ),
        "poll_backoff": (
            float(poll_backoff)
            if isinstance(poll_backoff, (int, float)) and float(poll_backoff) >= 1.0
            else 1.5
        ),
        "max_poll_interval_seconds": (
            float(max_poll_interval_seconds)
            if isinstance(max_poll_interval_seconds, (int, float)) and float(max_poll_interval_seconds) > 0
            else 15.0
        ),
        "max_poll_attempts": (
            int(max_poll_attempts)
            if isinstance(max_poll_attempts, int) and max_poll_attempts > 0
            else 15
        ),
        "max_poll_seconds": (
            float(max_poll_seconds)
            if isinstance(max_poll_seconds, (int, float)) and float(max_poll_seconds) > 0
            else 180.0
        ),
    }
