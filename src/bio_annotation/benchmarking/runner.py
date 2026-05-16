from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Callable

from bio_annotation.benchmarking.config import (
    DEFAULT_BENCHMARK_ANNOTATORS,
    benchmark_annotator_options,
)
from bio_annotation.benchmarking.metrics import evaluate_annotator
from bio_annotation.benchmarking.ncbi import BenchmarkCase, GoldAnnotation, load_ncbi_cases
from bio_annotation.pipeline_runner import run_selected_annotators_with_status
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation

RequestFn = Callable[[Document], Any]


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
) -> dict[str, Any]:
    """Run a standalone benchmark-review evaluation on NCBI Disease.

    This deliberately reuses the public annotator runner but keeps benchmark
    loading, matching, runtime defaults, and output generation outside the
    normal pipeline runner.
    """

    selected_annotators = annotators or list(DEFAULT_BENCHMARK_ANNOTATORS)
    runtime_options = benchmark_annotator_options(
        {
            "bern2": bern2_options or {},
            "pubtator3": pubtator3_options or {},
            "flair": flair_options or {},
        }
    )
    cases = load_ncbi_cases(benchmark_path, split=split)
    predictions_by_annotator: dict[str, list[dict[str, Any]]] = {
        annotator: [] for annotator in selected_annotators
    }
    prediction_objects: dict[str, list[Annotation]] = {
        annotator: [] for annotator in selected_annotators
    }
    gold_annotations = _flatten_gold(cases)
    statuses: list[dict[str, Any]] = []

    for case in cases:
        results, case_statuses = run_selected_annotators_with_status(
            case.document,
            selected_annotators,
            bern2_request_fn=bern2_request_fn,
            pubtator3_request_fn=pubtator3_request_fn,
            bern2_options=runtime_options.get("bern2"),
            pubtator3_options=runtime_options.get("pubtator3"),
            flair_options=runtime_options.get("flair"),
        )
        for status in case_statuses:
            statuses.append({"document_id": case.document.document_id, **status})
        for annotator, annotations in results.items():
            prediction_objects.setdefault(annotator, []).extend(annotations)
            predictions_by_annotator.setdefault(annotator, []).extend(
                _prediction_rows(case.document.document_id, annotator, annotations)
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
        "metrics": metric_rows,
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
    _write_gold_jsonl(payload, output_dir / "gold.jsonl")
    _write_predictions_jsonl(payload, output_dir / "predictions.jsonl")
    _write_statuses_tsv(payload, output_dir / "annotator_statuses.tsv")
    _write_warnings_tsv(payload, output_dir / "loader_warnings.tsv")


def _flatten_gold(cases: list[BenchmarkCase]) -> list[GoldAnnotation]:
    gold: list[GoldAnnotation] = []
    for case in cases:
        gold.extend(case.gold_annotations)
    return gold


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
            }
        )
    _write_tsv(path, rows)


def _write_statuses_tsv(payload: dict[str, Any], path: Path) -> None:
    rows = [row for row in payload.get("statuses", []) if isinstance(row, dict)]
    _write_tsv(path, rows)


def _write_warnings_tsv(payload: dict[str, Any], path: Path) -> None:
    rows = [row for row in payload.get("warnings", []) if isinstance(row, dict)]
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
