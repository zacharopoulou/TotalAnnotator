#!/usr/bin/env python3
"""Unified fetch CLI for :mod:`bio_annotation.fetch`: PMIDs, PMCIDs, PubMed queries,
optional TOML config, and optional annotators 
From the repository root::
    Example commands: TotalAnnotator\docs\unified_fetch_cli_reference.txt
    
``--source`` may be repeated. Defaults to ``pubtator3`` 

Use--medcat-raw`` (or ``[annotators.medcat] include_raw = true`` in a TOML ``--config``)
to add ``medcat_raw`` next to ``medcat`` in each annotator row: the full MedCATservice JSON
response for that document (same shape as ``Invoke-RestMethod`` / ``POST /api/process``).

Use ``--flair-raw`` (or ``[annotators.flair] include_raw = true``) to add ``flair_raw``: a
JSON-safe snapshot of the Flair ``Sentence`` after ``predict`` (``to_dict()``), alongside ``flair``.

If ``.env`` file exists in the repository root, it is loaded before annotators run

``--field`` maps to fetch logical fields. Use ``--list-fields`` to inspect all
supported fields per source.

``--input-kind`` selects PMID list (default), single PMID/PMCID, or ``query``.
Raw-text fetch is intentionally not exposed here.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_src_on_path() -> None:
    src = _repo_root() / "src"
    if src.is_dir():
        sys.path.insert(0, str(src))


def _load_repo_dotenv() -> None:
    """Set ``os.environ`` from ``<repo>/.env`` if present (``KEY=value``, ``#`` comments).

    Does not override variables already set in the process environment.
    Running ``py -3 scripts/unified_fetch.py`` then matches ``unified_fetch.cmd`` loading ``.env``.
    """

    path = _repo_root() / ".env"
    if not path.is_file():
        return
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except OSError:
        return
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key not in os.environ:
            os.environ[key] = value


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Unified fetch: documents via bio_annotation.fetch (PMID, PMCID, or query).",
    )
    p.add_argument(
        "ids",
        nargs="*",
        metavar="ID",
        help="One or more PMIDs or PMCIDs (depending on --input-kind; ignored if --ids-file is set).",
    )
    p.add_argument(
        "--input-kind",
        choices=("pmid", "pmid_list", "pmcid", "pmcid_list", "query"),
        default=None,
        help=(
            "What the IDs or --query represent. Default: query when --query/fetch.query is set and no IDs "
            "are given; otherwise pmid_list. Use pmcid/pmcid_list for PMCIDs."
        ),
    )
    p.add_argument(
        "--id",
        dest="single_id",
        default=None,
        metavar="ID",
        help="Single PMID or PMCID (alternative to one positional).",
    )
    p.add_argument(
        "--query",
        "-q",
        default=None,
        metavar="STRING",
        help="PubMed-style query (requires --input-kind query or sets kind to query when used alone).",
    )
    p.add_argument(
        "--file",
        "-f",
        "--ids-file",
        type=Path,
        metavar="PATH",
        dest="ids_file",
        help="Text file with one ID per line (# comments allowed).",
    )
    p.add_argument(
        "--config",
        type=Path,
        metavar="PATH",
        help="Optional TOML config for fetch defaults and annotator endpoints.",
    )
    p.add_argument(
        "--source",
        action="append",
        default=None,
        metavar="NAME",
        help=(
            "Fetch backend: pubtator3, entrez, europe_pmc. "
            "Repeat to merge in order (e.g. --source pubtator3 --source entrez). "
            "Default: pubtator3."
        ),
    )
    p.add_argument(
        "--annotator",
        action="append",
        default=None,
        metavar="NAME",
        help=(
            "Optional annotator(s) to run after fetch. "
            "Supported: pubtator3, medcat, flair (local Flair/HunFlair — requires ``flair`` installed)."
        ),
    )
    p.add_argument(
        "--field",
        action="append",
        default=None,
        metavar="NAME",
        help=(
            "Logical fetch fields (repeatable). Use --list-fields to see every "
            "supported field per source."
        ),
    )
    p.add_argument(
        "--list-fields",
        action="store_true",
        help="Print supported logical fields per source and exit.",
    )
    p.add_argument(
        "--include-annotations",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Include PubTator annotations payload when source includes pubtator3. "
            "Default: false unless you explicitly request --field annotations."
        ),
    )
    p.add_argument(
        "--strict-sources",
        action="store_true",
        default=None,
        help=(
            "Do not auto-add sources for requested fields. "
            "If a field is unavailable in selected --source values, exit with an error."
        ),
    )
    p.add_argument(
        "--pubtator-chunk-size",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Max characters per chunk when PubTator3 text annotation falls back to chunked mode "
            "(default 6000). Larger = fewer requests but more timeout risk per request."
        ),
    )
    p.add_argument(
        "--pubtator-chunk-overlap",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Overlap between adjacent chunks for PubTator3 chunked annotation (default 300). "
            "Helps entities at boundaries; higher overlap means more duplicate work before dedupe."
        ),
    )
    p.add_argument(
        "--medcat-raw",
        action="store_true",
        help=(
            "When MedCAT runs, include the full MedCATservice HTTP JSON per document under "
            "results.medcat_raw (large). Same as [annotators.medcat] include_raw = true in config."
        ),
    )
    p.add_argument(
        "--flair-raw",
        action="store_true",
        help=(
            "When Flair runs, include a JSON-safe Sentence snapshot per document under "
            "results.flair_raw (large). Same as [annotators.flair] include_raw = true in config."
        ),
    )
    p.add_argument(
        "--flair-model",
        default=None,
        metavar="ID",
        help=(
            "When --annotator flair is used: ``Classifier.load(ID)`` model name "
            "(default: hunflair2). Overrides [annotators.flair] model in config."
        ),
    )
    return p.parse_args(argv)


def _normalize_cli_aliases(argv: list[str]) -> list[str]:
    """Allow convenient config invocation aliases.

    Supported shortcuts:
    - ``unified_fetch.py config path/to/file.toml``
    - ``unified_fetch.py path/to/file.toml``
    """

    if not argv:
        return argv
    first = argv[0].strip()
    if first.lower() == "config" and len(argv) >= 2:
        return ["--config", argv[1], *argv[2:]]
    if (
        len(argv) == 1
        and first.lower().endswith(".toml")
        and not first.startswith("-")
    ):
        return ["--config", first]
    return argv


def _load_ids_from_file(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        if cleaned not in seen:
            seen.add(cleaned)
            out.append(cleaned)
    return out


def _is_plausible_pmcid(token: str) -> bool:
    if not token or token.startswith("-"):
        return False
    u = token.strip().upper()
    if u.startswith("PMC:"):
        u = u.split(":", 1)[1].strip()
    if u.startswith("PMC"):
        digits = u[3:]
    else:
        digits = u
    return bool(digits) and digits.isdigit()


def _wants_full_text(
    *,
    explicit_fields: list[str] | None,
    fields_per_source: dict[str, frozenset[str]] | None,
) -> bool:
    if explicit_fields and "full_text" in explicit_fields:
        return True
    if fields_per_source:
        return any("full_text" in fs for fs in fields_per_source.values())
    return False


def _warn_if_full_text_missing(
    documents: list[object],
    *,
    explicit_fields: list[str] | None,
    fields_per_source: dict[str, frozenset[str]] | None,
) -> None:
    if not _wants_full_text(explicit_fields=explicit_fields, fields_per_source=fields_per_source):
        return
    from bio_annotation.schemas.document import Document

    for doc in documents:
        if not isinstance(doc, Document):
            continue
        if (doc.full_text or "").strip():
            continue
        pmid = doc.pmid or doc.document_id
        meta = doc.metadata if isinstance(doc.metadata, dict) else {}
        status = meta.get("epmc_full_text_status")
        if status == "not_in_pubmed_central":
            print(
                f"Warning: {pmid} is not in PubMed Central (publisher/subscription). "
                "Europe PMC has no fullTextXML; PubTator export is often title+abstract only. "
                "Use a PMC-indexed PMID/PMCID for body text, or access the publisher PDF/HTML directly.",
                file=sys.stderr,
            )
        elif status == "no_pmcid_in_record":
            print(
                f"Warning: Europe PMC returned no PMCID for {pmid}; full text XML was not fetched.",
                file=sys.stderr,
            )
        else:
            print(
                f"Warning: full_text was requested but is empty for {pmid}. "
                "If the paper is not open-access in PMC, full body text may be unavailable via these APIs.",
                file=sys.stderr,
            )


def _validate_id_tokens_for_input_kind(input_kind: str, raw_ids: list[str]) -> str | None:
    """Return a user-facing error message if IDs are not plausible, else None."""

    if input_kind in ("pmid", "pmid_list"):
        for token in raw_ids:
            if token.startswith("-"):
                return (
                    f"Invalid ID {token!r}: token looks like an option.\n"
                    "In Python's argument parser, `--` means “everything after this is a positional ID”. "
                    "So `36403686 -- full_text ...` sends full_text (and more) to PubTator as PMIDs and "
                    "can trigger HTTP 400.\n"
                    "Use: `--field full_text` and `--annotator medcat` (double “t”), without a bare `--` "
                    "before field names."
                )
            if not token.isdigit():
                hint = ""
                if token in {"full_text", "abstract", "title", "annotations"}:
                    hint = f" Did you mean `--field {token}`?"
                return (
                    f"Invalid PMID {token!r}: PubMed IDs are numeric only.{hint}\n"
                    "If you used `--` before arguments, remove it so flags like `--field` are recognized."
                )
    elif input_kind in ("pmcid", "pmcid_list"):
        for token in raw_ids:
            if token.startswith("-"):
                return (
                    f"Invalid ID {token!r}: token looks like an option (see PMID validation message "
                    "about bare `--`)."
                )
            if not _is_plausible_pmcid(token):
                return (
                    f"Invalid PMCID {token!r}: expected e.g. PMC7083241 or 7083241.\n"
                    "If this was meant as a fetch field, use `--field`, not a positional argument."
                )
    return None


def _document_to_jsonable(doc: object) -> dict:
    from bio_annotation.schemas.document import Document

    if not isinstance(doc, Document):
        return {"error": "unexpected type", "type": type(doc).__name__}
    metadata = _clean_output_metadata(
        metadata=doc.metadata,
        title=doc.title,
        abstract=doc.abstract,
        year=doc.year,
    )
    return {
        "document_id": doc.document_id,
        "pmid": doc.pmid,
        "source": doc.source,
        "title": doc.title,
        "abstract": doc.abstract,
        "full_text": doc.full_text,
        "year": doc.year,
        "metadata": metadata,
    }


def _clean_output_metadata(
    *,
    metadata: dict[str, Any],
    title: str,
    abstract: str,
    year: str | None,
) -> dict[str, Any]:
    """Return display-friendly metadata without duplicate pubmed_record core fields."""

    out = dict(metadata) if isinstance(metadata, dict) else {}
    pubmed_record = out.get("pubmed_record")
    if not isinstance(pubmed_record, dict):
        return out

    pr = dict(pubmed_record)
    if _same_text(pr.get("title"), title):
        pr.pop("title", None)
    if _same_text(pr.get("abstract"), abstract):
        pr.pop("abstract", None)
    if _same_text(pr.get("year"), year):
        pr.pop("year", None)

    if pr:
        out["pubmed_record"] = pr
    else:
        out.pop("pubmed_record", None)
    return out


def _same_text(left: Any, right: Any) -> bool:
    return str(left or "").strip() == str(right or "").strip()


def _annotations_to_jsonable(annotations: list[object]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for annotation in annotations:
        to_dict = getattr(annotation, "to_dict", None)
        if callable(to_dict):
            out.append(to_dict())
    return out


def _document_for_pubtator_annotation(doc: object) -> object:
    """Prepare annotator text policy per source.

    For Europe PMC-backed documents, run PubTator3 on title+abstract+full_text
    together (user-requested behavior). For other sources, use the document as-is.
    """

    from bio_annotation.schemas.document import Document

    if not isinstance(doc, Document):
        return doc
    if doc.source != "europe_pmc":
        return doc

    chunks = [doc.title.strip(), doc.abstract.strip(), (doc.full_text or "").strip()]
    merged_text = "\n\n".join(part for part in chunks if part)
    return Document(
        document_id=doc.document_id,
        pmid=doc.pmid,
        title="",
        abstract=merged_text,
        full_text=None,
        source=doc.source,
        year=doc.year,
        metadata=dict(doc.metadata),
    )


def _document_for_pubtator_publication_fallback(doc: object) -> object:
    """Create a pubmed-shaped document so PubTator3 publication mode can run."""

    from bio_annotation.schemas.document import Document

    if not isinstance(doc, Document):
        return doc
    return Document(
        document_id=doc.document_id,
        pmid=doc.pmid,
        title=doc.title,
        abstract=doc.abstract,
        full_text=None,
        source="pubmed",
        year=doc.year,
        metadata=dict(doc.metadata),
    )


def _chunk_text(text: str, *, chunk_size: int = 6000, overlap: int = 300) -> list[tuple[int, str]]:
    cleaned = text or ""
    if not cleaned.strip():
        return []
    if chunk_size <= overlap:
        overlap = 0
    out: list[tuple[int, str]] = []
    start = 0
    length = len(cleaned)
    while start < length:
        end = min(length, start + chunk_size)
        chunk = cleaned[start:end]
        if chunk.strip():
            out.append((start, chunk))
        if end >= length:
            break
        start = end - overlap
    return out


def _shift_annotation_offsets(
    annotation: object,
    *,
    offset: int,
    document_id: str,
) -> object:
    from bio_annotation.entity_proposal._shared import build_annotation_id
    from bio_annotation.schemas.entity import Annotation

    if not isinstance(annotation, Annotation):
        return annotation
    start = annotation.start + offset if annotation.start is not None else None
    end = annotation.end + offset if annotation.end is not None else None
    return Annotation(
        annotation_id=build_annotation_id(
            source=annotation.source,
            document_id=document_id,
            span_text=annotation.span_text,
            entity_type=annotation.entity_type,
            start=start,
            end=end,
        ),
        source=annotation.source,
        span_text=annotation.span_text,
        start=start,
        end=end,
        entity_type=annotation.entity_type,
        canonical_id=annotation.canonical_id,
        canonical_name=annotation.canonical_name,
        confidence=annotation.confidence,
    )


def _annotate_pubtator3_chunked_full_text(
    doc: object,
    *,
    chunk_size: int = 6000,
    overlap: int = 300,
) -> list[dict[str, Any]]:
    """Chunk full text and merge PubTator3 text-only annotations with global offsets."""

    from bio_annotation.annotators.pubtator3 import annotate_with_pubtator3
    from bio_annotation.schemas.document import Document

    if not isinstance(doc, Document):
        return []
    chunks = _chunk_text(
        doc.get_text(prefer_full_text=True, include_title=True),
        chunk_size=chunk_size,
        overlap=overlap,
    )
    if not chunks:
        return []
    merged: list[object] = []
    seen: set[tuple[Any, ...]] = set()
    for idx, (offset, chunk_text) in enumerate(chunks, start=1):
        chunk_doc = Document(
            document_id=f"{doc.document_id}#chunk-{idx}",
            pmid=doc.pmid,
            title="",
            abstract=chunk_text,
            full_text=None,
            source=doc.source,
            year=doc.year,
            metadata={},
        )
        annotations = annotate_with_pubtator3(chunk_doc, mode="text_only")
        for annotation in annotations:
            shifted = _shift_annotation_offsets(
                annotation,
                offset=offset,
                document_id=doc.document_id,
            )
            key = (
                getattr(shifted, "source", None),
                getattr(shifted, "span_text", None),
                getattr(shifted, "entity_type", None),
                getattr(shifted, "start", None),
                getattr(shifted, "end", None),
                getattr(shifted, "canonical_id", None),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(shifted)
    return _annotations_to_jsonable(merged)


def _annotate_pubtator3_resilient(
    doc: object,
    *,
    chunk_size: int = 6000,
    chunk_overlap: int = 300,
) -> list[dict[str, Any]]:
    """Annotate with PubTator3 and gracefully fallback on slow text jobs."""

    from bio_annotation.annotators.pubtator3 import annotate_with_pubtator3, parse_pubtator3_response
    from bio_annotation.schemas.document import Document

    if not isinstance(doc, Document):
        return []

    payload = doc.metadata.get("pubtator3_payload") if isinstance(doc.metadata, dict) else None
    if payload is not None:
        return _annotations_to_jsonable(parse_pubtator3_response(doc, payload))

    annotation_doc = _document_for_pubtator_annotation(doc)
    try:
        return _annotations_to_jsonable(annotate_with_pubtator3(annotation_doc))
    except ValueError as exc:
        message = str(exc)
        if "not ready after" not in message:
            raise
        # Fallback 1: chunk long text into text-only requests and merge.
        chunked = _annotate_pubtator3_chunked_full_text(
            doc,
            chunk_size=chunk_size,
            overlap=chunk_overlap,
        )
        if chunked:
            return chunked
        if not doc.pmid:
            raise
        # Fallback: use PMID publication mode when long text polling times out.
        pubmed_doc = _document_for_pubtator_publication_fallback(doc)
        return _annotations_to_jsonable(
            annotate_with_pubtator3(pubmed_doc, mode="publication_only")
        )


def _field_catalog() -> dict[str, frozenset[str]]:
    from bio_annotation.fetch.fields import ENTREZ_FIELDS, EUROPE_PMC_FIELDS, PUBTATOR3_FIELDS

    return {
        "pubtator3": PUBTATOR3_FIELDS,
        "entrez": ENTREZ_FIELDS,
        "europe_pmc": EUROPE_PMC_FIELDS,
    }


def _print_field_catalog() -> None:
    catalog = _field_catalog()
    payload = {name: sorted(fields) for name, fields in catalog.items()}
    print(json.dumps(payload, indent=2))


def _load_script_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Config file not found: {path}")
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Invalid TOML in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a TOML table at root.")
    return raw


def _cfg_fetch_section(cfg: dict[str, Any]) -> dict[str, Any]:
    section = cfg.get("fetch", {})
    return section if isinstance(section, dict) else {}


def _cfg_annotators_enabled(cfg: dict[str, Any]) -> list[str] | None:
    section = cfg.get("annotators", {})
    if not isinstance(section, dict):
        return None
    value = section.get("enabled")
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError("annotators.enabled in config must be a list of strings.")
    out = [str(v).strip() for v in value if str(v).strip()]
    return out or None


def _cfg_medcat_endpoint(cfg: dict[str, Any]) -> str | None:
    section = cfg.get("annotators", {})
    if not isinstance(section, dict):
        return None
    medcat = section.get("medcat", {})
    if not isinstance(medcat, dict):
        return None
    endpoint = medcat.get("endpoint")
    if isinstance(endpoint, str) and endpoint.strip():
        return endpoint.strip()
    return None


def _cfg_flair_model(cfg: dict[str, Any]) -> str | None:
    section = cfg.get("annotators", {})
    if not isinstance(section, dict):
        return None
    flair = section.get("flair", {})
    if not isinstance(flair, dict):
        return None
    model = flair.get("model")
    if isinstance(model, str) and model.strip():
        return model.strip()
    return None


def _cfg_flair_include_raw(cfg: dict[str, Any]) -> bool | None:
    section = cfg.get("annotators", {})
    if not isinstance(section, dict):
        return None
    flair = section.get("flair", {})
    if not isinstance(flair, dict):
        return None
    val = flair.get("include_raw")
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    raise ValueError("annotators.flair.include_raw in config must be boolean.")


def _cfg_medcat_include_raw(cfg: dict[str, Any]) -> bool | None:
    section = cfg.get("annotators", {})
    if not isinstance(section, dict):
        return None
    medcat = section.get("medcat", {})
    if not isinstance(medcat, dict):
        return None
    val = medcat.get("include_raw")
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    raise ValueError("annotators.medcat.include_raw in config must be boolean.")


def _cfg_pubtator3_chunk_options(cfg: dict[str, Any]) -> tuple[int | None, int | None]:
    section = cfg.get("annotators", {})
    if not isinstance(section, dict):
        return None, None
    pub = section.get("pubtator3", {})
    if not isinstance(pub, dict):
        return None, None

    def _as_int(value: Any) -> int | None:
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return None

    return _as_int(pub.get("chunk_size")), _as_int(pub.get("chunk_overlap"))


def _effective_pubtator_chunk_params(
    *,
    cli_size: int | None,
    cli_overlap: int | None,
    cfg_size: int | None,
    cfg_overlap: int | None,
) -> tuple[int, int]:
    size = cli_size if cli_size is not None else (cfg_size if cfg_size is not None else 6000)
    overlap = cli_overlap if cli_overlap is not None else (cfg_overlap if cfg_overlap is not None else 300)
    if size < 256:
        raise ValueError("--pubtator-chunk-size must be at least 256.")
    if overlap < 0:
        raise ValueError("--pubtator-chunk-overlap must be non-negative.")
    if overlap >= size:
        raise ValueError("--pubtator-chunk-overlap must be smaller than --pubtator-chunk-size.")
    return size, overlap


def _resolve_fields(
    *,
    explicit_fields: list[str] | None,
    include_annotations: bool,
    sources: list[str],
    annotators: list[str] | None = None,
) -> tuple[frozenset[str] | None, dict[str, frozenset[str]] | None]:
    """Resolve global and per-source field filters.

    - If ``--field`` is provided, treat it as authoritative global selection.
    - Otherwise, for pubtator3, keep a lightweight default by excluding
      ``annotations`` unless ``--include-annotations`` is enabled.
    """

    annotator_set = {a.strip() for a in (annotators or []) if a and a.strip()}

    if explicit_fields:
        fields = frozenset(explicit_fields)
        return fields, None

    if "pubtator3" not in sources:
        return None, None

    catalog = _field_catalog()
    pubtator_fields = set(catalog["pubtator3"])
    # If pubtator3 annotator is requested, keep annotation payload from fetch so
    # we can parse it locally instead of creating a second remote text job.
    keep_annotations = include_annotations or ("pubtator3" in annotator_set)
    if not keep_annotations:
        pubtator_fields.discard("annotations")
    return None, {"pubtator3": frozenset(pubtator_fields)}


def _pubtator_default_fields(
    *,
    include_annotations: bool,
    annotators: list[str] | None,
) -> set[str]:
    catalog = _field_catalog()
    out = set(catalog["pubtator3"])
    annotator_set = {a.strip() for a in (annotators or []) if a and a.strip()}
    keep_annotations = include_annotations or ("pubtator3" in annotator_set)
    if not keep_annotations:
        out.discard("annotations")
    return out


def _resolve_sources_and_fields(
    *,
    explicit_sources: list[str] | None,
    explicit_fields: list[str] | None,
    include_annotations: bool,
    annotators: list[str] | None,
    strict_sources: bool,
) -> tuple[list[str], dict[str, frozenset[str]] | None, list[str], list[str]]:
    """Resolve final sources and per-source field filters.

    Rules:
    - If no source provided: start with pubtator3.
    - If no fields provided: keep current source behavior; for pubtator3 keep
      lightweight defaults via ``fields_per_source``.
    - If fields provided: keep pubtator defaults and add requested fields on
      owner sources. Missing owners are auto-added unless strict mode is on.
    """

    requested_sources = list(dict.fromkeys((explicit_sources or ["pubtator3"])))
    requested_fields = list(dict.fromkeys((explicit_fields or [])))
    catalog = _field_catalog()

    unresolved_fields: list[str] = []
    auto_added_sources: list[str] = []
    fields_per_source: dict[str, set[str]] = {}

    if "pubtator3" in requested_sources:
        fields_per_source["pubtator3"] = _pubtator_default_fields(
            include_annotations=include_annotations,
            annotators=annotators,
        )

    if not requested_fields:
        if fields_per_source:
            return (
                requested_sources,
                {k: frozenset(v) for k, v in fields_per_source.items()},
                unresolved_fields,
                auto_added_sources,
            )
        return requested_sources, None, unresolved_fields, auto_added_sources

    for field_name in requested_fields:
        owners = [name for name, values in catalog.items() if field_name in values]
        if not owners:
            unresolved_fields.append(field_name)
            continue
        for owner in owners:
            if owner not in requested_sources:
                if strict_sources:
                    continue
                requested_sources.append(owner)
                auto_added_sources.append(owner)
            if owner in requested_sources:
                fields_per_source.setdefault(owner, set()).add(field_name)

    if strict_sources:
        missing_for_strict = sorted(
            {
                field_name
                for field_name in requested_fields
                if field_name not in unresolved_fields
                and not any(
                    field_name in catalog.get(src, frozenset())
                    for src in requested_sources
                )
            }
        )
        if missing_for_strict:
            raise ValueError(
                "Requested fields are not available in selected --source values: "
                + ", ".join(missing_for_strict)
                + ". Remove --strict-sources to auto-add owner backends."
            )

    return (
        requested_sources,
        {k: frozenset(v) for k, v in fields_per_source.items()} if fields_per_source else None,
        unresolved_fields,
        auto_added_sources,
    )


def _load_flair_tagger(model: str) -> Any:
    from flair.nn import Classifier

    return Classifier.load(model)


def _run_annotators(
    *,
    annotators: list[str],
    documents: list[object],
    annotator_settings: dict[str, dict[str, Any]] | None = None,
    pubtator_chunk_size: int = 6000,
    pubtator_chunk_overlap: int = 300,
    include_medcat_raw: bool = False,
    include_flair_raw: bool = False,
) -> list[dict[str, Any]]:
    requested = list(dict.fromkeys(a.strip() for a in annotators if a and a.strip()))
    unsupported = [name for name in requested if name not in {"pubtator3", "medcat", "flair"}]
    if unsupported:
        raise ValueError(
            "Unsupported --annotator value(s): "
            + ", ".join(unsupported)
            + ". Supported: pubtator3, medcat, flair."
        )
    if not requested:
        return []

    from bio_annotation.annotators.flair import run_flair_on_document
    from bio_annotation.annotators.medcat import call_medcat, parse_medcat_response
    from bio_annotation.schemas.document import Document

    settings = annotator_settings or {}
    medcat_endpoint = settings.get("medcat", {}).get("endpoint")

    flair_tagger: Any | None = None
    flair_warned = False
    if "flair" in requested:
        flair_section = settings.get("flair", {})
        flair_model = (
            flair_section.get("model") if isinstance(flair_section, dict) else None
        ) or "hunflair2"
        if isinstance(flair_model, str) and flair_model.strip():
            flair_model = flair_model.strip()
        else:
            flair_model = "hunflair2"
        try:
            flair_tagger = _load_flair_tagger(flair_model)
        except ImportError as exc:
            print(
                f"Warning: Flair annotator skipped — install the ``flair`` package ({exc}).",
                file=sys.stderr,
            )
        except Exception as exc:
            print(
                f"Warning: Flair model {flair_model!r} failed to load: {exc}",
                file=sys.stderr,
            )

    out: list[dict[str, Any]] = []
    for doc in documents:
        if not isinstance(doc, Document):
            continue
        row: dict[str, Any] = {"document_id": doc.document_id, "results": {}}
        for name in requested:
            if name == "pubtator3":
                row["results"]["pubtator3"] = _annotate_pubtator3_resilient(
                    doc,
                    chunk_size=pubtator_chunk_size,
                    chunk_overlap=pubtator_chunk_overlap,
                )
            elif name == "medcat":
                ep = medcat_endpoint or os.getenv("MEDCAT_API_URL")
                if not ep:
                    print(
                        "Warning: MedCAT skipped — set MEDCAT_API_URL or "
                        "[annotators.medcat] endpoint in config (or use scripts/unified_fetch.cmd with .env).",
                        file=sys.stderr,
                    )
                    row["results"]["medcat"] = []
                else:
                    medcat_payload = call_medcat(doc, endpoint=ep)
                    annotations = (
                        parse_medcat_response(doc, medcat_payload)
                        if medcat_payload is not None
                        else []
                    )
                    row["results"]["medcat"] = _annotations_to_jsonable(annotations)
                    if include_medcat_raw:
                        row["results"]["medcat_raw"] = medcat_payload
                    text_len = len(doc.get_text())
                    if not annotations and text_len > 40:
                        print(
                            f"Warning: MedCAT returned no entities for {doc.document_id} "
                            f"(sent ~{text_len} chars to {ep!r}). "
                            "If the service is down or returns non-JSON, the client fails silently. "
                            "Check MEDCAT_API_URL, GET /api/info on the host, and Docker/logs for MedCATservice "
                            "(see docs/MEDCAT_GUIDE.md).",
                            file=sys.stderr,
                        )
            elif name == "flair":
                if flair_tagger is None:
                    if not flair_warned:
                        print(
                            "Warning: Flair annotator produced no results (model not loaded).",
                            file=sys.stderr,
                        )
                        flair_warned = True
                    row["results"]["flair"] = []
                else:
                    flair_ann, flair_snap = run_flair_on_document(
                        doc,
                        tagger=flair_tagger,
                        include_raw=include_flair_raw,
                    )
                    row["results"]["flair"] = _annotations_to_jsonable(flair_ann)
                    if include_flair_raw:
                        row["results"]["flair_raw"] = flair_snap
        out.append(row)
    return out


def main() -> int:
    _ensure_src_on_path()
    _load_repo_dotenv()
    normalized_argv = _normalize_cli_aliases(sys.argv[1:])
    args = _parse_args(normalized_argv)

    from bio_annotation.fetch.input import FetchInput
    from bio_annotation.fetch.orchestrator import default_fetch_orchestrator
    from bio_annotation.pipeline_config import SUPPORTED_FETCH_SOURCES

    if args.list_fields:
        _print_field_catalog()
        return 0

    cfg: dict[str, Any] = {}
    if args.config is not None:
        try:
            cfg = _load_script_config(args.config)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    fetch_cfg = _cfg_fetch_section(cfg)

    config_file = fetch_cfg.get("file")
    config_file_path = Path(config_file) if isinstance(config_file, str) and config_file.strip() else None
    effective_file = args.ids_file if args.ids_file is not None else config_file_path

    config_query = fetch_cfg.get("query")
    if config_query is not None and not isinstance(config_query, str):
        print("fetch.query in config must be a string.", file=sys.stderr)
        return 1
    effective_query = (
        args.query.strip() if isinstance(args.query, str) and args.query.strip() else None
    )
    if effective_query is None and isinstance(config_query, str) and config_query.strip():
        effective_query = config_query.strip()

    cfg_input_kind = fetch_cfg.get("input_kind")
    if cfg_input_kind is not None and not isinstance(cfg_input_kind, str):
        print("fetch.input_kind in config must be a string.", file=sys.stderr)
        return 1
    config_kind = cfg_input_kind.strip().lower() if isinstance(cfg_input_kind, str) and cfg_input_kind.strip() else None
    if config_kind and config_kind not in {"pmid", "pmid_list", "pmcid", "pmcid_list", "query"}:
        print(
            "fetch.input_kind must be one of: pmid, pmid_list, pmcid, pmcid_list, query.",
            file=sys.stderr,
        )
        return 1

    config_single_id = fetch_cfg.get("id")
    if config_single_id is not None and not isinstance(config_single_id, str):
        print("fetch.id in config must be a string.", file=sys.stderr)
        return 1
    single_from_cfg = config_single_id.strip() if isinstance(config_single_id, str) and config_single_id.strip() else None
    single_id = (
        args.single_id.strip()
        if isinstance(args.single_id, str) and args.single_id.strip()
        else None
    ) or single_from_cfg

    has_id_inputs = bool(
        effective_file is not None
        or bool(single_id)
        or any(str(p).strip() for p in args.ids if str(p).strip())
    )

    explicit_kind = args.input_kind or config_kind
    if explicit_kind:
        input_kind = explicit_kind
    elif effective_query and not has_id_inputs:
        input_kind = "query"
    else:
        input_kind = "pmid_list"

    if args.query and args.input_kind and args.input_kind != "query":
        print("--query cannot be combined with a non-query --input-kind.", file=sys.stderr)
        return 1
    if effective_query and config_kind and config_kind != "query" and not args.input_kind:
        print(
            "Config fetch.query is set but fetch.input_kind is not query; "
            'set fetch.input_kind = "query" or pass --input-kind query.',
            file=sys.stderr,
        )
        return 1
    if effective_query and has_id_inputs and input_kind != "query":
        print(
            "Warning: ignoring --query / fetch.query because ID inputs were provided.",
            file=sys.stderr,
        )
        effective_query = None

    if single_id and args.ids:
        print("Use either --id or positional IDs, not both.", file=sys.stderr)
        return 1
    if effective_file is not None and single_id:
        print("Do not combine --id with --ids-file/--file.", file=sys.stderr)
        return 1

    raw_ids: list[str] = []
    if effective_file is not None:
        if not effective_file.is_file():
            print(f"Not a file: {effective_file}", file=sys.stderr)
            return 1
        raw_ids = _load_ids_from_file(effective_file)
    elif single_id:
        raw_ids = [single_id]
    else:
        raw_ids = [p.strip() for p in args.ids if p.strip()]

    if input_kind == "query":
        if not effective_query:
            print("query input requires --query or fetch.query in config.", file=sys.stderr)
            return 1
        if raw_ids:
            print("Do not pass IDs with --input-kind query.", file=sys.stderr)
            return 1
    elif input_kind == "pmid":
        if len(raw_ids) != 1:
            print("--input-kind pmid requires exactly one PMID (--id or one positional).", file=sys.stderr)
            return 1
    elif input_kind == "pmcid":
        if len(raw_ids) != 1:
            print("--input-kind pmcid requires exactly one PMCID (--id or one positional).", file=sys.stderr)
            return 1
    elif not raw_ids:
        print(
            "Provide ID(s) as arguments, --id, or --ids-file/--file (not used for query input).",
            file=sys.stderr,
        )
        return 1

    id_err = _validate_id_tokens_for_input_kind(input_kind, raw_ids)
    if id_err:
        print(id_err, file=sys.stderr)
        return 1

    cfg_sources = fetch_cfg.get("source")
    config_sources: list[str] | None = None
    if isinstance(cfg_sources, str) and cfg_sources.strip():
        config_sources = [cfg_sources.strip()]
    elif isinstance(cfg_sources, list):
        config_sources = [str(x).strip() for x in cfg_sources if str(x).strip()] or None
    elif cfg_sources is not None:
        print("fetch.source in config must be a string or list of strings.", file=sys.stderr)
        return 1

    sources = args.source if args.source else (config_sources or ["pubtator3"])
    invalid = [s for s in sources if s not in SUPPORTED_FETCH_SOURCES]
    if invalid:
        print(
            f"Unsupported --source value(s): {invalid}. "
            f"Allowed: {', '.join(SUPPORTED_FETCH_SOURCES)}.",
            file=sys.stderr,
        )
        return 1
    if "raw_text" in sources:
        print("--source raw_text is not supported by this script (use pipeline or library).", file=sys.stderr)
        return 1

    cfg_fields = fetch_cfg.get("fields")
    config_fields: list[str] | None = None
    if isinstance(cfg_fields, list):
        config_fields = [str(x).strip() for x in cfg_fields if str(x).strip()] or None
    elif cfg_fields is not None:
        print("fetch.fields in config must be a list of strings.", file=sys.stderr)
        return 1
    effective_fields = args.field if args.field else config_fields

    cfg_include = fetch_cfg.get("include_annotations")
    if cfg_include is not None and not isinstance(cfg_include, bool):
        print("fetch.include_annotations in config must be boolean.", file=sys.stderr)
        return 1
    include_annotations = args.include_annotations if args.include_annotations is not None else bool(cfg_include)

    cfg_strict = fetch_cfg.get("strict_sources")
    if cfg_strict is not None and not isinstance(cfg_strict, bool):
        print("fetch.strict_sources in config must be boolean.", file=sys.stderr)
        return 1
    strict_sources = args.strict_sources if args.strict_sources is not None else bool(cfg_strict)

    config_annotators = _cfg_annotators_enabled(cfg)
    effective_annotators = args.annotator if args.annotator else config_annotators

    try:
        sources, fields_per_source, unresolved_fields, auto_added_sources = _resolve_sources_and_fields(
            explicit_sources=sources,
            explicit_fields=effective_fields,
            include_annotations=include_annotations,
            annotators=effective_annotators,
            strict_sources=strict_sources,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if unresolved_fields:
        print(
            "Warning: unknown/unsupported field name(s): "
            + ", ".join(sorted(unresolved_fields)),
            file=sys.stderr,
        )
    if auto_added_sources:
        print(
            "Info: auto-added source(s) for requested fields: "
            + ", ".join(auto_added_sources),
            file=sys.stderr,
        )

    try:
        if input_kind == "query":
            if not effective_query:
                print("query input requires --query or fetch.query in config.", file=sys.stderr)
                return 1
            request = FetchInput.from_query(
                effective_query,
                fields=None,
                fields_per_source=fields_per_source,
            )
        elif input_kind == "pmid":
            request = FetchInput.from_pmid(
                raw_ids[0],
                fields=None,
                fields_per_source=fields_per_source,
            )
        elif input_kind == "pmid_list":
            request = FetchInput.from_pmid_list(
                raw_ids,
                fields=None,
                fields_per_source=fields_per_source,
            )
        elif input_kind == "pmcid":
            request = FetchInput.from_pmcid(
                raw_ids[0],
                fields=None,
                fields_per_source=fields_per_source,
            )
        elif input_kind == "pmcid_list":
            request = FetchInput.from_pmcid_list(
                raw_ids,
                fields=None,
                fields_per_source=fields_per_source,
            )
        else:
            print(f"Unsupported input kind: {input_kind}", file=sys.stderr)
            return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    cfg_chunk_size, cfg_chunk_overlap = _cfg_pubtator3_chunk_options(cfg)
    try:
        pubtator_chunk_size, pubtator_chunk_overlap = _effective_pubtator_chunk_params(
            cli_size=args.pubtator_chunk_size,
            cli_overlap=args.pubtator_chunk_overlap,
            cfg_size=cfg_chunk_size,
            cfg_overlap=cfg_chunk_overlap,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    orch = default_fetch_orchestrator()
    prefer: str | list[str] = sources[0] if len(sources) == 1 else list(sources)
    documents = orch.fetch(request, prefer=prefer)
    _warn_if_full_text_missing(
        documents,
        explicit_fields=effective_fields,
        fields_per_source=fields_per_source,
    )
    payload: dict[str, Any] = {
        "input_kind": input_kind,
        "sources": sources,
        "documents": [_document_to_jsonable(d) for d in documents],
    }
    if input_kind == "query" and effective_query:
        payload["query"] = effective_query
    annotator_settings: dict[str, dict[str, Any]] = {}
    medcat_endpoint = _cfg_medcat_endpoint(cfg)
    if medcat_endpoint:
        annotator_settings["medcat"] = {"endpoint": medcat_endpoint}

    effective_annotators_list = effective_annotators or []
    if effective_annotators_list and "flair" in effective_annotators_list:
        flair_model_cfg = _cfg_flair_model(cfg)
        flair_model_arg = (
            args.flair_model.strip()
            if isinstance(args.flair_model, str) and args.flair_model.strip()
            else None
        )
        flair_model = flair_model_arg or flair_model_cfg or "hunflair2"
        annotator_settings["flair"] = {"model": flair_model}

    try:
        cfg_medcat_include_raw = _cfg_medcat_include_raw(cfg)
        cfg_flair_include_raw = _cfg_flair_include_raw(cfg)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    include_medcat_raw = bool(args.medcat_raw) or (cfg_medcat_include_raw is True)
    include_flair_raw = bool(args.flair_raw) or (cfg_flair_include_raw is True)

    if effective_annotators:
        try:
            payload["annotators"] = _run_annotators(
                annotators=effective_annotators,
                documents=documents,
                annotator_settings=annotator_settings,
                pubtator_chunk_size=pubtator_chunk_size,
                pubtator_chunk_overlap=pubtator_chunk_overlap,
                include_medcat_raw=include_medcat_raw,
                include_flair_raw=include_flair_raw,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
