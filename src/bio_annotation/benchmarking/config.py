from __future__ import annotations

from copy import deepcopy
from typing import Any


DEFAULT_BENCHMARK_ANNOTATORS = ["bern2", "pubtator3", "flair"]

DEFAULT_BENCHMARK_ANNOTATOR_OPTIONS: dict[str, dict[str, Any]] = {
    "bern2": {
        "runtime": "remote_api",
        "base_url": "http://127.0.0.1:8888",
        "endpoint": "http://bern2.korea.ac.kr/plain",
    },
    "flair": {
        "runtime": "local_model",
        "model": "hunflair2",
    },
    "pubtator3": {
        "runtime": "remote_api",
        "endpoint": "https://www.ncbi.nlm.nih.gov/research/pubtator3-api",
        "format": "biocjson",
        "timeout": 60,
        "mode": "auto",
        "bioconcept": "All",
    },
}


def benchmark_annotator_options(
    overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return benchmark-owned annotator options with optional per-annotator overrides."""

    options = deepcopy(DEFAULT_BENCHMARK_ANNOTATOR_OPTIONS)
    if not overrides:
        return options

    for annotator, values in overrides.items():
        options.setdefault(annotator, {})
        options[annotator].update(values)
    return options


__all__ = [
    "DEFAULT_BENCHMARK_ANNOTATORS",
    "DEFAULT_BENCHMARK_ANNOTATOR_OPTIONS",
    "benchmark_annotator_options",
]
