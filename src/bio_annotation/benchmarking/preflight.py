from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(slots=True)
class PreflightResult:
    name: str
    status: str
    message: str
    resource: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
        }


class BenchmarkPreflightError(RuntimeError):
    """Raised when a benchmark annotator cannot be initialized before a run."""

    def __init__(self, result: PreflightResult) -> None:
        super().__init__(result.message)
        self.result = result


def preflight_benchmark_annotators(
    annotators: list[str],
    annotator_options: dict[str, dict[str, Any]],
    *,
    flair_tagger_loader: Callable[[str], Any] | None = None,
) -> tuple[list[PreflightResult], dict[str, Any]]:
    """Check benchmark runtime settings before iterating over documents.

    The checks are intentionally lightweight. Remote APIs are reported from the
    benchmark-owned configuration, while local Flair is loaded once so missing
    local models fail early instead of once per document.
    """

    results: list[PreflightResult] = []
    resources: dict[str, Any] = {}

    for annotator in annotators:
        options = annotator_options.get(annotator, {})
        if annotator == "bern2":
            endpoint = options.get("endpoint")
            if endpoint:
                results.append(
                    PreflightResult(
                        name="bern2",
                        status="configured",
                        message=f"BERN2 endpoint configured for benchmark review: {endpoint}",
                    )
                )
            else:
                result = PreflightResult(
                    name="bern2",
                    status="failed",
                    message=(
                        "BERN2 endpoint is not configured in the benchmark runtime settings. "
                        "Set it in src/bio_annotation/benchmarking/config.py."
                    ),
                )
                raise BenchmarkPreflightError(result)

        elif annotator == "flair":
            model = options.get("model")
            if not model:
                result = PreflightResult(
                    name="flair",
                    status="failed",
                    message=(
                        "Flair model is not configured in the benchmark runtime settings. "
                        "Set it in src/bio_annotation/benchmarking/config.py."
                    ),
                )
                raise BenchmarkPreflightError(result)
            loader = flair_tagger_loader or _load_flair_model
            try:
                tagger = loader(str(model))
            except Exception as exc:
                result = PreflightResult(
                    name="flair",
                    status="failed",
                    message=(
                        f"Benchmark config is being used. Flair is being called with model {model!r}, "
                        "but the model is not available through Flair's classifier loader in the local environment. "
                        f"Original error: {exc}"
                    ),
                )
                raise BenchmarkPreflightError(result) from exc
            resources["flair_tagger"] = tagger
            results.append(
                PreflightResult(
                    name="flair",
                    status="ready",
                    message=f"Flair model loaded for benchmark review: {model}",
                    resource=tagger,
                )
            )

        elif annotator == "pubtator3":
            endpoint = options.get("endpoint")
            mode = options.get("mode", "auto")
            results.append(
                PreflightResult(
                    name="pubtator3",
                    status="configured",
                    message=(
                        "PubTator3 benchmark runtime configured: "
                        f"endpoint={endpoint}, mode={mode}"
                    ),
                )
            )

    return results, resources


def _load_flair_model(model: str) -> Any:
    from flair.nn import Classifier

    return Classifier.load(model)


__all__ = [
    "BenchmarkPreflightError",
    "PreflightResult",
    "preflight_benchmark_annotators",
]
