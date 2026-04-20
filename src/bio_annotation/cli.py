from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bio_annotation.annotators import flatten_annotations, run_all_annotators
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
        pubtator_response={
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
    search_parser = subparsers.add_parser("search-pmids", help="Search PubMed and write matching PMIDs to a file.")
    search_parser.add_argument("--query", required=True, help="PubMed query string.")
    search_parser.add_argument("--max-results", type=int, default=100, help="Maximum number of PMIDs to return.")
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
                    "entity_types": config.entity_types,
                    "output_path": str(config.output_path) if config.output_path is not None else None,
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
            payload = run_pipeline_from_config(args.config)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(payload, indent=2))
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
                    "pmids": pmids,
                },
                indent=2,
            )
        )
        return 0

    parser.print_help()
    return 1
