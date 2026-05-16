"""Standalone benchmark-review utilities.

This package is intentionally separate from the main pipeline runner so benchmark
experiments can reuse the public document/annotation contracts without changing
normal production runs.
"""

from bio_annotation.benchmarking.ncbi import BenchmarkCase, GoldAnnotation, load_ncbi_cases

__all__ = ["BenchmarkCase", "GoldAnnotation", "load_ncbi_cases"]
