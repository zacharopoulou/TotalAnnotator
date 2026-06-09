from __future__ import annotations

from pathlib import Path

import pytest

from bio_annotation.pipeline_config import (
    SUPPORTED_FETCH_SOURCES,
    load_pipeline_config,
)


def _write_toml(tmp_path: Path, body: str) -> Path:
    config_path = tmp_path / "pipeline.toml"
    config_path.write_text(body, encoding="utf-8")
    return config_path


_BASE = """
[input]
mode = "pmids"
pmids = ["12345678"]
"""


# A. input.source

def test_source_omitted_yields_empty_list(tmp_path: Path) -> None:
    config = load_pipeline_config(_write_toml(tmp_path, _BASE))
    assert config.fetch_sources == []


def test_source_as_string_becomes_one_element_list(tmp_path: Path) -> None:
    body = _BASE + 'source = "pubtator3"\n'
    config = load_pipeline_config(_write_toml(tmp_path, body))
    assert config.fetch_sources == ["pubtator3"]


def test_source_as_list_is_preserved(tmp_path: Path) -> None:
    body = _BASE + 'source = ["pubtator3", "entrez", "europe_pmc"]\n'
    config = load_pipeline_config(_write_toml(tmp_path, body))
    assert config.fetch_sources == ["pubtator3", "entrez", "europe_pmc"]


def test_source_raw_text_is_rejected(tmp_path: Path) -> None:
    body = _BASE + 'source = "raw_text"\n'
    with pytest.raises(ValueError, match="unsupported values"):
        load_pipeline_config(_write_toml(tmp_path, body))


def test_source_unknown_value_is_rejected(tmp_path: Path) -> None:
    body = _BASE + 'source = "doesnotexist"\n'
    with pytest.raises(ValueError, match="unsupported values"):
        load_pipeline_config(_write_toml(tmp_path, body))


def test_supported_fetch_sources_constant_excludes_raw_text() -> None:
    assert SUPPORTED_FETCH_SOURCES == ["pubtator3", "entrez", "europe_pmc"]


# B. input.fields and input.fields_per_source

def test_fields_omitted_is_none(tmp_path: Path) -> None:
    config = load_pipeline_config(_write_toml(tmp_path, _BASE))
    assert config.fetch_fields is None


def test_fields_parsed_as_list(tmp_path: Path) -> None:
    body = _BASE + 'fields = ["title", "abstract"]\n'
    config = load_pipeline_config(_write_toml(tmp_path, body))
    assert config.fetch_fields == ["title", "abstract"]


def test_fields_per_source_parsed(tmp_path: Path) -> None:
    body = _BASE + (
        "[input.fields_per_source]\n"
        'entrez = ["mesh_terms", "authors"]\n'
        'europe_pmc = ["citation_count"]\n'
    )
    config = load_pipeline_config(_write_toml(tmp_path, body))
    assert config.fetch_fields_per_source == {
        "entrez": ["mesh_terms", "authors"],
        "europe_pmc": ["citation_count"],
    }


def test_fields_per_source_unknown_source_is_rejected(tmp_path: Path) -> None:
    body = _BASE + (
        "[input.fields_per_source]\n"
        'unknown = ["mesh_terms"]\n'
    )
    with pytest.raises(ValueError, match="not a supported source"):
        load_pipeline_config(_write_toml(tmp_path, body))


# C. [input.pubtator3].full_text

def test_pubtator3_full_text_default_false(tmp_path: Path) -> None:
    config = load_pipeline_config(_write_toml(tmp_path, _BASE))
    assert config.pubtator3_full_text is False


def test_pubtator3_full_text_true(tmp_path: Path) -> None:
    body = _BASE + (
        "[input.pubtator3]\n"
        "full_text = true\n"
    )
    config = load_pipeline_config(_write_toml(tmp_path, body))
    assert config.pubtator3_full_text is True


def test_pubtator3_full_text_non_bool_is_rejected(tmp_path: Path) -> None:
    body = _BASE + (
        "[input.pubtator3]\n"
        'full_text = "yes"\n'
    )
    with pytest.raises(ValueError, match="must be a boolean"):
        load_pipeline_config(_write_toml(tmp_path, body))


def test_pubtator3_section_not_table_is_rejected(tmp_path: Path) -> None:
    body = _BASE + 'pubtator3 = "not_a_table"\n'
    with pytest.raises(ValueError, match="must be a table"):
        load_pipeline_config(_write_toml(tmp_path, body))
