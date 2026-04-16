from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from bio_annotation.entity_proposal.bern2_proposer import annotate_with_bern2
from bio_annotation.entity_proposal.flair_proposer import annotate_with_flair
from bio_annotation.entity_proposal.pubtator_proposer import annotate_with_pubtator
from bio_annotation.pipeline_config import PipelineConfig, load_pipeline_config
from bio_annotation.preprocessing.document_loader import load_documents_from_config, resolve_input_description
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation


SUPPORTED_ANNOTATORS = {"bern2", "flair", "pubtator"}


def run_pipeline_from_config(
    config_path: Path,
    *,
    pmid_fetcher: Callable[[str], dict[str, Any]] | None = None,
    bern2_request_fn: Callable[[Document], Any] | None = None,
    pubtator_request_fn: Callable[[Document], Any] | None = None,
    flair_spans_by_document: dict[str, list[Any]] | None = None,
) -> dict[str, Any]:
    config = load_pipeline_config(config_path)
    documents = load_documents_from_config(config, pmid_fetcher=pmid_fetcher)
    payload = build_pipeline_output(
        documents,
        config,
        bern2_request_fn=bern2_request_fn,
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
    pubtator_request_fn: Callable[[Document], Any] | None = None,
    flair_spans_by_document: dict[str, list[Any]] | None = None,
) -> dict[str, Any]:
    _validate_annotators(config.annotators)
    input_description = resolve_input_description(config)

    output_documents: list[dict[str, Any]] = []
    for document in documents:
        results = run_selected_annotators(
            document,
            config.annotators,
            bern2_request_fn=bern2_request_fn,
            pubtator_request_fn=pubtator_request_fn,
            flair_spans=(
                flair_spans_by_document.get(document.document_id)
                if flair_spans_by_document is not None
                else None
            ),
        )
        annotations = flatten_annotations(results)
        annotations = filter_annotations_by_type(annotations, config.entity_types)
        output_documents.append(
            {
                "document": document_to_dict(document),
                "sources": sorted(results),
                "annotation_count": len(annotations),
                "annotations": [annotation.to_dict() for annotation in annotations],
            }
        )

    return {
        "stage": "corpus",
        "input": input_description,
        "document_count": len(output_documents),
        "annotators": config.annotators,
        "entity_types": config.entity_types,
        "documents": output_documents,
    }


def write_pipeline_output(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_selected_annotators(
    document: Document,
    annotators: list[str],
    *,
    bern2_request_fn: Callable[[Document], Any] | None = None,
    pubtator_request_fn: Callable[[Document], Any] | None = None,
    flair_spans: list[Any] | None = None,
) -> dict[str, list[Annotation]]:
    results: dict[str, list[Annotation]] = {}

    for annotator in annotators:
        if annotator == "bern2":
            results[annotator] = annotate_with_bern2(document, request_fn=bern2_request_fn)
        elif annotator == "flair":
            results[annotator] = annotate_with_flair(document, spans=flair_spans)
        elif annotator == "pubtator":
            results[annotator] = annotate_with_pubtator(document, request_fn=pubtator_request_fn)
        else:
            raise ValueError(f"Unsupported annotator: {annotator}")

    return results


def flatten_annotations(results: dict[str, list[Annotation]]) -> list[Annotation]:
    annotations: list[Annotation] = []
    for source in ("bern2", "flair", "pubtator"):
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
