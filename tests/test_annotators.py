from __future__ import annotations

from dataclasses import dataclass
import json
from io import StringIO
from contextlib import redirect_stdout
from urllib import error
from urllib import request
import pytest

import pytest

from bio_annotation.cli import main
from bio_annotation.annotators import flatten_annotations, run_all_annotators
from bio_annotation.annotators.bern2 import annotate_with_bern2, call_bern2
from bio_annotation.annotators.flair import annotate_with_flair
from bio_annotation.annotators.pubtator3 import annotate_with_pubtator3, call_pubtator3
from bio_annotation.schemas.document import Document


def sample_document() -> Document:
    return Document(
        document_id="PMID:12345678",
        pmid="12345678",
        title="PTEN regulates glioblastoma",
        abstract="PTEN and miR-21 are biomarkers in glioblastoma.",
        source="pubmed",
    )


def test_bern2_adapter_normalizes_records() -> None:
    document = sample_document()
    response = {
        "annotations": [
            {
                "mention": "PTEN",
                "span": {"begin": 0, "end": 4},
                "type": "Gene",
                "id": ["NCBIGene:5728"],
                "normalizedName": "PTEN",
                "prob": 0.98,
            },
            {
                "mention": "glioblastoma",
                "span": {"begin": 15, "end": 27},
                "type": "Disease",
                "id": "MESH:D005909",
            },
        ]
    }

    annotations = annotate_with_bern2(document, response=response)

    assert len(annotations) == 2
    assert annotations[0].source == "bern2"
    assert annotations[0].entity_type == "gene"
    assert annotations[0].canonical_id == "NCBIGene:5728"
    assert annotations[0].confidence == 0.98
    assert annotations[1].entity_type == "disease"


def test_bern2_call_surfaces_connection_failures(monkeypatch) -> None:
    document = sample_document()

    class FakeOpener:
        def open(self, http_request: request.Request, timeout: int) -> object:
            raise error.URLError("connection refused")

    monkeypatch.setattr(request, "build_opener", lambda *args: FakeOpener())

    with pytest.raises(RuntimeError, match="BERN2 request failed"):
        call_bern2(document, endpoint="http://127.0.0.1:8888/plain")


@dataclass
class FakeLabel:
    value: str
    score: float


@dataclass
class FakeSpan:
    text: str
    start_position: int
    end_position: int
    labels: list[FakeLabel]


def test_flair_adapter_preserves_unsupported_span_labels() -> None:
    document = sample_document()
    spans = [
        FakeSpan(
            text="miR-21",
            start_position=37,
            end_position=43,
            labels=[FakeLabel(value="micro_rna", score=0.87)],
        )
    ]

    annotations = annotate_with_flair(document, spans=spans)

    assert len(annotations) == 1
    assert annotations[0].source == "flair"
    assert annotations[0].entity_type == "micro_rna"
    assert annotations[0].confidence == 0.87


def test_flair_adapter_loads_configured_model() -> None:
    document = sample_document()
    loaded_models: list[str] = []

    class FakeTagger:
        def predict(self, sentence: object) -> None:
            return None

    class FakeSentence:
        def __init__(self, text: str) -> None:
            self.text = text

        def get_spans(self, label_type: str) -> list[FakeSpan]:
            assert label_type == "ner"
            return [
                FakeSpan(
                    text="PTEN",
                    start_position=0,
                    end_position=4,
                    labels=[FakeLabel(value="gene", score=0.99)],
                )
            ]

    def fake_loader(model: str) -> FakeTagger:
        loaded_models.append(model)
        return FakeTagger()

    annotations = annotate_with_flair(
        document,
        model="hunflair2",
        sentence_factory=FakeSentence,
        tagger_loader=fake_loader,
    )

    assert loaded_models == ["hunflair2"]
    assert len(annotations) == 1
    assert annotations[0].source == "flair"
    assert annotations[0].entity_type == "gene"


def test_flair_adapter_raises_when_configured_model_cannot_load() -> None:
    document = sample_document()

    def broken_loader(model: str) -> object:
        raise RuntimeError(f"{model} is unavailable")

    with pytest.raises(RuntimeError, match="hunflair2 is unavailable"):
        annotate_with_flair(
            document,
            model="hunflair2",
            tagger_loader=broken_loader,
        )


def test_pubtator3_adapter_parses_bioc_json_with_absolute_offsets() -> None:
    document = sample_document()
    response = {
        "documents": [
            {
                "passages": [
                    {
                        "offset": 10,
                        "annotations": [
                            {
                                "text": "PTEN",
                                "infons": {"type": "Gene", "identifier": "5728"},
                                "locations": [{"offset": 0, "length": 4}],
                            },
                            {
                                "text": "glioblastoma",
                                "infons": {"type": "Disease", "identifier": "D005909"},
                                "locations": [{"offset": 15, "length": 12}],
                            },
                        ],
                    }
                ]
            }
        ]
    }

    annotations = annotate_with_pubtator3(document, response=response)

    assert len(annotations) == 2
    assert annotations[0].source == "pubtator3"
    assert annotations[0].start == 0
    assert annotations[0].canonical_id == "5728"
    assert annotations[1].start == 15
    assert annotations[1].entity_type == "disease"


