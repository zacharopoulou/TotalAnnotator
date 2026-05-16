from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Callable

from bio_annotation.benchmarking.config import (
    DEFAULT_BENCHMARK_ANNOTATORS,
    benchmark_annotator_options,
)
from bio_annotation.benchmarking.errors import build_error_analysis
from bio_annotation.benchmarking.metrics import ScoredPrediction, evaluate_annotator
from bio_annotation.benchmarking.ncbi import BenchmarkCase, GoldAnnotation, load_ncbi_cases
from bio_annotation.benchmarking.preflight import (
    preflight_benchmark_annotators,
)
from bio_annotation.pipeline_runner import run_selected_annotators_with_status
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation

RequestFn = Callable[[Document], Any]
ProgressCallback = Callable[[int, int, str], None]


def run_ncbi_review_evaluation(
    *,
    benchmark_path: str | Path | None = None,
    split: str = "test",
    annotators: list[str] | None = None,
    output_dir: str | Path | None = None,
    entity_type: str = "disease",
    bern2_request_fn: RequestFn | None = None,
    pubtator3_request_fn: RequestFn | None = None,
    bern2_options: dict[str, Any] | None = None,
    pubtator3_options: dict[str, Any] | None = None,
    flair_options: dict[str, Any] | None = None,
    flair_tagger_loader: Callable[[str], Any] | None = None,
    progress_callback: ProgressCallback | None = None,
    progress_interval: int = 25,
) -> dict[str, Any]:
    """Run a standalone benchmark-review evaluation on NCBI Disease.

    This deliberately reuses the public annotator runner but keeps benchmark
    loading, matching, runtime defaults, preflight checks, and output generation
    outside the normal pipeline runner.
    """

    selected_annotators = annotators or list(DEFAULT_BENCHMARK_ANNOTATORS)
    runtime_options = benchmark_annotator_options(
        {
            "bern2": bern2_options or {},
            "pubtator3": pubtator3_options or {},
            "flair": flair_options or {},
        }
    )
    preflight_results, preflight_resources = preflight_benchmark_annotators(
        selected_annotators,
        runtime_options,
        flair_tagger_loader=flair_tagger_loader,
    )
    cases = load_ncbi_cases(benchmark_path, split=split)
    predictions_by_annotator: dict[str, list[dict[str, Any]]] = {
        annotator: [] for annotator in selected_annotators
    }
    prediction_objects: dict[str, list[ScoredPrediction]] = {
        annotator: [] for annotator in selected_annotators
    }
    gold_annotations = _flatten_gold(cases)
    statuses: list[dict[str, Any]] = []
    total_documents = len(cases)

    for index, case in enumerate(cases, start=1):
        results, case_statuses = run_selected_annotators_with_status(
            case.document,
            selected_annotators,
            bern2_request_fn=bern2_request_fn,
            pubtator3_request_fn=pubtator3_request_fn,
            bern2_options=runtime_options.get("bern2"),
            pubtator3_options=runtime_options.get("pubtator3"),
            flair_tagger=preflight_resources.get("flair_tagger"),
            flair_options=runtime_options.get("flair"),
        )
        for status in case_statuses:
            statuses.append({"document_id": case.document.document_id, **status})
        for annotator, annotations in results.items():
            prediction_objects.setdefault(annotator, []).extend(
                ScoredPrediction(
                    document_id=case.document.document_id,
                    annotation=annotation,
                )
                for annotation in annotations
            )
            predictions_by_annotator.setdefault(annotator, []).extend(
                _prediction_rows(case.document.document_id, annotator, annotations)
            )
        _emit_progress(
            progress_callback,
            index=index,
            total=total_documents,
            document_id=case.document.document_id,
            interval=progress_interval,
        )

    metric_rows = [
        evaluate_annotator(
            annotator=annotator,
            predictions=prediction_objects.get(annotator, []),
            gold_annotations=gold_annotations,
            entity_type=entity_type,
        ).to_dict()
        for annotator in selected_annotators
    ]
    error_analysis = _build_error_analysis_by_annotator(
        selected_annotators=selected_annotators,
        prediction_objects=prediction_objects,
        gold_annotations=gold_annotations,
        entity_type=entity_type,
    )

    payload: dict[str, Any] = {
        "benchmark": "ncbi_disease",
        "split": split,
        "entity_type": entity_type,
        "document_count": len(cases),
        "gold_count": len(gold_annotations),
        "annotators": selected_annotators,
        "annotator_options": {
            name: runtime_options.get(name, {}) for name in selected_annotators
        },
        "preflight": [result.to_dict() for result in preflight_results],
        "metrics": metric_rows,
        "error_analysis": error_analysis,
        "statuses": statuses,
        "warnings": _warning_rows(cases),
        "gold_annotations": [gold.to_dict() for gold in gold_annotations],
        "predictions": predictions_by_annotator,
    }

    if output_dir is not None:
        write_review_outputs(payload, Path(output_dir))
    return payload


