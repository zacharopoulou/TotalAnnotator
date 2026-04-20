from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from bio_annotation.annotators.bern2 import annotate_with_bern2
from bio_annotation.annotators.flair import annotate_with_flair
from bio_annotation.annotators.pubtator3 import annotate_with_pubtator3
from bio_annotation.pipeline_config import PipelineConfig, load_pipeline_config
from bio_annotation.preprocessing.document_loader import (
    load_documents_from_config,
    resolve_input_description,
    summarize_ingestion,
)
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation


SUPPORTED_ANNOTATORS = {"bern2", "flair", "pubtator", "pubtator3"}
ANNOTATOR_ALIASES = {"pubtator": "pubtator3"}


def run_pipeline_from_config(
    config_path: Path,
    *,
    pmid_fetcher: Callable[[str], dict[str, Any]] | None = None,
    bern2_request_fn: Callable[[Document], Any] | None = None,
    pubtator3_request_fn: Callable[[Document], Any] | None = None,
    pubtator_request_fn: Callable[[Document], Any] | None = None,
    flair_spans_by_document: dict[str, list[Any]] | None = None,
) -> dict[str, Any]:
    config = load_pipeline_config(config_path)
    documents = load_documents_from_config(config, pmid_fetcher=pmid_fetcher)
    payload = build_pipeline_output(
        documents,
        config,
        bern2_request_fn=bern2_request_fn,
        pubtator3_request_fn=pubtator3_request_fn,
        pubtator_request_fn=pubtator_request_fn,
        flair_spans_by_document=flair_spans_by_document,
    )
    if config.output_path is not None:
        write_pipeline_output(payload, config.output_path)
    return payload


def build_pipeline_output(
    documents: list[Document],
    config: PipelineConfig,
    *,
    bern2_request_fn: Callable[[Document], Any] | None = None,
    pubtator3_request_fn: Callable[[Document], Any] | None = None,
    pubtator_request_fn: Callable[[Document], Any] | None = None,
    flair_spans_by_document: dict[str, list[Any]] | None = None,
) -> dict[str, Any]:
    enabled_annotators = _canonicalize_annotators(config.annotators)
    annotator_settings = _canonicalize_annotator_settings(config.annotator_settings)
    _validate_annotators(enabled_annotators)
    input_description = resolve_input_description(config)
    corpus_documents = [document_to_dict(document) for document in documents]
    pubtator3_options = _read_pubtator3_options(annotator_settings.get("pubtator3", {}))

    document_annotations: list[dict[str, Any]] = []
    annotations_output: list[dict[str, Any]] = []
    annotation_summary = {
        "annotators_enabled": enabled_annotators,
        "document_count": len(documents),
        "annotation_count": 0,
    }
    for document in documents:
        results = run_selected_annotators(
            document,
            enabled_annotators,
            bern2_request_fn=bern2_request_fn,
            pubtator3_request_fn=pubtator3_request_fn,
            pubtator_request_fn=pubtator_request_fn,
            pubtator3_options=pubtator3_options,
            flair_spans=(
                flair_spans_by_document.get(document.document_id)
                if flair_spans_by_document is not None
                else None
            ),
        )
        annotations = flatten_annotations(results)
        annotations = filter_annotations_by_type(annotations, config.entity_types)
        annotation_summary["annotation_count"] += len(annotations)
        if enabled_annotators:
            document_annotations.append(
                {
                    "document_id": document.document_id,
                    "sources": sorted(results),
                    "annotation_count": len(annotations),
                    "annotations": [annotation.to_dict() for annotation in annotations],
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
        "document_annotations": document_annotations,
        "annotations": annotations_output,
    }


def write_pipeline_output(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_selected_annotators(
    document: Document,
    annotators: list[str],
    *,
    bern2_request_fn: Callable[[Document], Any] | None = None,
    pubtator3_request_fn: Callable[[Document], Any] | None = None,
    pubtator_request_fn: Callable[[Document], Any] | None = None,
    pubtator3_options: dict[str, Any] | None = None,
    flair_spans: list[Any] | None = None,
) -> dict[str, list[Annotation]]:
    results: dict[str, list[Annotation]] = {}

    for annotator in annotators:
        if annotator == "bern2":
            results[annotator] = annotate_with_bern2(document, request_fn=bern2_request_fn)
        elif annotator == "flair":
            results[annotator] = annotate_with_flair(document, spans=flair_spans)
        elif annotator == "pubtator3":
            results[annotator] = annotate_with_pubtator3(
                document,
                request_fn=pubtator3_request_fn if pubtator3_request_fn is not None else pubtator_request_fn,
                endpoint=pubtator3_options.get("endpoint") if pubtator3_options else None,
                timeout=pubtator3_options.get("timeout", 60) if pubtator3_options else 60,
                format=pubtator3_options.get("format", "biocjson") if pubtator3_options else "biocjson",
            )
        else:
            raise ValueError(f"Unsupported annotator: {annotator}")

    return results


def flatten_annotations(results: dict[str, list[Annotation]]) -> list[Annotation]:
    annotations: list[Annotation] = []
    for source in ("bern2", "flair", "pubtator3"):
        annotations.extend(results.get(source, []))
    return annotations


def filter_annotations_by_type(annotations: list[Annotation], entity_types: list[str]) -> list[Annotation]:
    if not entity_types:
        return annotations
    allowed = set(entity_types)
    return [annotation for annotation in annotations if annotation.entity_type in allowed]


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


def _validate_annotators(annotators: list[str]) -> None:
    unsupported = [annotator for annotator in annotators if annotator not in SUPPORTED_ANNOTATORS]
    if unsupported:
        raise ValueError(f"Unsupported annotators requested: {', '.join(unsupported)}")


def _canonicalize_annotators(annotators: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for annotator in annotators:
        canonical = ANNOTATOR_ALIASES.get(annotator, annotator)
        if canonical not in seen:
            seen.add(canonical)
            normalized.append(canonical)
    return normalized


def _canonicalize_annotator_settings(settings: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    normalized: dict[str, dict[str, object]] = {}
    for annotator, values in settings.items():
        canonical = ANNOTATOR_ALIASES.get(annotator, annotator)
        normalized[canonical] = dict(values)
    return normalized


def _read_pubtator3_options(settings: dict[str, object]) -> dict[str, Any]:
    endpoint = settings.get("endpoint")
    timeout = settings.get("timeout")
    export_format = settings.get("format")
    return {
        "endpoint": endpoint if isinstance(endpoint, str) and endpoint.strip() else None,
        "timeout": timeout if isinstance(timeout, int) and timeout > 0 else 60,
        "format": export_format if isinstance(export_format, str) and export_format.strip() else "biocjson",
    }
