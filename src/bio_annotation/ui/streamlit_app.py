"""Streamlit shell for the unified TotalAnnotator fetch pipeline.

Launch with::

    uv run streamlit run src/bio_annotation/ui/streamlit_app.py

The app lets the user pick an input (single PMID, PMID list, single PMCID,
PMCID list, PubMed query, or raw text), choose how to dispatch it (auto,
single source, or chain across sources), optionally trim the Entrez fields
that get fetched, run the request, and inspect the resulting Documents.

This module is intentionally a thin wiring layer over
:class:`FetchOrchestrator` and the helpers in :mod:`bio_annotation.ui.inputs`
so the bulk of the logic stays unit-testable. UI behaviour itself should be
validated by running the app locally.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import streamlit as st

from bio_annotation.orchestrator import FetchOrchestrator, SourceNotFoundError
from bio_annotation.schemas.document import Document
from bio_annotation.sources import (
    EntrezSource,
    EuropePmcSource,
    PubTator3Source,
    RawTextSource,
)
from bio_annotation.sources.base import FetchInput, UnsupportedInputError
from bio_annotation.ui.inputs import (
    INPUT_MODE_LABELS,
    InputMode,
    build_fetch_input,
)


SOURCE_DESCRIPTIONS: dict[str, str] = {
    "europe_pmc": "Europe PMC: citation counts, OA flags, full-text URLs.",
    "entrez": "NCBI E-utilities: rich PubMed metadata (MeSH, journal, authors).",
    "pubtator3": "PubTator3: title, abstract, and pre-computed entity annotations.",
    "raw_text": "Raw text wrapper: no network call, used with pasted text.",
}


@st.cache_resource(show_spinner=False)
def _build_default_orchestrator() -> FetchOrchestrator:
    """Construct one orchestrator per Streamlit session.

    Streamlit reruns the script on every interaction, so without
    ``cache_resource`` the HTTP clients (and their connection pools) would
    be rebuilt on every keystroke.
    """

    return FetchOrchestrator(
        sources=[
            EuropePmcSource(),
            EntrezSource(),
            PubTator3Source(),
            RawTextSource(),
        ]
    )


def _select_input_mode() -> InputMode:
    label = st.sidebar.radio(
        "Input mode",
        options=list(INPUT_MODE_LABELS.values()),
        index=0,
    )
    inverse = {v: k for k, v in INPUT_MODE_LABELS.items()}
    return inverse[label]


def _render_input_widget(mode: InputMode) -> dict[str, str]:
    """Render the right widget for the chosen mode and return its raw values."""

    values: dict[str, str] = {
        "single_pmid": "",
        "pmid_list_text": "",
        "single_pmcid": "",
        "pmcid_list_text": "",
        "query": "",
        "raw_text": "",
        "raw_text_id": "RAW:1",
    }
    if mode == "pmid":
        values["single_pmid"] = st.text_input("PMID", value="36403686")
    elif mode == "pmid_list":
        values["pmid_list_text"] = st.text_area(
            "PMIDs (comma, space, or newline separated)",
            value="36403686\n33473926\n32296168",
            height=140,
        )
    elif mode == "pmcid":
        values["single_pmcid"] = st.text_input(
            "PMCID (PMC prefix optional)",
            value="PMC7156099",
        )
    elif mode == "pmcid_list":
        values["pmcid_list_text"] = st.text_area(
            "PMCIDs (comma, space, or newline separated)",
            value="PMC7156099\nPMC7857391",
            height=140,
        )
    elif mode == "query":
        values["query"] = st.text_input(
            "PubMed / Europe PMC query",
            value="microRNA AND glioblastoma",
        )
    elif mode == "raw_text":
        values["raw_text"] = st.text_area(
            "Paste your text",
            value=(
                "Glioblastoma is the most common primary brain tumor. "
                "PTEN and TP53 mutations drive disease progression."
            ),
            height=200,
        )
        values["raw_text_id"] = st.text_input(
            "Document ID (optional)",
            value="RAW:1",
        )
    return values


def _select_dispatch(
    orchestrator: FetchOrchestrator,
    request_kind: str,
) -> tuple[str | list[str] | None, list[str]]:
    """Return ``(prefer, available_source_names_for_kind)``."""

    available = [
        s.name for s in orchestrator.sources if request_kind in s.supported_inputs
    ]
    st.sidebar.markdown("### Source")
    if not available:
        st.sidebar.error(
            f"No registered source supports input kind {request_kind!r}."
        )
        return None, available

    dispatch = st.sidebar.radio(
        "Dispatch mode",
        options=["Auto", "Single source", "Chain (merge)"],
        index=0,
        help=(
            "Auto: use the first source that supports your input. "
            "Single: pick exactly one. "
            "Chain: run several and merge metadata per Document."
        ),
    )

    if dispatch == "Auto":
        return None, available
    if dispatch == "Single source":
        chosen = st.sidebar.selectbox("Source", options=available)
        st.sidebar.caption(SOURCE_DESCRIPTIONS.get(chosen, ""))
        return chosen, available
    chain = st.sidebar.multiselect(
        "Sources (run in order, results merged by document_id)",
        options=available,
        default=available,
    )
    return list(chain), available


_FIELD_FILTERABLE_SOURCES: tuple[tuple[str, str, str], ...] = (
    (
        "entrez",
        "Entrez fields",
        "Fields to keep in metadata['pubmed_record']",
    ),
    (
        "europe_pmc",
        "Europe PMC fields",
        "Fields to keep in metadata (epmc_meta is always preserved)",
    ),
)


def _will_source_run(
    source_name: str,
    prefer: str | list[str] | None,
) -> bool:
    if prefer is None:
        return True
    if isinstance(prefer, str):
        return prefer == source_name
    return source_name in prefer


def _render_source_fields_filter(
    orchestrator: FetchOrchestrator,
    source_name: str,
    section_title: str,
    multiselect_label: str,
    prefer: str | list[str] | None,
) -> frozenset[str] | None:
    """Show one source-specific fields multiselect when that source will run."""

    try:
        source = orchestrator.get(source_name)
    except SourceNotFoundError:
        return None
    if not _will_source_run(source_name, prefer):
        return None
    if not source.fields_provided:
        return None

    st.sidebar.markdown(f"### {section_title}")
    all_fields = sorted(source.fields_provided)
    chosen = st.sidebar.multiselect(
        multiselect_label,
        options=all_fields,
        default=all_fields,
        key=f"fields_{source_name}",
        help=(
            "Starts with every field selected. Remove any you do not need; "
            "core fields (pmid, title, abstract, year) are always kept. "
            "If you remove everything, only the core fields remain."
        ),
    )
    if set(chosen) == set(all_fields):
        return None
    return frozenset(chosen)


def _render_all_fields_filters(
    orchestrator: FetchOrchestrator,
    prefer: str | list[str] | None,
) -> dict[str, frozenset[str]] | None:
    """Render one multiselect per filterable source and return their slices.

    Returns ``None`` when no source had its fields trimmed (so no per-source
    override is sent and every source returns its full field set). Otherwise
    returns ``{source_name: frozenset_of_kept_fields}`` for **only** the
    sources whose multiselects were actually narrowed. Sources not in the
    returned dict keep all their fields, just as before.

    This dict is plumbed into :class:`FetchInput.fields_per_source` so each
    source independently filters using its own slice. Strict per-source
    semantics: dropping ``mesh_terms`` from Entrez no longer affects
    EuropePMC and vice versa.
    """

    overrides: dict[str, frozenset[str]] = {}
    for source_name, section_title, label in _FIELD_FILTERABLE_SOURCES:
        chosen = _render_source_fields_filter(
            orchestrator,
            source_name,
            section_title,
            label,
            prefer,
        )
        if chosen is not None:
            overrides[source_name] = chosen

    return overrides or None


def _extract_journal(meta: dict[str, Any]) -> str:
    """Pull a journal title out of whichever source's metadata is present."""

    pubmed = meta.get("pubmed_record") or {}
    if isinstance(pubmed, dict) and pubmed.get("journal"):
        return str(pubmed["journal"])
    epmc = meta.get("epmc_meta") or {}
    if isinstance(epmc, dict):
        for key in ("journalTitle", "journalInfo"):
            value = epmc.get(key)
            if isinstance(value, str) and value:
                return value
            if isinstance(value, dict):
                title = value.get("journal", {}).get("title") if isinstance(
                    value.get("journal"), dict
                ) else None
                if title:
                    return str(title)
    return ""


