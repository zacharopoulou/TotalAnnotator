from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urljoin

import bent.annotate as bt


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BENT and emit BRAT .ann files.")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--mode", choices=("ner", "ner_nel"), default="ner_nel")
    parser.add_argument("--types", required=True, help="Comma-separated entity_type:kb pairs.")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    patch_transformers_relative_redirects()

    bt.annotate(
        recognize=True,
        link=args.mode == "ner_nel",
        types=parse_types(args.types),
        in_dir=f"{input_dir}/",
        out_dir=f"{output_dir}/",
    )
    return 0


def patch_transformers_relative_redirects() -> None:
    """Make old Transformers releases tolerate current Hugging Face redirects."""

    import transformers.file_utils as file_utils

    original_head = file_utils.requests.head

    def head_with_absolute_location(url: str, *args, **kwargs):
        response = original_head(url, *args, **kwargs)
        location = response.headers.get("Location")
        if location and location.startswith("/"):
            response.headers["Location"] = urljoin(url, location)
        return response

    file_utils.requests.head = head_with_absolute_location


def parse_types(raw: str) -> dict[str, str]:
    types: dict[str, str] = {}
    for item in raw.split(","):
        if not item.strip():
            continue
        entity_type, _, kb = item.partition(":")
        entity_type = entity_type.strip()
        if entity_type:
            types[entity_type] = kb.strip()
    return types


if __name__ == "__main__":
    raise SystemExit(main())

