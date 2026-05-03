from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from bio_annotation.annotators.bern2 import annotate_with_bern2
from bio_annotation.annotators.flair import annotate_with_flair
from bio_annotation.annotators.medcat import annotate_with_medcat
from bio_annotation.annotators.pubtator3 import annotate_with_pubtator3
from bio_annotation.pipeline_config import PipelineConfig, load_pipeline_config
from bio_annotation.preprocessing.document_loader import (
    load_documents_from_config,
    resolve_input_description,
    summarize_ingestion,
)
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation

SUPPORTED_ANNOTATORS = {"bern2", "flair", "pubtator3", "medcat"}


def run_pipeline_from_config(
    config_path: Path,
    *,
    pmid_fetcher: Callable[[str], dict[str, Any]] | None = None,
    bern2_request_fn: Callable[[Document], Any] | None = None,
    pubtator3_request_fn: Callable[[Document], Any] | None = None,
    medcat_request_fn: Callable[[Document], Any] | None = None,
    flair_spans_by_document: dict[str, list[Any]] | None = None,
    orchestrator_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    config = load_pipeline_config(config_path)
    documents = load_documents_from_config(
        config,
        pmid_fetcher=pmid_fetcher,
        orchestrator_factory=orchestrator_factory,
    )
    payload = build_pipeline_output(
        documents,
        config,
        bern2_request_fn=bern2_request_fn,
        pubtator3_request_fn=pubtator3_request_fn,
        medcat_request_fn=medcat_request_fn,
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
    medcat_request_fn: Callable[[Document], Any] | None = None,
    flair_spans_by_document: dict[str, list[Any]] | None = None,
) -> dict[str, Any]:
    enabled_annotators = list(config.annotators)
    annotator_settings = dict(config.annotator_settings)
    _validate_annotators(enabled_annotators)
    input_description = resolve_input_description(config)
    corpus_documents = [document_to_dict(document) for document in documents]
    pubtator3_options = _read_pubtator3_options(annotator_settings.get("pubtator3", {}))
    medcat_options = _read_medcat_options(annotator_settings.get("medcat", {}))
    flair_options = _read_flair_options(annotator_settings.get("flair", {}))

    flair_tagger = None
    if "flair" in enabled_annotators and flair_spans_by_document is None:
        flair_tagger = _load_flair_tagger(flair_options["model"])

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
            medcat_request_fn=medcat_request_fn,
            pubtator3_options=pubtator3_options,
            medcat_options=medcat_options,
            flair_spans=(
                flair_spans_by_document.get(document.document_id)
                if flair_spans_by_document is not None
                else None
            ),
            flair_tagger=flair_tagger,
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
    medcat_request_fn: Callable[[Document], Any] | None = None,
    pubtator3_options: dict[str, Any] | None = None,
    medcat_options: dict[str, Any] | None = None,
    flair_spans: list[Any] | None = None,
    flair_tagger: Any | None = None,
) -> dict[str, list[Annotation]]:
    results: dict[str, list[Annotation]] = {}

    for annotator in annotators:
        if annotator == "bern2":
            results[annotator] = annotate_with_bern2(document, request_fn=bern2_request_fn)
        elif annotator == "flair":
            results[annotator] = annotate_with_flair(
                document,
                spans=flair_spans,
                tagger=flair_tagger,
            )
        elif annotator == "pubtator3":
            results[annotator] = annotate_with_pubtator3(
                document,
                request_fn=pubtator3_request_fn,
                endpoint=pubtator3_options.get("endpoint") if pubtator3_options else None,
                timeout=pubtator3_options.get("timeout", 60) if pubtator3_options else 60,
                format=pubtator3_options.get("format", "biocjson") if pubtator3_options else "biocjson",
                mode=pubtator3_options.get("mode", "auto") if pubtator3_options else "auto",
                bioconcept=pubtator3_options.get("bioconcept", "All") if pubtator3_options else "All",
                poll_interval_seconds=pubtator3_options.get("poll_interval_seconds", 2.0)
                if pubtator3_options
                else 2.0,
                poll_backoff=pubtator3_options.get("poll_backoff", 1.5) if pubtator3_options else 1.5,
                max_poll_interval_seconds=(
                    pubtator3_options.get("max_poll_interval_seconds", 15.0)
                    if pubtator3_options
                    else 15.0
                ),
                max_poll_attempts=pubtator3_options.get("max_poll_attempts", 15)
                if pubtator3_options
                else 15,
            )
        elif annotator == "medcat":
            results[annotator] = annotate_with_medcat(
                document,
                request_fn=medcat_request_fn,
                endpoint=medcat_options.get("endpoint") if medcat_options else None,
            )
        else:
            raise ValueError(f"Unsupported annotator: {annotator}")

    return results


def flatten_annotations(results: dict[str, list[Annotation]]) -> list[Annotation]:
    annotations: list[Annotation] = []
    for source in ("bern2", "flair", "pubtator3", "medcat"):
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


def _read_flair_options(settings: dict[str, object]) -> dict[str, Any]:
    model = settings.get("model")
    return {
        "model": model.strip() if isinstance(model, str) and model.strip() else "hunflair2",
    }


def _load_flair_tagger(model: str) -> Any:
    from flair.nn import Classifier

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
    }


def _read_medcat_options(settings: dict[str, object]) -> dict[str, Any]:
    endpoint = settings.get("endpoint")
    return {
        "endpoint": endpoint if isinstance(endpoint, str) and endpoint.strip() else None,
    }