def _count_authors(meta: dict[str, Any]) -> int | str:
    pubmed = meta.get("pubmed_record") or {}
    authors = pubmed.get("authors") if isinstance(pubmed, dict) else None
    if isinstance(authors, list):
        return len(authors)
    epmc = meta.get("epmc_meta") or {}
    if isinstance(epmc, dict):
        author_list = epmc.get("authorList")
        if isinstance(author_list, dict):
            inner = author_list.get("author")
            if isinstance(inner, list):
                return len(inner)
    return ""


def _count_list_field(meta: dict[str, Any], key: str) -> int | str:
    pubmed = meta.get("pubmed_record") or {}
    if isinstance(pubmed, dict):
        value = pubmed.get(key)
        if isinstance(value, list):
            return len(value)
    return ""


def _summary_row(doc: Document) -> dict[str, Any]:
    meta = doc.metadata or {}
    title = doc.title or ""
    return {
        "document_id": doc.document_id,
        "source(s)": ", ".join(meta.get("origin_sources", [doc.source])),
        "pmid": doc.pmid or "",
        "pmcid": meta.get("pmcid", "") or "",
        "doi": meta.get("doi", "") or "",
        "year": doc.year or "",
        "title": (title[:140] + "...") if len(title) > 140 else title,
        "abstract_chars": len(doc.abstract or ""),
        "has_full_text": bool(doc.full_text),
        "full_text_chars": len(doc.full_text or "") if doc.full_text else 0,
        "is_open_access": meta.get("is_open_access", ""),
        "in_epmc": meta.get("in_epmc", ""),
        "citation_count": meta.get("citation_count", ""),
        "license": meta.get("license", "") or "",
        "journal": _extract_journal(meta),
        "n_authors": _count_authors(meta),
        "n_mesh": _count_list_field(meta, "mesh_terms"),
        "n_keywords": _count_list_field(meta, "keywords"),
        "n_chemicals": _count_list_field(meta, "chemicals"),
    }


