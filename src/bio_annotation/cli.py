from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bio_annotation._cli_arg_validator import positive_int
from bio_annotation.annotators import flatten_annotations, run_all_annotators
from bio_annotation.benchmarking.preflight import BenchmarkPreflightError
from bio_annotation.benchmarking.runner import run_ncbi_review_evaluation
from bio_annotation._cli_arg_validator import positive_int
from bio_annotation.io.search import search_pubmed_pmids, write_pmids
from bio_annotation.pipeline_config import load_pipeline_config
from bio_annotation.pipeline_runner import run_pipeline_from_config
from bio_annotation.preprocessing.document_loader import load_documents_from_config
from bio_annotation.schemas.document import Document


def build_demo_document() -> Document:
    return Document(
        document_id="PMID:12345678",
        pmid="12345678",
        title="PTEN regulates glioblastoma",
        abstract="PTEN and miR-21 are biomarkers in glioblastoma.",
        source="pubmed",
    )


def demo_payload() -> dict[str, object]:
    document = build_demo_document()
    results = run_all_annotators(
        document,
        bern2_response={
            "annotations": [
                {
                    "mention": "PTEN",
                    "span": {"begin": 0, "end": 4},
                    "type": "Gene",
                    "id": "NCBIGene:5728",
                    "normalizedName": "PTEN",
                    "probability": 0.98,
                }
            ]
        },
        flair_spans=[],
        pubtator3_response={
            "documents": [
                {
                    "passages": [
                        {
                            "annotations": [
                                {
                                    "text": "glioblastoma",
                                    "infons": {"type": "Disease", "identifier": "D005909"},
                                    "locations": [{"offset": 15, "length": 12}],
                                }
                            ]
                        }
                    ]
                }
            ]
        },
    )
    return {
        "document_id": document.document_id,
        "pmid": document.pmid,
        "sources": sorted(results),
        "annotation_count": len(flatten_annotations(results)),
        "annotations": [annotation.to_dict() for annotation in flatten_annotations(results)],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="totalannotator",
        description="Utilities for the TotalAnnotator biomedical annotation project.",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("info", help="Show a short project summary.")
    subparsers.add_parser("demo", help="Run a local mocked annotation demo.")
    inspect_parser = subparsers.add_parser("inspect-config", help="Show parsed pipeline config values.")
    inspect_parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/pipeline.toml"),
        help="Pipeline config path.",
    )
    load_parser = subparsers.add_parser("load-documents", help="Load documents from a pipeline config and print a preview.")
    load_parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/pipeline.toml"),
        help="Pipeline config path.",
    )
    run_parser = subparsers.add_parser("run-config", help="Load documents from config and run selected annotators.")
    run_parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/pipeline.toml"),
        help="Pipeline config path.",
    )
    review_parser = subparsers.add_parser(
        "evaluate-ncbi-review",
        help="Run the standalone NCBI Disease benchmark-review evaluator.",
    )
    review_parser.add_argument(
        "--benchmark-path",
        type=Path,
        default=None,
        help="Optional path to an NCBI Disease JSONL split. Default: benchmarks/data/ncbi/<split>.jsonl.",
    )
    review_parser.add_argument("--split", default="test", help="NCBI split name. Default: test.")
    review_parser.add_argument(
        "--annotators",
        default="bern2,pubtator3,flair",
        help="Comma-separated annotators to evaluate. Default: bern2,pubtator3,flair.",
    )
    review_parser.add_argument(
        "--entity-type",
        default="disease",
        help="Entity type to score. Default: disease.",
    )
    review_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/benchmark-review/ncbi_disease"),
        help="Directory for JSONL/TSV review outputs.",
    )
    search_parser = subparsers.add_parser("search-pmids", help="Search PubMed and write matching PMIDs to a file.")
    search_parser.add_argument("--query", required=True, help="PubMed query string.")
    search_parser.add_argument(
        "--max-results",
        type=positive_int,
        default=None,
        help="Optional upper bound on PMIDs returned. Default: fetch all matching PMIDs.",
    )
    search_parser.add_argument("--date-from", help="Optional publication start date.")
    search_parser.add_argument("--date-to", help="Optional publication end date.")
    search_parser.add_argument("--sort-by", default="relevance", help="PubMed sort order.")
    search_parser.add_argument(
        "--filter",
        action="append",
        default=[],
        help="Additional raw PubMed filter clause. Can be repeated.",
    )
    search_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output path for the PMID file.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in (None, "info"):
        print("TotalAnnotator")
        print("Workflow: corpus -> annotators -> comparable outputs")
        print("Quickstart: uv sync && uv run totalannotator demo")
        print("Inspect config: uv run totalannotator inspect-config")
        print("Preview documents: uv run totalannotator load-documents")
        print("Run config: uv run totalannotator run-config")
        print("Review benchmark: uv run totalannotator evaluate-ncbi-review")
        print("Search PMIDs: uv run totalannotator search-pmids --query '...' --output data/inputs/query_pmids.txt")
        return 0

    if args.command == "demo":
        print(json.dumps(demo_payload(), indent=2))
        return 0

    if args.command == "inspect-config":
        try:
            config = load_pipeline_config(args.config)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "input_mode": config.input_mode,
                    "pmids": config.pmids,
                    "pmid_file": str(config.pmid_file) if config.pmid_file is not None else None,
                    "text_file": str(config.text_file) if config.text_file is not None else None,
                    "text_format": config.text_format,
                    "document_id_column": config.document_id_column,
                    "title_column": config.title_column,
                    "abstract_column": config.abstract_column,
                    "corpus_path": str(config.corpus_path) if config.corpus_path is not None else None,
                    "enrichment_sources": config.enrichment_sources,
                    "annotators": config.annotators,
                    "annotator_settings": config.annotator_settings,
                    "entity_types": config.entity_types,
                    "output_path": str(config.output_path) if config.output_path is not None else None,
                    "fetch_sources": config.fetch_sources,
                    "fetch_fields": config.fetch_fields,
                    "fetch_fields_per_source": config.fetch_fields_per_source,
                    "pubtator3_full_text": config.pubtator3_full_text,
                },
                indent=2,
            )
        )
        return 0

    if args.command == "load-documents":
        try:
            config = load_pipeline_config(args.config)
            documents = load_documents_from_config(config)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "input_mode": config.input_mode,
                    "document_count": len(documents),
                    "documents": [
                        {
                            "document_id": document.document_id,
                            "pmid": document.pmid,
                            "source": document.source,
                            "title": document.title,
                            "abstract": document.abstract,
                        }
                        for document in documents
                    ],
                },
                indent=2,
            )
        )
        return 0

    if args.command == "run-config":
        try:
            config = load_pipeline_config(args.config)
            payload = run_pipeline_from_config(args.config)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print_run_config_summary(payload, config.output_path)
        return 0

    if args.command == "evaluate-ncbi-review":
        try:
            annotators = [item.strip() for item in args.annotators.split(",") if item.strip()]
            payload = run_ncbi_review_evaluation(
                benchmark_path=args.benchmark_path,
                split=args.split,
                annotators=annotators,
                output_dir=args.output_dir,
                entity_type=args.entity_type,
            )
        except BenchmarkPreflightError as exc:
            print("Benchmark preflight failed.", file=sys.stderr)
            print(exc.result.message, file=sys.stderr)
            return 1
        except (FileNotFoundError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print_benchmark_review_summary(payload, args.output_dir)
        return 0

    if args.command == "search-pmids":
        try:
            pmids = search_pubmed_pmids(
                args.query,
                max_results=args.max_results,
                date_from=args.date_from,
                date_to=args.date_to,
                sort_by=args.sort_by,
                filters=args.filter,
            )
            write_pmids(args.output, pmids)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "query": args.query,
                    "pmid_count": len(pmids),
                    "output": str(args.output),
                    "pmids_preview (First 10)": pmids[:10],
                },
                indent=2,
            )
        )
        return 0

    parser.print_help()
    return 1