def test_pubtator3_adapter_parses_pubtator3_wrapped_bioc_json() -> None:
    document = sample_document()
    response = {
        "PubTator3": [
            {
                "passages": [
                    {
                        "offset": 0,
                        "annotations": [
                            {
                                "text": "PTEN",
                                "infons": {"type": "Gene", "identifier": "5728"},
                                "locations": [{"offset": 0, "length": 4}],
                            }
                        ],
                    }
                ]
            }
        ]
    }

    annotations = annotate_with_pubtator3(document, response=response)

    assert len(annotations) == 1
    assert annotations[0].source == "pubtator3"
    assert annotations[0].canonical_id == "5728"


def test_pubtator3_adapter_parses_pubannotation_json() -> None:
    document = sample_document()
    response = {
        "text": document.text,
        "sourcedb": "PubMed",
        "sourceid": document.document_id,
        "denotations": [
            {"obj": "Gene:5728", "span": {"begin": 0, "end": 4}},
            {"obj": "Disease:D005909", "span": {"begin": 15, "end": 27}},
        ],
    }

    annotations = annotate_with_pubtator3(document, response=response)

    assert len(annotations) == 2
    assert annotations[0].source == "pubtator3"
    assert annotations[0].entity_type == "gene"
    assert annotations[1].canonical_id == "D005909"


def test_pubtator3_adapter_parses_pubtator_text_format() -> None:
    document = sample_document()
    response = (
        "00000|t|PTEN regulates glioblastoma.\n"
        "00000|a|PTEN and miR-21 are biomarkers in glioblastoma.\n"
        "00000\t0\t4\tPTEN\tGene\t5728\n"
        "00000\t9\t21\tglioblastoma\tDisease\tD005909\n"
    )

    annotations = annotate_with_pubtator3(document, response=response)

    assert len(annotations) == 2
    assert annotations[0].entity_type == "gene"
    assert annotations[0].canonical_id == "5728"
    assert annotations[1].entity_type == "disease"


def test_pubtator3_adapter_uses_raw_text_mode_for_plain_corpus() -> None:
    document = Document(
        document_id="CORPUS:doc1",
        pmid="12345678",
        title="PTEN regulates glioblastoma",
        abstract="PTEN is important in glioblastoma.",
        source="corpus",
    )

    class FakeClient:
        def __init__(self) -> None:
            self.payloads: list[str] = []
            self.options: list[dict[str, object]] = []

        def annotate_text(self, payload: str, **kwargs: object) -> str:
            self.payloads.append(payload)
            self.options.append(kwargs)
            return '{"text":"PTEN regulates glioblastoma\\n\\nPTEN is important in glioblastoma.","denotations":[{"obj":"Gene:5728","span":{"begin":0,"end":4}}]}'

    client = FakeClient()
    annotations = annotate_with_pubtator3(document, client=client, mode="text_only")

    assert len(annotations) == 1
    assert annotations[0].source == "pubtator3"
    assert annotations[0].entity_type == "gene"
    assert annotations[0].canonical_id == "5728"
    assert client.payloads == [document.text]
    assert client.options[0]["bioconcept"] == "All"


def test_pubtator3_auto_uses_publication_export_for_pubtator3_pmid_documents() -> None:
    document = Document(
        document_id="PMID:12345678",
        pmid="12345678",
        title="PTEN regulates glioblastoma",
        abstract="PTEN is important in glioblastoma.",
        source="pubtator3",
    )

    class FakeClient:
        def __init__(self) -> None:
            self.pmids: list[list[str]] = []
            self.text_payloads: list[str] = []

        def fetch_publications_by_pmids(self, pmids: list[str], **kwargs: object) -> dict[str, list[dict[str, object]]]:
            self.pmids.append(pmids)
            return {"documents": []}

        def fetch_publications_by_pmcids(self, pmcids: list[str], **kwargs: object) -> dict[str, list[dict[str, object]]]:
            raise AssertionError("PMCID lookup should not be used when PMID is present")

        def annotate_text(self, payload: str, **kwargs: object) -> str:
            self.text_payloads.append(payload)
            raise AssertionError("raw text annotation should not be used for PMID documents in auto mode")

    client = FakeClient()
    payload = call_pubtator3(document, client=client, mode="auto")

    assert payload == {"documents": []}
    assert client.pmids == [["12345678"]]
    assert client.text_payloads == []


