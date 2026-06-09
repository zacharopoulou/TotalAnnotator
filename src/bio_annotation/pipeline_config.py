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

SUPPORTED_FETCH_SOURCES = ["pubtator3", "entrez", "europe_pmc"]
SUPPORTED_FETCH_FIELDS_BY_SOURCE = {
    "pubtator3": frozenset(
        {
            "pmid",
            "pmcid",
            "title",
            "abstract",
            "full_text",
            "annotations",
        }
    ),
    "entrez": frozenset(
        {
            "pmid",
            "pmcid",
            "doi",
            "title",
            "abstract",
            "structured_abstract",
            "year",
            "authors",
            "affiliations",
            "journal",
            "journal_abbrev",
            "volume",
            "issue",
            "pages",
            "language",
            "publication_type",
            "country",
            "pub_date",
            "epub_date",
            "received_date",
            "accepted_date",
            "medline_date",
            "entrez_date",
            "revision_date",
            "keywords",
            "mesh_terms",
            "chemicals",
            "gene_symbols",
            "supplemental_mesh",
            "grants",
            "elinks",
        }
    ),
    "europe_pmc": frozenset(
        {
            "pmid",
            "pmcid",
            "doi",
            "title",
            "abstract",
            "year",
            "authors",
            "journal",
            "mesh_terms",
            "keywords",
            "is_open_access",
            "in_epmc",
            "citation_count",
            "full_text_urls",
            "full_text",
            "license",
        }
    ),
}


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
    annotator_settings: dict[str, dict[str, object]]
    entity_types: list[str]
    output_path: Path | None
    fetch_sources: list[str]
    fetch_fields: list[str] | None
    fetch_fields_per_source: dict[str, list[str]] | None
    pubtator3_full_text: bool


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
    annotator_settings = _read_annotator_settings(annotator_config)
    entity_types = _read_string_list(filter_config.get("entity_types"), field_name="filters.entity_types", allow_empty=True)
    output_path_value = output_config.get("path")
    output_path = Path(output_path_value) if isinstance(output_path_value, str) and output_path_value.strip() else None

    fetch_sources = _read_fetch_sources(input_config.get("source"))
    fetch_fields = _read_optional_string_list(
        input_config.get("fields"),
        field_name="input.fields",
    )
    fetch_fields_per_source = _read_fields_per_source(input_config.get("fields_per_source"))
    _validate_fetch_fields(
        fetch_sources=fetch_sources,
        fetch_fields=fetch_fields,
        fetch_fields_per_source=fetch_fields_per_source,
    )
    pubtator3_full_text = _read_pubtator3_full_text(input_config.get("pubtator3"))

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
        annotator_settings=annotator_settings,
        entity_types=entity_types,
        output_path=output_path,
        fetch_sources=fetch_sources,
        fetch_fields=fetch_fields,
        fetch_fields_per_source=fetch_fields_per_source,
        pubtator3_full_text=pubtator3_full_text,
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


def _read_fetch_sources(value: object) -> list[str]:
    """Parse input.source: missing -> [] (loader defaults to pubtator3), str -> one source, list -> chain."""

    if value is None:
        return []
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return []
        items = [cleaned]
    elif isinstance(value, list):
        items = _read_string_list(value, field_name="input.source", allow_empty=True)
    else:
        raise ValueError(
            "input.source must be a string or a list of strings (got "
            f"{type(value).__name__})."
        )
    invalid = [name for name in items if name not in SUPPORTED_FETCH_SOURCES]
    if invalid:
        raise ValueError(
            "input.source contains unsupported values: "
            + ", ".join(invalid)
            + f". Supported: {', '.join(SUPPORTED_FETCH_SOURCES)}."
        )
    return items


def _read_optional_string_list(value: object, *, field_name: str) -> list[str] | None:
    if value is None:
        return None
    return _read_string_list(value, field_name=field_name, allow_empty=True)


