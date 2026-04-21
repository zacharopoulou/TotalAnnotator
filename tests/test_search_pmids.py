from __future__ import annotations

import json
import re
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from bio_annotation.cli import main
from bio_annotation.io.search import search_pubmed_pmids, write_pmids


def test_write_pmids_writes_one_per_line(tmp_path: Path) -> None:
    output = tmp_path / "pmids.txt"
    write_pmids(output, ["38123456", "31452104"])
    assert output.read_text(encoding="utf-8") == "38123456\n31452104\n"


def test_small_query_single_call() -> None:
    calls = []

    def fake(term: str) -> dict:
        calls.append(term)
        return {"count": 3, "pmids": ["1", "2", "3"]}

    assert search_pubmed_pmids("glioblastoma", esearch_fn=fake) == ["1", "2", "3"]
    assert len(calls) == 1


def test_bisects_when_over_cap() -> None:
    responses = iter(
        [
            {"count": 25_000, "pmids": []},
            {"count": 500, "pmids": [f"a{i}" for i in range(500)]},
            {"count": 700, "pmids": [f"b{i}" for i in range(700)]},
        ]
    )
    pmids = search_pubmed_pmids(
        "glioblastoma",
        date_from="2020/01/01",
        date_to="2020/12/31",
        esearch_fn=lambda t: next(responses),
    )
    assert len(pmids) == 1200


def test_bisection_windows_are_disjoint() -> None:
    windows: list[tuple[str, str]] = []

    def fake(term: str) -> dict:
        match = re.search(r'"(\d{4}/\d{2}/\d{2})".*?"(\d{4}/\d{2}/\d{2})"', term)
        assert match is not None
        windows.append((match.group(1), match.group(2)))
        return {"count": 25_000 if len(windows) == 1 else 100, "pmids": []}

    search_pubmed_pmids(
        "glioblastoma",
        date_from="2020/01/01",
        date_to="2020/12/31",
        esearch_fn=fake,
    )

    leaves = sorted(windows[1:])
    for (_, end_a), (start_b, _) in zip(leaves, leaves[1:]):
        assert end_a < start_b


def test_raises_on_unbisectable_leaf() -> None:
    try:
        search_pubmed_pmids(
            "glioblastoma",
            date_from="2020/06/15",
            date_to="2020/06/15",
            esearch_fn=lambda t: {"count": 15_000, "pmids": []},
        )
    except ValueError as exc:
        assert "exceeds" in str(exc)
    else:
        raise AssertionError("Expected ValueError.")


def test_respects_max_results() -> None:
    pmids = search_pubmed_pmids(
        "glioblastoma",
        max_results=3,
        esearch_fn=lambda t: {"count": 5, "pmids": ["1", "2", "3", "4", "5"]},
    )
    assert pmids == ["1", "2", "3"]


def test_cli_search_pmids_writes_output(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "query_pmids.txt"
    monkeypatch.setattr(
        "bio_annotation.cli.search_pubmed_pmids",
        lambda query, **kwargs: ["38123456", "31452104"],
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