def _stringify(value: Any) -> Any:
    """Make nested dicts/lists safe for a flat dataframe column."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def _flat_row(doc: Document) -> dict[str, Any]:
    """One row with every Document field + every metadata key as its own column."""

    meta = doc.metadata or {}
    row: dict[str, Any] = {
        "document_id": doc.document_id,
        "pmid": doc.pmid or "",
        "title": doc.title or "",
        "abstract": doc.abstract or "",
        "full_text": doc.full_text or "",
        "source": doc.source,
        "year": doc.year or "",
    }
    for key, value in meta.items():
        row[f"meta.{key}"] = _stringify(value)
    return row


def _render_results(documents: list[Document]) -> None:
    if not documents:
        st.warning("No documents returned.")
        return

    st.success(f"Fetched {len(documents)} document(s).")

    flatten = st.checkbox(
        "Flatten all metadata into columns",
        value=False,
        help=(
            "Off: compact summary (DOI, PMCID, OA, citation count, journal, "
            "author/MeSH counts, ...). "
            "On: every Document field + every metadata key gets its own column "
            "(nested values are JSON-stringified)."
        ),
    )

    rows = [_flat_row(d) if flatten else _summary_row(d) for d in documents]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption(
        f"Columns: {len(rows[0]) if rows else 0}. "
        "Use the **Per-document detail** below to drill into a single Document."
    )

    st.markdown("---")
    st.markdown("### Per-document detail")
    for doc in documents:
        with st.expander(f"{doc.document_id} - {doc.title or '(no title)'}"):
            st.markdown(
                f"**Source(s):** `{', '.join(doc.metadata.get('origin_sources', [doc.source]))}`"
            )
            if doc.year:
                st.markdown(f"**Year:** {doc.year}")
            if doc.abstract:
                st.markdown("**Abstract:**")
                st.write(doc.abstract)
            if doc.full_text:
                st.markdown("**Full text:**")
                st.text_area(
                    "full_text",
                    value=doc.full_text,
                    height=240,
                    label_visibility="collapsed",
                )
            st.markdown("**Metadata:**")
            st.json(_safe_metadata(doc), expanded=False)


def _safe_metadata(doc: Document) -> dict[str, Any]:
    """Convert the Document to a JSON-serialisable dict for st.json."""

    payload = asdict(doc)
    return payload


def main() -> None:
    st.set_page_config(
        page_title="TotalAnnotator - unified fetcher",
        layout="wide",
    )
    st.title("TotalAnnotator: unified fetcher")
    st.caption(
        "Choose an input, pick a source (or chain several), and fetch. "
        "Built on top of the EntrezSource, EuropePmcSource, PubTator3Source, "
        "and RawTextSource pluggable adapters."
    )

    orchestrator = _build_default_orchestrator()

    st.sidebar.markdown("## Request")
    mode = _select_input_mode()
    raw_values = _render_input_widget(mode)
    prefer, available = _select_dispatch(orchestrator, request_kind=mode)
    fields_per_source = _render_all_fields_filters(orchestrator, prefer)

    st.sidebar.markdown("---")
    run = st.sidebar.button("Run fetch", type="primary", use_container_width=True)

    if not run:
        st.info(
            "Configure your request in the sidebar and click **Run fetch**. "
            "Available sources for the chosen mode: "
            f"`{', '.join(available) if available else '(none)'}`."
        )
        return

    try:
        request = build_fetch_input(
            mode=mode,
            fields_per_source=fields_per_source,
            **raw_values,
        )
    except ValueError as exc:
        st.error(str(exc))
        return

    if isinstance(prefer, list) and not prefer:
        st.error("Select at least one source for chain mode, or switch to Auto.")
        return

    with st.spinner("Fetching..."):
        try:
            documents = orchestrator.fetch(request, prefer=prefer)
        except UnsupportedInputError as exc:
            st.error(str(exc))
            return
        except Exception as exc:
            st.exception(exc)
            return

    _render_results(documents)


if __name__ == "__main__":
    main()
