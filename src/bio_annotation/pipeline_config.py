from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


SUPPORTED_ENRICHMENT_SOURCES = [
    "elinks",
    "crossref",
    "europe_pmc",
    "semantic_scholar",
    "unpaywall",
    "biorxiv",
]
DEFAULT_ENRICHMENT_SOURCES: list[str] = []


@dataclass(frozen=True)
class PipelineConfig:
    input_mode: str
    pmids: list[str]
    pmid_file: Path | None
    text_file: Path | None
    text_format: str
    document_id_column: str
    title_column: str
    abstract_column: str
    corpus_path: Path | None
    enrichment_sources: list[str]
    annotators: list[str]
    entity_types: list[str]
    output_path: Path | None


def load_pipeline_config(path: Path) -> PipelineConfig:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))

    input_config = raw.get("input", {})
    enrichment_config = raw.get("enrichment", {})
    annotator_config = raw.get("annotators", {})
    filter_config = raw.get("filters", {})
    output_config = raw.get("output", {})

    if not isinstance(input_config, dict):
        raise ValueError(f"{path} is missing a valid [input] table.")
    if not isinstance(enrichment_config, dict):
        raise ValueError(f"{path} has an invalid [enrichment] table.")
    if not isinstance(annotator_config, dict):
        raise ValueError(f"{path} is missing a valid [annotators] table.")
    if not isinstance(filter_config, dict):
        raise ValueError(f"{path} has an invalid [filters] table.")
    if not isinstance(output_config, dict):
        raise ValueError(f"{path} has an invalid [output] table.")

    input_mode = _read_input_mode(input_config)
    pmids = _read_string_list(input_config.get("pmids"), field_name="input.pmids", allow_empty=True)
    pmid_file = _read_optional_path(input_config.get("pmid_file"))
    text_file = _read_optional_path(input_config.get("text_file"))
    text_format = _read_optional_string(input_config.get("format")) or "csv"
    document_id_column = _read_optional_string(input_config.get("document_id_column")) or "document_id"
    title_column = _read_optional_string(input_config.get("title_column")) or "title"
    abstract_column = _read_optional_string(input_config.get("abstract_column")) or "abstract"
    corpus_path_value = input_config.get("corpus_path")
    corpus_path = Path(corpus_path_value) if isinstance(corpus_path_value, str) and corpus_path_value.strip() else None
    enrichment_sources = _read_enrichment_sources(enrichment_config.get("sources"))
    annotators = _read_string_list(
        annotator_config.get("enabled"),
        field_name="annotators.enabled",
        allow_empty=True,
    )
    entity_types = _read_string_list(filter_config.get("entity_types"), field_name="filters.entity_types", allow_empty=True)
    output_path_value = output_config.get("path")
    output_path = Path(output_path_value) if isinstance(output_path_value, str) and output_path_value.strip() else None

    _validate_input_config(
        path,
        input_mode=input_mode,
        pmids=pmids,
        pmid_file=pmid_file,
        text_file=text_file,
        corpus_path=corpus_path,
    )
    return PipelineConfig(
        input_mode=input_mode,
        pmids=pmids,
        pmid_file=pmid_file,
        text_file=text_file,
        text_format=text_format,
        document_id_column=document_id_column,
        title_column=title_column,
        abstract_column=abstract_column,
        corpus_path=corpus_path,
        enrichment_sources=enrichment_sources,
        annotators=annotators,
        entity_types=entity_types,
        output_path=output_path,
    )


def _read_string_list(value: object, *, field_name: str, allow_empty: bool = False) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list of strings.")

    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name} contains an invalid value: {item!r}")
        cleaned = item.strip()
        if cleaned not in seen:
            seen.add(cleaned)
            out.append(cleaned)

    if not allow_empty and not out:
        raise ValueError(f"{field_name} must not be empty.")
    return out


def _read_optional_path(value: object) -> Path | None:
    cleaned = _read_optional_string(value)
    return Path(cleaned) if cleaned is not None else None


def _read_optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Expected a string value, got {value!r}.")
    cleaned = value.strip()
    return cleaned or None


def _read_enrichment_sources(value: object) -> list[str]:
    if value is None:
        return list(DEFAULT_ENRICHMENT_SOURCES)
    sources = _read_string_list(value, field_name="enrichment.sources", allow_empty=True)
    invalid = [source for source in sources if source not in SUPPORTED_ENRICHMENT_SOURCES]
    if invalid:
        raise ValueError(
            "enrichment.sources contains unsupported values: "
            + ", ".join(invalid)
        )
    return sources


def _read_input_mode(input_config: dict[str, object]) -> str:
    raw_mode = input_config.get("mode")
    if raw_mode is None:
        if input_config.get("pmid_file") is not None:
            return "pmid_file"
        if input_config.get("text_file") is not None:
            return "text_table"
        if input_config.get("corpus_path") is not None:
            return "corpus"
        return "pmids"
    if not isinstance(raw_mode, str) or not raw_mode.strip():
        raise ValueError("input.mode must be a non-empty string.")
    return raw_mode.strip().lower()


def _validate_input_config(
    path: Path,
    *,
    input_mode: str,
    pmids: list[str],
    pmid_file: Path | None,
    text_file: Path | None,
    corpus_path: Path | None,
) -> None:
    if input_mode == "pmids":
        if not pmids:
            raise ValueError(f"{path} must define input.pmids when input.mode = 'pmids'.")
        return
    if input_mode == "pmid_file":
        if pmid_file is None:
            raise ValueError(f"{path} must define input.pmid_file when input.mode = 'pmid_file'.")
        return
    if input_mode == "text_table":
        if text_file is None:
            raise ValueError(f"{path} must define input.text_file when input.mode = 'text_table'.")
        return
    if input_mode == "corpus":
        if corpus_path is None:
            raise ValueError(f"{path} must define input.corpus_path when input.mode = 'corpus'.")
        return
    raise ValueError(f"{path} has unsupported input.mode {input_mode!r}.")
