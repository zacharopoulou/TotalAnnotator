from __future__ import annotations

import argparse
import json

from bio_annotation.entity_proposal import flatten_annotations, run_all_annotators
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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in (None, "info"):
        print("TotalAnnotator")
        print("Workflow: document -> annotators -> unified annotations")
        print("Quickstart: uv sync && uv run totalannotator demo")
        return 0

    if args.command == "demo":
        print(json.dumps(demo_payload(), indent=2))
        return 0

    parser.print_help()
    return 1
