from __future__ import annotations

from dataclasses import dataclass
import json
from io import StringIO
from contextlib import redirect_stdout

from bio_annotation.cli import main
from bio_annotation.annotators import flatten_annotations, run_all_annotators
from bio_annotation.annotators.bern2 import annotate_with_bern2
from bio_annotation.annotators.flair import annotate_with_flair, run_flair_on_document
from bio_annotation.annotators.pubtator3 import annotate_with_pubtator3
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
                "id": "NCBIGene:5728",
                "normalizedName": "PTEN",
                "probability": 0.98,
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
    assert annotations[1].entity_type == "disease"


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


def test_run_flair_on_document_empty_body_raw_snapshot() -> None:
    document = Document(document_id="PMID:1", pmid="1", title="", abstract="  \n", source="pubmed")
    ann, raw = run_flair_on_document(document, tagger=object(), include_raw=True)
    assert ann == []
    assert raw == {"skipped": "empty_document_text"}

    _, raw_off = run_flair_on_document(document, tagger=object(), include_raw=False)
    assert raw_off is None


def test_flair_adapter_normalizes_spans() -> None:
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
    assert annotations[0].entity_type == "mirna"
    assert annotations[0].confidence == 0.87


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
    # Passage-level BioC ``offset`` (10) must be added to location offsets (0, 15).
    assert annotations[0].start == 10
    assert annotations[0].canonical_id == "5728"
    assert annotations[1].start == 25
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
    annotations = annotate_with_pubtator3(document, client=client)

    assert len(annotations) == 1
    assert annotations[0].source == "pubtator3"
    assert annotations[0].entity_type == "gene"
    assert annotations[0].canonical_id == "5728"
    assert client.payloads == [document.text]
    assert client.options[0]["bioconcept"] == "All"


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

    assert set(results) == {"bern2", "flair", "pubtator3", "medcat"}
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
    assert output["annotators"] == ["pubtator3"]
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