def print_benchmark_review_summary(payload: dict[str, object], output_dir: Path) -> None:
    print("NCBI Disease benchmark review completed.")
    preflight = payload.get("preflight")
    if isinstance(preflight, list):
        print("Preflight:")
        for item in preflight:
            if isinstance(item, dict):
                print(f"  - {item.get('name')}: {item.get('status')} — {item.get('message')}")
    print(f"Documents: {payload.get('document_count', 0)}")
    print(f"Gold annotations: {payload.get('gold_count', 0)}")
    print(f"Output directory: {output_dir.as_posix()}")
    metrics = payload.get("metrics")
    if isinstance(metrics, list):
        for item in metrics:
            if not isinstance(item, dict):
                continue
            strict = item.get("strict") if isinstance(item.get("strict"), dict) else {}
            lenient = item.get("lenient") if isinstance(item.get("lenient"), dict) else {}
            print(
                f"{item.get('annotator')}: "
                f"strict F1={float(strict.get('f1', 0.0)):.3f}, "
                f"lenient F1={float(lenient.get('f1', 0.0)):.3f}"
            )


def print_run_config_summary(payload: dict[str, object], output_path: Path | None) -> None:
    annotation_summary = payload.get("annotation_summary")
    summary = annotation_summary if isinstance(annotation_summary, dict) else {}
    output = payload.get("output")
    actual_output_path = (
        output.get("path")
        if isinstance(output, dict)
        else None
    )

    print("Pipeline completed.")
    if isinstance(actual_output_path, str) and actual_output_path:
        print(f"Output written to: {actual_output_path}")
    elif output_path is not None:
        print(f"Output written to: {output_path.as_posix()}")
    else:
        print("No output path configured; no JSON file was written.")

    print(f"Documents: {payload.get('document_count', 0)}")
    print(f"Annotations: {summary.get('annotation_count', 0)}")
    print(f"Keywords: {summary.get('keyword_count', 0)}")

    annotator_summary = payload.get("annotator_summary")
    if isinstance(annotator_summary, dict):
        produced = annotator_summary.get("produced")
        not_produced = annotator_summary.get("not_produced")
        failed = annotator_summary.get("failed")
        print(f"Annotators with results: {_format_name_list(produced)}")
        print(f"Annotators without results: {_format_name_list(not_produced)}")
        if failed:
            print(f"Annotators failed: {_format_name_list(failed)}")


def _format_name_list(value: object) -> str:
    if isinstance(value, list) and value:
        return ", ".join(str(item) for item in value)
    return "none"