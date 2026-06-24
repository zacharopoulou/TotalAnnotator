from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

from bio_annotation.entity_proposal._shared import make_annotation
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation

DEFAULT_BENT_MODE = "ner_nel"
DEFAULT_BENT_PROJECT = "tools/bent"
DEFAULT_BENT_TIMEOUT = 900
DEFAULT_BENT_TYPES: dict[str, str] = {
    "disease": "medic",
    "chemical": "chebi",
    "gene": "ncbi_gene",
    "organism": "ncbi_taxon",
    "anatomical": "uberon",
    "cell_line": "cellosaurus",
    "bioprocess": "go_bp",
    "cell_component": "go_cc",
    "cell_type": "cell_ontology",
}

SETUP_HINT = (
    "Run tools/bent/setup.sh to install BENT and its dictionaries, then enable "
    "annotators.bent in your config."
)


def parse_bent_response(document: Document, payload: Any) -> list[Annotation]:
    if not payload:
        return []

    terms: dict[str, dict[str, Any]] = {}
    links: dict[str, dict[str, str]] = {}

    for line in str(payload).splitlines():
        if not line.strip():
            continue
        if line.startswith("T"):
            term = _parse_term_line(line)
            if term is not None:
                terms[term["term_id"]] = term
        elif line.startswith("N"):
            link = _parse_normalization_line(line)
            if link is not None:
                links[link["term_id"]] = link

    annotations: list[Annotation] = []
    for term_id, term in terms.items():
        link = links.get(term_id, {})
        start, end = _validated_offsets(
            document=document,
            span_text=term["span_text"],
            start=term["start"],
            end=term["end"],
        )
        annotations.append(
            make_annotation(
                document=document,
                source="bent",
                span_text=term["span_text"],
                entity_type=term["entity_type"],
                start=start,
                end=end,
                canonical_id=link.get("canonical_id"),
                canonical_name=link.get("canonical_name"),
            )
        )
    return annotations


def call_bent(
    document: Document,
    *,
    types: dict[str, str] | None = None,
    mode: str = DEFAULT_BENT_MODE,
    project: str = DEFAULT_BENT_PROJECT,
    python: str | None = None,
    timeout: int = DEFAULT_BENT_TIMEOUT,
) -> str:
    """Run BENT as an isolated subprocess and return raw BRAT standoff output."""

    with tempfile.TemporaryDirectory() as tmp:
        in_dir = Path(tmp) / "input"
        out_dir = Path(tmp) / "output"
        in_dir.mkdir()
        out_dir.mkdir()
        in_file = in_dir / "document.txt"
        in_file.write_text(document.text, encoding="utf-8")

        script = Path(__file__).resolve().parents[3] / "tools" / "bent" / "run_bent.py"
        if python:
            command = [python, str(script)]
        else:
            command = ["uv", "run", "--project", str(Path(project).resolve()), "python", str(script)]

        command += [
            "--input-dir",
            str(in_dir),
            "--output-dir",
            str(out_dir),
            "--mode",
            mode,
            "--types",
            _serialize_types(types or DEFAULT_BENT_TYPES),
        ]

        try:
            env = os.environ.copy()
            env.pop("VIRTUAL_ENV", None)
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"BENT could not be launched ('{command[0]}' not found): {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"BENT timed out after {timeout}s.") from exc

        if completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"BENT failed (exit {completed.returncode}): {stderr}. {SETUP_HINT}")

        out_file = out_dir / "document.ann"
        if not out_file.exists():
            produced = sorted(out_dir.glob("*.ann"))
            if not produced:
                return ""
            out_file = produced[0]
        return out_file.read_text(encoding="utf-8")


def annotate_with_bent(
    document: Document,
    *,
    response: Any = None,
    request_fn: Callable[[Document], Any] | None = None,
    types: dict[str, str] | None = None,
    mode: str = DEFAULT_BENT_MODE,
    project: str = DEFAULT_BENT_PROJECT,
    python: str | None = None,
    timeout: int = DEFAULT_BENT_TIMEOUT,
) -> list[Annotation]:
    payload = response
    if payload is None and request_fn is not None:
        payload = request_fn(document)
    if payload is None:
        payload = call_bent(
            document,
            types=types,
            mode=mode,
            project=project,
            python=python,
            timeout=timeout,
        )
    return parse_bent_response(document, payload)


def _parse_term_line(line: str) -> dict[str, Any] | None:
    parts = line.split("\t")
    if len(parts) < 3:
        return None
    term_id, span_info, span_text = parts[0], parts[1], parts[2]
    span_parts = span_info.split()
    if len(span_parts) < 3:
        return None
    entity_type = span_parts[0]
    start, end = _parse_simple_brat_span(span_parts[1:])
    if start is None or end is None or not span_text:
        return None
    return {
        "term_id": term_id,
        "entity_type": entity_type,
        "start": start,
        "end": end,
        "span_text": span_text,
    }


def _parse_simple_brat_span(span_parts: list[str]) -> tuple[int | None, int | None]:
    # BENT emits contiguous BRAT spans in normal operation. If a discontinuous
    # BRAT span appears, use the outer bounds so downstream code still has a
    # useful location for the mention text.
    try:
        start = int(span_parts[0].split(";", 1)[0])
        end = int(span_parts[-1])
    except (IndexError, ValueError):
        return None, None
    return start, end


def _parse_normalization_line(line: str) -> dict[str, str] | None:
    parts = line.split("\t")
    if len(parts) < 2:
        return None
    reference_parts = parts[1].split()
    if len(reference_parts) < 3 or reference_parts[0] != "Reference":
        return None
    return {
        "term_id": reference_parts[1],
        "canonical_id": reference_parts[2],
        "canonical_name": parts[2] if len(parts) > 2 else "",
    }


def _validated_offsets(
    *,
    document: Document,
    span_text: str,
    start: int,
    end: int,
) -> tuple[int | None, int | None]:
    if 0 <= start <= end <= len(document.text) and document.text[start:end] == span_text:
        return start, end
    return None, None


def _serialize_types(types: dict[str, str]) -> str:
    return ",".join(f"{entity_type}:{kb}" for entity_type, kb in sorted(types.items()) if entity_type)