def test_pubtator3_auto_uses_publication_export_for_metadata_pmcid_documents() -> None:
    document = Document(
        document_id="PMC:PMC1234567",
        title="PTEN regulates glioblastoma",
        abstract="PTEN is important in glioblastoma.",
        source="europe_pmc",
        metadata={"pmcid": "PMC1234567"},
    )

    class FakeClient:
        def __init__(self) -> None:
            self.pmcids: list[list[str]] = []
            self.text_payloads: list[str] = []

        def fetch_publications_by_pmids(self, pmids: list[str], **kwargs: object) -> dict[str, list[dict[str, object]]]:
            raise AssertionError("PMID lookup should not be used when no PMID is present")

        def fetch_publications_by_pmcids(self, pmcids: list[str], **kwargs: object) -> dict[str, list[dict[str, object]]]:
            self.pmcids.append(pmcids)
            return {"documents": []}

        def annotate_text(self, payload: str, **kwargs: object) -> str:
            self.text_payloads.append(payload)
            raise AssertionError("raw text annotation should not be used for PMCID documents in auto mode")

    client = FakeClient()
    payload = call_pubtator3(document, client=client, mode="auto")

    assert payload == {"documents": []}
    assert client.pmcids == [["PMC1234567"]]
    assert client.text_payloads == []


def test_pubtator3_auto_falls_back_to_raw_text_without_publication_identifiers() -> None:
    document = Document(
        document_id="CORPUS:doc1",
        title="PTEN regulates glioblastoma",
        abstract="PTEN is important in glioblastoma.",
        source="corpus",
    )

    class FakeClient:
        def __init__(self) -> None:
            self.payloads: list[str] = []

        def fetch_publications_by_pmids(self, pmids: list[str], **kwargs: object) -> dict[str, list[dict[str, object]]]:
            raise AssertionError("PMID lookup should not be used without a PMID")

        def fetch_publications_by_pmcids(self, pmcids: list[str], **kwargs: object) -> dict[str, list[dict[str, object]]]:
            raise AssertionError("PMCID lookup should not be used without a PMCID")

        def annotate_text(self, payload: str, **kwargs: object) -> str:
            self.payloads.append(payload)
            return '{"text":"PTEN regulates glioblastoma\\n\\nPTEN is important in glioblastoma.","denotations":[]}'

    client = FakeClient()
    payload = call_pubtator3(document, client=client, mode="auto")

    assert payload == '{"text":"PTEN regulates glioblastoma\\n\\nPTEN is important in glioblastoma.","denotations":[]}'
    assert client.payloads == [document.text]


def test_run_all_annotators_returns_consistent_result_map() -> None:
    document = sample_document()
    results = run_all_annotators(
        document,
        bern2_response={
            "annotations": [
                {"mention": "PTEN", "span": {"begin": 0, "end": 4}, "type": "Gene"}
            ]
        },
        flair_spans=[
            FakeSpan(
                text="miR-21",
                start_position=37,
                end_position=43,
                labels=[FakeLabel(value="micro_rna", score=0.87)],
            )
        ],
        pubtator3_response={
            "documents": [
                {
                    "passages": [
                        {
                            "annotations": [
                                {
                                    "text": "glioblastoma",
                                    "infons": {"type": "Disease", "identifier": "D005909"},
                                    "locations": [{"offset": 15, "length": 12}],
                                }
                            ]
                        }
                    ]
                }
            ]
        },
    )

    assert set(results) == {"bern2", "flair", "pubtator3"}
    assert all(isinstance(items, list) for items in results.values())
    assert len(flatten_annotations(results)) == 3


def test_cli_demo_runs() -> None:
    stream = StringIO()
    with redirect_stdout(stream):
        exit_code = main(["demo"])

    output = stream.getvalue()
    assert exit_code == 0
    assert "PMID:12345678" in output
    assert '"sources"' in output


def test_cli_inspect_config_runs() -> None:
    stream = StringIO()
    with redirect_stdout(stream):
        exit_code = main(["inspect-config"])

    output = json.loads(stream.getvalue())
    assert exit_code == 0
    assert output["input_mode"] == "pmids"
    assert output["pmids"] == ["36403686"]
    assert output["enrichment_sources"] == []
    assert output["annotators"] == ["bern2", "flair", "pubtator3"]
    assert output["annotator_settings"]["bern2"]["runtime"] == "remote_api"
    assert output["annotator_settings"]["bern2"]["base_url"] == "http://127.0.0.1:8888"
    assert output["annotator_settings"]["flair"]["model"] == "hunflair2"
    assert output["annotator_settings"]["pubtator3"]["runtime"] == "remote_api"
    assert output["annotator_settings"]["pubtator3"]["format"] == "biocjson"
    assert output["annotator_settings"]["pubtator3"]["endpoint"] == "https://www.ncbi.nlm.nih.gov/research/pubtator3-api"


def test_cli_load_documents_runs(monkeypatch) -> None:
    monkeypatch.setattr(
        "bio_annotation.preprocessing.document_loader.fetch_pubmed_record",
        lambda pmid, **kwargs: {
            "pmid": pmid,
            "title": "Mock title",
            "abstract": "Mock abstract",
            "year": "2024",
            "elinks": {},
        },
    )
    stream = StringIO()
    with redirect_stdout(stream):
        exit_code = main(["load-documents"])

    output = json.loads(stream.getvalue())
    assert exit_code == 0
    assert output["input_mode"] == "pmids"
    assert output["document_count"] == 1