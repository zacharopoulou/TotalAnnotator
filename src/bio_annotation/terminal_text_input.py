from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]

TEXT_TABLE_SUFFIXES: dict[str, str] = {".csv": "csv", ".tsv": "tsv"}
GENERATED_TEXT_DOCUMENT_ID = "text-1"
GENERATED_TEXT_TITLE = "User-provided plain text"


def is_text_table_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_TABLE_SUFFIXES


def text_table_format(path: Path) -> str:
    return TEXT_TABLE_SUFFIXES.get(path.suffix.lower(), "tsv")


def resolve_existing_file(raw_path: str) -> Path:
    return Path(raw_path).expanduser().resolve()


def prompt_existing_file(*, input_fn: InputFn, output_fn: OutputFn) -> Path:
    while True:
        raw = input_fn("Plain text file path: ").strip()
        if not raw:
            continue
        path = resolve_existing_file(raw)
        if path.is_file():
            return path
        output_fn(f"File not found: {path}")


def prompt_multiline_text(*, input_fn: InputFn, output_fn: OutputFn) -> str:
    output_fn("Enter plain text. Finish with a line containing only END.")
    lines: list[str] = []
    while True:
        line = input_fn("")
        if line.strip() == "END":
            break
        lines.append(line)
    text = "\n".join(lines).strip()
    if not text:
        raise ValueError("Plain text input must not be empty.")
    return text


def write_generated_text_table(path: Path, text: str) -> None:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Plain text input must not be empty.")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["document_id", "title", "abstract"],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerow(
            {
                "document_id": GENERATED_TEXT_DOCUMENT_ID,
                "title": GENERATED_TEXT_TITLE,
                "abstract": cleaned,
            }
        )


def write_generated_text_table_from_raw_text_file(path: Path, text_file: Path) -> None:
    lines = [line.strip() for line in text_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise ValueError("Plain text file must contain at least one non-empty line.")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["document_id", "title", "abstract"],
            delimiter="\t",
        )
        writer.writeheader()
        for index, text in enumerate(lines, start=1):
            writer.writerow(
                {
                    "document_id": f"text-{index}",
                    "title": "",
                    "abstract": text,
                }
            )
