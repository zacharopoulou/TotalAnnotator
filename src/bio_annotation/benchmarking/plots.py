from __future__ import annotations

from pathlib import Path
from typing import Any


def write_review_plots(payload: dict[str, Any], output_dir: Path) -> None:
    """Write benchmark-review PNG plots.

    Plot generation is intentionally downstream of the JSON/TSV payload so it
    stays a review/reporting concern and does not affect scoring semantics.
    """

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plots_dir = output_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    _plot_metrics_overview(payload, plots_dir / "metrics_overview.png", plt)
    _plot_coverage_groups(payload, plots_dir / "coverage_groups.png", plt)
    _plot_normalization_accuracy(payload, plots_dir / "normalization_accuracy.png", plt)
    _plot_consensus_gold_coverage(payload, plots_dir / "consensus_gold_coverage.png", plt)


def _plot_metrics_overview(payload: dict[str, Any], path: Path, plt: Any) -> None:
    metrics = _metric_rows(payload)
    annotators = [str(row.get("annotator", "")) for row in metrics]
    strict_f1 = [_metric_value(row, "strict", "f1") for row in metrics]
    lenient_f1 = [_metric_value(row, "lenient", "f1") for row in metrics]

    x_positions = list(range(len(annotators)))
    width = 0.35
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar([x - width / 2 for x in x_positions], strict_f1, width, label="Strict F1")
    ax.bar([x + width / 2 for x in x_positions], lenient_f1, width, label="Lenient F1")
    ax.set_title("NCBI Disease span performance")
    ax.set_ylabel("F1")
    ax.set_ylim(0, 1.05)
    ax.set_xticks(x_positions)
    ax.set_xticklabels(annotators, rotation=30, ha="right")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_normalization_accuracy(payload: dict[str, Any], path: Path, plt: Any) -> None:
    metrics = _metric_rows(payload)
    annotators = [str(row.get("annotator", "")) for row in metrics]
    strict_norm = [
        _metric_value(row, "strict_normalization", "accuracy_on_matched_spans")
        for row in metrics
    ]
    lenient_norm = [
        _metric_value(row, "lenient_normalization", "accuracy_on_matched_spans")
        for row in metrics
    ]
    strict_coverage = [
        _metric_value(row, "strict_normalization", "prediction_id_coverage_on_matched_spans")
        for row in metrics
    ]
    lenient_coverage = [
        _metric_value(row, "lenient_normalization", "prediction_id_coverage_on_matched_spans")
        for row in metrics
    ]

    x_positions = list(range(len(annotators)))
    width = 0.2
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar([x - 1.5 * width for x in x_positions], strict_norm, width, label="Strict norm acc")
    ax.bar([x - 0.5 * width for x in x_positions], lenient_norm, width, label="Lenient norm acc")
    ax.bar([x + 0.5 * width for x in x_positions], strict_coverage, width, label="Strict ID coverage")
    ax.bar([x + 1.5 * width for x in x_positions], lenient_coverage, width, label="Lenient ID coverage")
    ax.set_title("NCBI Disease normalization performance")
    ax.set_ylabel("Rate")
    ax.set_ylim(0, 1.05)
    ax.set_xticks(x_positions)
    ax.set_xticklabels(annotators, rotation=30, ha="right")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_coverage_groups(payload: dict[str, Any], path: Path, plt: Any) -> None:
    gold_keys, coverage = _gold_coverage(payload)
    annotators = _annotators(payload)
    annotator_count = len(annotators)
    counts = {
        "missed_by_all": 0,
        "found_by_1_annotator": 0,
        "found_by_2_annotators": 0,
        "found_by_3_annotators": 0,
        "strictly_found_by_all": 0,
        "normalization_correct_by_all": 0,
    }

    for key in gold_keys:
        states = [coverage.get(key, {}).get(annotator, 0) for annotator in annotators]
        found = sum(1 for state in states if state >= 1)
        if found == 0:
            counts["missed_by_all"] += 1
        elif found == 1:
            counts["found_by_1_annotator"] += 1
        elif found == 2:
            counts["found_by_2_annotators"] += 1
        elif found >= 3:
            counts["found_by_3_annotators"] += 1
        if annotator_count and all(state >= 2 for state in states):
            counts["strictly_found_by_all"] += 1
        if annotator_count and all(state >= 3 for state in states):
            counts["normalization_correct_by_all"] += 1

    labels = list(counts)
    values = [counts[label] for label in labels]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(labels, values)
    ax.set_title("NCBI Disease gold coverage groups")
    ax.set_ylabel("Gold annotations")
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.grid(axis="y", alpha=0.3)
    for index, value in enumerate(values):
        ax.text(index, value, str(value), ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_consensus_gold_coverage(payload: dict[str, Any], path: Path, plt: Any) -> None:
    gold_keys, coverage = _gold_coverage(payload)
    annotators = _annotators(payload)
    if not gold_keys or not annotators:
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.text(0.5, 0.5, "No gold coverage data", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        fig.savefig(path, dpi=160)
        plt.close(fig)
        return

    sorted_keys = sorted(
        gold_keys,
        key=lambda key: (
            sum(coverage.get(key, {}).get(annotator, 0) for annotator in annotators),
            key,
        ),
    )
    matrix = [
        [coverage.get(key, {}).get(annotator, 0) for annotator in annotators]
        for key in sorted_keys
    ]

    height = max(5, min(14, 0.08 * len(sorted_keys) + 2))
    fig, ax = plt.subplots(figsize=(7, height))
    image = ax.imshow(matrix, aspect="auto", interpolation="nearest", vmin=0, vmax=3)
    ax.set_title("Gold disease coverage by annotator")
    ax.set_xticks(list(range(len(annotators))))
    ax.set_xticklabels(annotators, rotation=30, ha="right")
    ax.set_ylabel("Gold annotations, sorted by coverage")
    ax.set_yticks([])
    colorbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    colorbar.set_ticks([0, 1, 2, 3])
    colorbar.set_ticklabels(["miss", "lenient", "strict", "norm ok"])
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _metric_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = payload.get("metrics")
    return [row for row in metrics if isinstance(row, dict)] if isinstance(metrics, list) else []


def _metric_value(row: dict[str, Any], group: str, key: str) -> float:
    value = row.get(group)
    if not isinstance(value, dict):
        return 0.0
    try:
        return float(value.get(key, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _annotators(payload: dict[str, Any]) -> list[str]:
    annotators = payload.get("annotators")
    if isinstance(annotators, list):
        return [str(item) for item in annotators]
    predictions = payload.get("predictions")
    if isinstance(predictions, dict):
        return [str(item) for item in predictions]
    return []


def _gold_coverage(payload: dict[str, Any]) -> tuple[list[tuple[str, int, int]], dict[tuple[str, int, int], dict[str, int]]]:
    gold_rows = _gold_rows(payload)
    prediction_rows_by_annotator = _prediction_rows_by_annotator(payload)
    annotators = _annotators(payload)
    gold_keys = [
        (str(row.get("document_id", "")), int(row.get("start", 0)), int(row.get("end", 0)))
        for row in gold_rows
        if _has_offsets(row)
    ]
    coverage: dict[tuple[str, int, int], dict[str, int]] = {
        key: {annotator: 0 for annotator in annotators}
        for key in gold_keys
    }

    for gold in gold_rows:
        if not _has_offsets(gold):
            continue
        key = (str(gold.get("document_id", "")), int(gold.get("start", 0)), int(gold.get("end", 0)))
        gold_ids = _id_aliases(gold.get("normalized_ids"))
        for annotator in annotators:
            best_state = 0
            for prediction in prediction_rows_by_annotator.get(annotator, []):
                if str(prediction.get("document_id", "")) != key[0] or not _has_offsets(prediction):
                    continue
                prediction_start = int(prediction.get("start", 0))
                prediction_end = int(prediction.get("end", 0))
                if prediction_start == key[1] and prediction_end == key[2]:
                    state = 2
                    prediction_ids = _id_aliases(prediction.get("canonical_id"))
                    if gold_ids and prediction_ids and gold_ids & prediction_ids:
                        state = 3
                elif max(prediction_start, key[1]) < min(prediction_end, key[2]):
                    state = 1
                else:
                    state = 0
                if state > best_state:
                    best_state = state
            coverage[key][annotator] = best_state
    return gold_keys, coverage


def _gold_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("gold_annotations")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _prediction_rows_by_annotator(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    predictions = payload.get("predictions")
    out: dict[str, list[dict[str, Any]]] = {}
    if not isinstance(predictions, dict):
        return out
    for annotator, rows in predictions.items():
        out[str(annotator)] = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    return out


def _has_offsets(row: dict[str, Any]) -> bool:
    return row.get("start") is not None and row.get("end") is not None


def _id_aliases(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, list):
        values = [str(item) for item in value]
    else:
        values = str(value).strip("[]").replace("|", ";").replace(",", ";").split(";")
    aliases: set[str] = set()
    for item in values:
        normalized = str(item).strip().strip("'\"").upper().replace(" ", "")
        if not normalized or normalized == "-":
            continue
        aliases.add(normalized)
        if ":" in normalized:
            suffix = normalized.split(":", 1)[1]
            if suffix:
                aliases.add(suffix)
    return aliases


__all__ = ["write_review_plots"]
