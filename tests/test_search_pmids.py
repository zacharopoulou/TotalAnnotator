from __future__ import annotations

import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from bio_annotation.cli import main
from bio_annotation.io.search import search_pubmed_pmids, write_pmids


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_search_pubmed_pmids_parses_json(monkeypatch) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: _FakeResponse({"esearchresult": {"idlist": ["38123456", "31452104"]}}),
    )

    pmids = search_pubmed_pmids("glioblastoma")

    assert pmids == ["38123456", "31452104"]


def test_write_pmids_writes_one_per_line(tmp_path: Path) -> None:
    output = tmp_path / "pmids.txt"
    write_pmids(output, ["38123456", "31452104"])
    assert output.read_text(encoding="utf-8") == "38123456\n31452104\n"


def test_cli_search_pmids_writes_output(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "query_pmids.txt"
    monkeypatch.setattr(
        "bio_annotation.cli.search_pubmed_pmids",
        lambda query, max_results, date_from, date_to, sort_by, filters: ["38123456", "31452104"],
    )

    stream = StringIO()
    with redirect_stdout(stream):
        exit_code = main(
            [
                "search-pmids",
                "--query",
                "glioblastoma",
                "--output",
                str(output),
            ]
        )

    payload = json.loads(stream.getvalue())
    assert exit_code == 0
    assert payload["pmid_count"] == 2
    assert output.read_text(encoding="utf-8") == "38123456\n31452104\n"