def write_review_outputs(payload: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_metrics_tsv(payload, output_dir / "metrics_by_annotator.tsv")
    _write_error_analysis_tsv(payload, output_dir)
    _write_gold_jsonl(payload, output_dir / "gold.jsonl")
    _write_predictions_jsonl(payload, output_dir / "predictions.jsonl")
    _write_statuses_tsv(payload, output_dir / "annotator_statuses.tsv")
    _write_warnings_tsv(payload, output_dir / "loader_warnings.tsv")
    _write_preflight_tsv(payload, output_dir / "preflight.tsv")


def _flatten_gold(cases: list[BenchmarkCase]) -> list[GoldAnnotation]:
    gold: list[GoldAnnotation] = []
    for case in cases:
        gold.extend(case.gold_annotations)
    return gold


def _build_error_analysis_by_annotator(
    *,
    selected_annotators: list[str],
    prediction_objects: dict[str, list[ScoredPrediction]],
    gold_annotations: list[GoldAnnotation],
    entity_type: str,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    return {
        annotator: build_error_analysis(
            annotator=annotator,
            predictions=prediction_objects.get(annotator, []),
            gold_annotations=gold_annotations,
            entity_type=entity_type,
        ).to_dict()
        for annotator in selected_annotators
    }


def _emit_progress(
    callback: ProgressCallback | None,
    *,
    index: int,
    total: int,
    document_id: str,
    interval: int,
) -> None:
    if callback is None:
        return
    normalized_interval = max(1, interval)
    if index == 1 or index == total or index % normalized_interval == 0:
        callback(index, total, document_id)


def _prediction_rows(
    document_id: str,
    annotator: str,
    annotations: list[Annotation],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for annotation in annotations:
        row = annotation.to_dict()
        row["document_id"] = document_id
        row["annotator"] = annotator
        rows.append(row)
    return rows


def _warning_rows(cases: list[BenchmarkCase]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for case in cases:
        for warning in case.warnings:
            rows.append({"document_id": case.document.document_id, "warning": warning})
    return rows


def _write_metrics_tsv(payload: dict[str, Any], path: Path) -> None:
    rows: list[dict[str, Any]] = []
    for item in payload.get("metrics", []):
        if not isinstance(item, dict):
            continue
        strict = item.get("strict") if isinstance(item.get("strict"), dict) else {}
        lenient = item.get("lenient") if isinstance(item.get("lenient"), dict) else {}
        strict_norm = (
            item.get("strict_normalization")
            if isinstance(item.get("strict_normalization"), dict)
            else {}
        )
        lenient_norm = (
            item.get("lenient_normalization")
            if isinstance(item.get("lenient_normalization"), dict)
            else {}
        )
        rows.append(
            {
                "annotator": item.get("annotator"),
                "prediction_count": item.get("prediction_count"),
                "gold_count": item.get("gold_count"),
                "strict_tp": strict.get("true_positive"),
                "strict_fp": strict.get("false_positive"),
                "strict_fn": strict.get("false_negative"),
                "strict_precision": strict.get("precision"),
                "strict_recall": strict.get("recall"),
                "strict_f1": strict.get("f1"),
                "lenient_tp": lenient.get("true_positive"),
                "lenient_fp": lenient.get("false_positive"),
                "lenient_fn": lenient.get("false_negative"),
                "lenient_precision": lenient.get("precision"),
                "lenient_recall": lenient.get("recall"),
                "lenient_f1": lenient.get("f1"),
                "strict_norm_span_matches": strict_norm.get("span_matches"),
                "strict_norm_correct": strict_norm.get("correct"),
                "strict_norm_incorrect": strict_norm.get("incorrect"),
                "strict_norm_missing_prediction_id": strict_norm.get("missing_prediction_id"),
                "strict_norm_missing_gold_id": strict_norm.get("missing_gold_id"),
                "strict_norm_accuracy_on_matched_spans": strict_norm.get("accuracy_on_matched_spans"),
                "strict_norm_accuracy_on_comparable_gold_spans": strict_norm.get("accuracy_on_comparable_gold_spans"),
                "strict_norm_prediction_id_coverage_on_matched_spans": strict_norm.get("prediction_id_coverage_on_matched_spans"),
                "strict_norm_gold_id_coverage_on_matched_spans": strict_norm.get("gold_id_coverage_on_matched_spans"),
                "lenient_norm_span_matches": lenient_norm.get("span_matches"),
                "lenient_norm_correct": lenient_norm.get("correct"),
                "lenient_norm_incorrect": lenient_norm.get("incorrect"),
                "lenient_norm_missing_prediction_id": lenient_norm.get("missing_prediction_id"),
                "lenient_norm_missing_gold_id": lenient_norm.get("missing_gold_id"),
                "lenient_norm_accuracy_on_matched_spans": lenient_norm.get("accuracy_on_matched_spans"),
                "lenient_norm_accuracy_on_comparable_gold_spans": lenient_norm.get("accuracy_on_comparable_gold_spans"),
                "lenient_norm_prediction_id_coverage_on_matched_spans": lenient_norm.get("prediction_id_coverage_on_matched_spans"),
                "lenient_norm_gold_id_coverage_on_matched_spans": lenient_norm.get("gold_id_coverage_on_matched_spans"),
            }
        )
    _write_tsv(path, rows)


def _write_error_analysis_tsv(payload: dict[str, Any], output_dir: Path) -> None:
    error_analysis = payload.get("error_analysis")
    false_positives: list[dict[str, Any]] = []
    false_negatives: list[dict[str, Any]] = []
    boundary_errors: list[dict[str, Any]] = []
    if isinstance(error_analysis, dict):
        for item in error_analysis.values():
            if not isinstance(item, dict):
                continue
            false_positives.extend(
                row for row in item.get("false_positives", []) if isinstance(row, dict)
            )
            false_negatives.extend(
                row for row in item.get("false_negatives", []) if isinstance(row, dict)
            )
            boundary_errors.extend(
                row for row in item.get("boundary_errors", []) if isinstance(row, dict)
            )
    _write_tsv(output_dir / "false_positives.tsv", false_positives)
    _write_tsv(output_dir / "false_negatives.tsv", false_negatives)
    _write_tsv(output_dir / "boundary_errors.tsv", boundary_errors)


def _write_statuses_tsv(payload: dict[str, Any], path: Path) -> None:
    rows = [row for row in payload.get("statuses", []) if isinstance(row, dict)]
    _write_tsv(path, rows)


def _write_warnings_tsv(payload: dict[str, Any], path: Path) -> None:
    rows = [row for row in payload.get("warnings", []) if isinstance(row, dict)]
    _write_tsv(path, rows)


def _write_preflight_tsv(payload: dict[str, Any], path: Path) -> None:
    rows = [row for row in payload.get("preflight", []) if isinstance(row, dict)]
    _write_tsv(path, rows)


def _write_gold_jsonl(payload: dict[str, Any], path: Path) -> None:
    _write_jsonl(path, payload.get("gold_annotations", []))


def _write_predictions_jsonl(payload: dict[str, Any], path: Path) -> None:
    rows: list[dict[str, Any]] = []
    predictions = payload.get("predictions")
    if isinstance(predictions, dict):
        for annotator_rows in predictions.values():
            if isinstance(annotator_rows, list):
                rows.extend(row for row in annotator_rows if isinstance(row, dict))
    _write_jsonl(path, rows)


def _write_jsonl(path: Path, rows: Any) -> None:
    iterable = rows if isinstance(rows, list) else []
    with path.open("w", encoding="utf-8") as handle:
        for row in iterable:
            handle.write(json.dumps(row, ensure_ascii=False, default=str))
            handle.write("\n")


def _write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


__all__ = ["run_ncbi_review_evaluation", "write_review_outputs"]