def _read_fields_per_source(value: object) -> dict[str, list[str]] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(
            "input.fields_per_source must be a table mapping source names to lists of fields."
        )
    cleaned: dict[str, list[str]] = {}
    for source_name, fields_value in value.items():
        if not isinstance(source_name, str) or not source_name.strip():
            raise ValueError("input.fields_per_source contains an invalid source name.")
        normalized_name = source_name.strip()
        if normalized_name not in SUPPORTED_FETCH_SOURCES:
            raise ValueError(
                f"input.fields_per_source.{normalized_name} is not a supported source. "
                f"Supported: {', '.join(SUPPORTED_FETCH_SOURCES)}."
            )
        cleaned[normalized_name] = _read_string_list(
            fields_value,
            field_name=f"input.fields_per_source.{normalized_name}",
            allow_empty=True,
        )
    return cleaned or None


def _validate_fetch_fields(
    *,
    fetch_sources: list[str],
    fetch_fields: list[str] | None,
    fetch_fields_per_source: dict[str, list[str]] | None,
) -> None:
    if fetch_fields is not None:
        active_sources = fetch_sources or ["pubtator3"]
        supported = set().union(
            *(SUPPORTED_FETCH_FIELDS_BY_SOURCE[source] for source in active_sources)
        )
        _reject_unknown_fetch_fields(
            fetch_fields,
            supported=supported,
            field_name="input.fields",
        )

    if fetch_fields_per_source is None:
        return
    for source_name, fields in fetch_fields_per_source.items():
        _reject_unknown_fetch_fields(
            fields,
            supported=SUPPORTED_FETCH_FIELDS_BY_SOURCE[source_name],
            field_name=f"input.fields_per_source.{source_name}",
        )


def _reject_unknown_fetch_fields(
    fields: list[str],
    *,
    supported: frozenset[str] | set[str],
    field_name: str,
) -> None:
    invalid = [field for field in fields if field not in supported]
    if invalid:
        raise ValueError(
            f"{field_name} contains unsupported values: "
            + ", ".join(invalid)
            + f". Supported: {', '.join(sorted(supported))}."
        )


def _read_pubtator3_full_text(value: object) -> bool:
    """Parse [input.pubtator3].full_text: default False, must be bool when present."""

    if value is None:
        return False
    if not isinstance(value, dict):
        raise ValueError("[input.pubtator3] must be a table.")
    raw = value.get("full_text")
    if raw is None:
        return False
    if not isinstance(raw, bool):
        raise ValueError("[input.pubtator3].full_text must be a boolean.")
    return raw


def _read_annotator_settings(annotator_config: dict[str, object]) -> dict[str, dict[str, object]]:
    settings: dict[str, dict[str, object]] = {}
    for name, value in annotator_config.items():
        if name == "enabled":
            continue
        if not isinstance(name, str) or not name.strip():
            raise ValueError("annotators contains an invalid annotator key.")
        if not isinstance(value, dict):
            raise ValueError(f"annotators.{name} must be a table.")
        settings[name.strip().lower()] = _sanitize_annotator_table(name.strip(), value)
    return settings


def _sanitize_annotator_table(name: str, value: dict[str, object]) -> dict[str, object]:
    cleaned: dict[str, object] = {}
    for field, field_value in value.items():
        if not isinstance(field, str) or not field.strip():
            raise ValueError(f"annotators.{name} contains an invalid key.")
        cleaned[field.strip()] = _sanitize_annotator_value(name, field.strip(), field_value)
    return cleaned


def _sanitize_annotator_value(name: str, field: str, value: object) -> object:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        cleaned_list: list[object] = []
        for item in value:
            if not isinstance(item, (str, int, float, bool)):
                raise ValueError(f"annotators.{name}.{field} contains an unsupported value: {item!r}")
            cleaned_list.append(item)
        return cleaned_list
    raise ValueError(f"annotators.{name}.{field} contains an unsupported value: {value!r}")


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
