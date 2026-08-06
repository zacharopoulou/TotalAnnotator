from __future__ import annotations

from dataclasses import dataclass
import json
from io import StringIO
from pathlib import Path
from contextlib import redirect_stdout
from urllib import error
from urllib import request
import pytest

from bio_annotation.cli import main
from bio_annotation.annotators import flatten_annotations, run_all_annotators
from bio_annotation.annotators.aioner import (
    annotate_with_aioner,
    build_aioner_pubtator_input,
    call_aioner,
)
from bio_annotation.annotators.clinicalbert import (
    DEFAULT_CLINICALBERT_MODEL,
    annotate_with_clinicalbert,
)
from bio_annotation.annotators.apollo import (
    DEFAULT_APOLLO_MODEL,
    annotate_with_apollo,
)
from bio_annotation.annotators.bent import annotate_with_bent, call_bent
from bio_annotation.annotators.bern2 import annotate_with_bern2, call_bern2
from bio_annotation.annotators.biobert import (
    DEFAULT_BIOBERT_MODELS,
    annotate_with_biobert,
)
from bio_annotation.annotators.d4data import (
    DEFAULT_D4DATA_MODEL,
    annotate_with_d4data,
)
from bio_annotation.annotators.flair import annotate_with_flair
from bio_annotation.annotators.pubtator3 import annotate_with_pubtator3, call_pubtator3
from bio_annotation.annotators.scispacy import (
    SCISPACY_MODEL_BY_ANNOTATOR,
    annotate_with_scispacy,
    annotate_with_scispacy_bc5cdr,
    annotate_with_scispacy_bionlp13cg,
    annotate_with_scispacy_craft,
    annotate_with_scispacy_jnlpba,
    annotate_with_scispacy_md,
    annotate_with_scispacy_scibert,
)
from bio_annotation.annotators.stanza import annotate_with_stanza
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


def test_pubtator3_adapter_remaps_publication_offsets_to_document_text() -> None:
    document = Document(
        document_id="9288106",
        pmid="9288106",
        title="Ataxia-telangiectasia causes cancer.",
        abstract="A-T is a recessive multi-system disorder.",
        source="benchmark:ncbi_disease",
    )
    source_abstract_start = len(document.title) + 1
    canonical_abstract_start = len(document.title) + 2
    response = {
        "documents": [
            {
                "passages": [
                    {
                        "type": "title",
                        "text": document.title,
                        "offset": 0,
                        "annotations": [
                            {
                                "text": "Ataxia-telangiectasia",
                                "infons": {"type": "Disease", "identifier": "D001260"},
                                "locations": [{"offset": 0, "length": 21}],
                            }
                        ],
                    },
                    {
                        "type": "abstract",
                        "text": document.abstract,
                        "offset": source_abstract_start,
                        "annotations": [
                            {
                                "text": "recessive multi-system disorder",
                                "infons": {"type": "Disease", "identifier": "D030342"},
                                "locations": [
                                    {
                                        "offset": source_abstract_start + 9,
                                        "length": 31,
                                    }
                                ],
                            }
                        ],
                    },
                ]
            }
        ]
    }

    annotations = annotate_with_pubtator3(document, response=response)

    assert annotations[0].span_text == "Ataxia-telangiectasia"
    assert annotations[0].start == 0
    assert annotations[0].end == 21
    assert annotations[1].span_text == "recessive multi-system disorder"
    assert annotations[1].start == canonical_abstract_start + 9
    assert annotations[1].end == canonical_abstract_start + 40
    assert document.text[annotations[1].start : annotations[1].end] == annotations[1].span_text


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


def test_pubtator3_publication_mode_uses_pmid_for_benchmark_documents() -> None:
    document = Document(
        document_id="9949209",
        pmid="9949209",
        title="Genetic mapping of the copper toxicosis locus.",
        abstract="Wilson disease causes hepatic copper accumulation.",
        source="benchmark:ncbi_disease",
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
            raise AssertionError("raw text annotation should not be used for benchmark PMID documents")

    client = FakeClient()
    payload = call_pubtator3(document, client=client, mode="publication_only")

    assert payload == {"documents": []}
    assert client.pmids == [["9949209"]]
    assert client.text_payloads == []


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


def test_aioner_adapter_parses_pubtator_output_and_normalizes_types() -> None:
    document = sample_document()
    # AIONER emits 5-column PubTator (no identifier; NER only). "Chemical" and
    # "CellLine" must normalize to the canonical "drug" / "cell_line" types.
    response = (
        "PMID:12345678|t|PTEN regulates glioblastoma\n"
        "PMID:12345678|a|\n"
        "PMID:12345678\t0\t4\tPTEN\tGene\n"
        "PMID:12345678\t15\t27\tglioblastoma\tDisease\n"
        "PMID:12345678\t40\t48\tcisplatin\tChemical\n"
        "PMID:12345678\t60\t65\tHeLa\tCellLine\n"
    )

    annotations = annotate_with_aioner(document, response=response)

    assert len(annotations) == 4
    assert all(annotation.source == "aioner" for annotation in annotations)
    assert annotations[0].entity_type == "gene"
    assert annotations[0].start == 0
    assert annotations[0].end == 4
    assert annotations[1].entity_type == "disease"
    assert annotations[2].entity_type == "drug"
    assert annotations[3].entity_type == "cell_line"
    assert all(annotation.canonical_id is None for annotation in annotations)


def test_aioner_adapter_uses_request_fn() -> None:
    document = sample_document()
    calls: list[Document] = []

    def fake_request(doc: Document) -> str:
        calls.append(doc)
        return "PMID:12345678\t0\t4\tPTEN\tGene\n"

    annotations = annotate_with_aioner(document, request_fn=fake_request)

    assert calls == [document]
    assert len(annotations) == 1
    assert annotations[0].entity_type == "gene"


def test_aioner_input_flattens_newlines_preserving_offsets() -> None:
    document = sample_document()
    rendered = build_aioner_pubtator_input(document)

    title_line = rendered.splitlines()[0]
    assert title_line.startswith("PMID:12345678|t|")
    flat_text = title_line.split("|t|", 1)[1]
    assert "\n" not in flat_text
    # Length is preserved so AIONER's absolute offsets map onto document.text.
    assert len(flat_text) == len(document.text)


def test_aioner_call_requires_configuration(monkeypatch) -> None:
    document = sample_document()
    monkeypatch.delenv("AIONER_REPO", raising=False)
    monkeypatch.delenv("AIONER_MODEL", raising=False)

    with pytest.raises(RuntimeError, match="AIONER repo path is not configured"):
        call_aioner(document)


def test_clinicalbert_adapter_parses_pipeline_output_and_normalizes_types() -> None:
    document = sample_document()
    # HuggingFace token-classification output. The clinical labels problem / test
    # / treatment are kept as their own types. Span text is sliced from
    # document.text, so the model's "word" field is ignored.
    response = [
        {"entity_group": "problem", "score": 0.99, "word": "oblastoma", "start": 15, "end": 27},
        {"entity_group": "treatment", "score": 0.95, "word": "PTEN", "start": 0, "end": 4},
        {"entity_group": "test", "score": 0.80, "word": "x", "start": 49, "end": 59},
    ]

    annotations = annotate_with_clinicalbert(document, response=response)

    assert len(annotations) == 3
    assert all(annotation.source == "clinicalbert" for annotation in annotations)
    assert annotations[0].entity_type == "problem"
    assert annotations[0].span_text == "glioblastoma"
    assert annotations[0].start == 15
    assert annotations[0].end == 27
    assert annotations[1].entity_type == "treatment"
    assert annotations[2].entity_type == "test"
    assert all(annotation.canonical_id is None for annotation in annotations)


def test_clinicalbert_adapter_uses_request_fn() -> None:
    document = sample_document()
    calls: list[Document] = []

    def fake_request(doc: Document) -> list[dict[str, object]]:
        calls.append(doc)
        return [
            {"entity_group": "problem", "score": 0.9, "word": "glioblastoma", "start": 15, "end": 27}
        ]

    annotations = annotate_with_clinicalbert(document, request_fn=fake_request)

    assert calls == [document]
    assert len(annotations) == 1
    assert annotations[0].entity_type == "problem"


def test_clinicalbert_adapter_loads_configured_model() -> None:
    document = sample_document()
    loaded_models: list[str] = []

    class FakePipeline:
        def __call__(self, text: str) -> list[dict[str, object]]:
            assert text == document.text
            return [
                {"entity_group": "treatment", "score": 0.88, "word": "PTEN", "start": 0, "end": 4}
            ]

    def fake_loader(model: str) -> FakePipeline:
        loaded_models.append(model)
        return FakePipeline()

    annotations = annotate_with_clinicalbert(
        document,
        model=DEFAULT_CLINICALBERT_MODEL,
        pipeline_loader=fake_loader,
    )

    assert loaded_models == [DEFAULT_CLINICALBERT_MODEL]
    assert len(annotations) == 1
    assert annotations[0].source == "clinicalbert"
    assert annotations[0].entity_type == "treatment"


def test_clinicalbert_adapter_trims_leading_articles_and_drops_noise() -> None:
    document = sample_document()
    # On out-of-domain text the i2b2 model tags articles and stray punctuation.
    # Leading "a"/"an"/"the" are stripped; bare articles and lone "-" are dropped.
    response = [
        {"entity_group": "problem", "score": 0.9, "word": "a stop codon"},
        {"entity_group": "problem", "score": 0.9, "word": "an 11-base pair insertion"},
        {"entity_group": "problem", "score": 0.9, "word": "a"},
        {"entity_group": "problem", "score": 0.9, "word": "-"},
        {"entity_group": "problem", "score": 0.9, "word": "the"},
        {"entity_group": "problem", "score": 0.9, "word": "breast cancer"},
    ]

    annotations = annotate_with_clinicalbert(document, response=response)

    spans = [annotation.span_text for annotation in annotations]
    assert spans == ["stop codon", "11-base pair insertion", "breast cancer"]
    assert all(annotation.entity_type == "problem" for annotation in annotations)


def test_biobert_adapter_merges_per_model_responses() -> None:
    document = sample_document()
    # One HuggingFace payload per checkpoint; the producing model sets the type.
    response = {
        "gene": [{"entity_group": "GENE", "score": 0.98, "word": "PTEN"}],
        "disease": [{"entity_group": "DISEASE", "score": 0.95, "word": "glioblastoma"}],
        "drug": [{"entity_group": "CHEMICAL", "score": 0.90, "word": "miR-21"}],
    }

    annotations = annotate_with_biobert(document, response=response)

    assert all(annotation.source == "biobert" for annotation in annotations)
    assert {(a.span_text, a.entity_type) for a in annotations} == {
        ("PTEN", "gene"),
        ("glioblastoma", "disease"),
        ("miR-21", "drug"),
    }


def test_biobert_adapter_loads_one_pipeline_per_model() -> None:
    document = sample_document()
    loaded: list[str] = []
    label_by_model = {
        "alvaroalon2/biobert_genetic_ner": "GENE",
        "alvaroalon2/biobert_diseases_ner": "DISEASE",
        "alvaroalon2/biobert_chemical_ner": "CHEMICAL",
    }

    def fake_loader(model: str):
        loaded.append(model)
        label = label_by_model[model]
        return lambda text: [{"entity_group": label, "score": 0.9, "word": "PTEN"}]

    annotations = annotate_with_biobert(document, pipeline_loader=fake_loader)

    # One pipeline loaded per configured checkpoint, all merged under "biobert".
    assert loaded == list(DEFAULT_BIOBERT_MODELS.values())
    assert all(a.source == "biobert" for a in annotations)
    assert sorted(a.entity_type for a in annotations) == ["disease", "drug", "gene"]


def test_biobert_adapter_uses_request_fn_and_drops_punctuation() -> None:
    document = sample_document()

    def fake_request(doc: Document) -> dict[str, list[dict[str, object]]]:
        return {
            "gene": [
                {"entity_group": "GENE", "score": 0.9, "word": "PTEN"},
                {"entity_group": "GENE", "score": 0.4, "word": "-"},
            ],
        }

    annotations = annotate_with_biobert(document, request_fn=fake_request)

    assert [a.span_text for a in annotations] == ["PTEN"]
    assert annotations[0].entity_type == "gene"
    assert annotations[0].source == "biobert"


def test_biobert_adapter_drops_outside_zero_labels() -> None:
    document = sample_document()
    # The diseases checkpoint mislabels its "outside" tag as "0" (not "O"), so the
    # pipeline emits bogus "0" spans over plain text; those must be dropped.
    response = {
        "disease": [
            {"entity_group": "0", "score": 1.0, "word": "PTEN and"},
            {"entity_group": "DISEASE", "score": 0.99, "word": "glioblastoma"},
            {"entity_group": "0", "score": 1.0, "word": "are biomarkers in"},
        ],
    }

    annotations = annotate_with_biobert(document, response=response)

    assert [a.span_text for a in annotations] == ["glioblastoma"]
    assert annotations[0].entity_type == "disease"


def test_aioner_windows_runner_uses_posix_paths_and_utf8(monkeypatch, tmp_path) -> None:
    # The Windows runner must hand AIONER forward-slash paths (it splits the model
    # path on "/") and decode the subprocess as UTF-8. Imported directly so the
    # test runs on any OS.
    from pathlib import Path

    from bio_annotation.entity_proposal import aioner_windows

    repo = tmp_path / "aioner"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "AIONER_Run.py").write_text("", encoding="utf-8")
    (repo / "vocab").mkdir()
    (repo / "vocab" / "AIO_label.vocab").write_text("", encoding="utf-8")
    model = tmp_path / "models" / "AIONER.h5"
    model.parent.mkdir()
    model.write_text("", encoding="utf-8")

    captured: dict = {}

    class FakeCompleted:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        out_dir = Path(command[command.index("-o") + 1])
        (out_dir / "document.txt").write_text("doc\t0\t4\tPTEN\tGene\n", encoding="utf-8")
        return FakeCompleted()

    monkeypatch.setattr(aioner_windows.subprocess, "run", fake_run)

    document = sample_document()
    out = aioner_windows.call_aioner(
        document, repo=str(repo), model=str(model), python="python"
    )

    cmd = captured["command"]
    model_arg = cmd[cmd.index("-m") + 1]
    assert "\\" not in model_arg
    assert model_arg.endswith("/models/AIONER.h5")
    assert "\\" not in cmd[cmd.index("-i") + 1]
    assert "\\" not in cmd[cmd.index("-o") + 1]
    assert captured["kwargs"].get("encoding") == "utf-8"
    assert "PTEN" in out


def test_apollo_adapter_parses_pipeline_output_and_normalizes_types() -> None:
    document = sample_document()
    # HuggingFace token-classification output (aggregation_strategy="first").
    # "DISEASE_DISORDER"/"MEDICATION" must normalize to canonical "disease"/"drug";
    # unmapped clinical labels like "SIGN_SYMPTOM" pass through. The span text is
    # sliced from document.text, so a subword "word" artifact is ignored.
    response = [
        {"entity_group": "DISEASE_DISORDER", "score": 0.99, "word": "oblastoma", "start": 15, "end": 27},
        {"entity_group": "MEDICATION", "score": 0.95, "word": "PTEN", "start": 0, "end": 4},
        {"entity_group": "SIGN_SYMPTOM", "score": 0.80, "word": "biomarkers", "start": 49, "end": 59},
    ]

    annotations = annotate_with_apollo(document, response=response)

    assert len(annotations) == 3
    assert all(annotation.source == "apollo" for annotation in annotations)
    assert annotations[0].entity_type == "disease"
    assert annotations[0].span_text == "glioblastoma"
    assert annotations[0].start == 15
    assert annotations[0].end == 27
    assert annotations[1].entity_type == "drug"
    assert annotations[2].entity_type == "sign_symptom"
    assert all(annotation.canonical_id is None for annotation in annotations)


def test_apollo_adapter_uses_request_fn() -> None:
    document = sample_document()
    calls: list[Document] = []

    def fake_request(doc: Document) -> list[dict[str, object]]:
        calls.append(doc)
        return [
            {"entity_group": "DISEASE_DISORDER", "score": 0.9, "word": "glioblastoma", "start": 15, "end": 27}
        ]

    annotations = annotate_with_apollo(document, request_fn=fake_request)

    assert calls == [document]
    assert len(annotations) == 1
    assert annotations[0].entity_type == "disease"


def test_apollo_adapter_loads_configured_model() -> None:
    document = sample_document()
    loaded_models: list[str] = []

    class FakePipeline:
        def __call__(self, text: str) -> list[dict[str, object]]:
            assert text == document.text
            return [
                {"entity_group": "MEDICATION", "score": 0.88, "word": "PTEN", "start": 0, "end": 4}
            ]

    def fake_loader(model: str) -> FakePipeline:
        loaded_models.append(model)
        return FakePipeline()

    annotations = annotate_with_apollo(
        document,
        model=DEFAULT_APOLLO_MODEL,
        pipeline_loader=fake_loader,
    )

    assert loaded_models == [DEFAULT_APOLLO_MODEL]
    assert len(annotations) == 1
    assert annotations[0].source == "apollo"
    assert annotations[0].entity_type == "drug"


def test_d4data_adapter_parses_pipeline_output_and_normalizes_types() -> None:
    document = sample_document()
    # d4data emits mixed-case MACCROBAT labels; they should normalize through the
    # shared MACCROBAT alias table used by Apollo too.
    response = [
        {"entity_group": "Disease_disorder", "score": 0.99, "word": "oblastoma", "start": 15, "end": 27},
        {"entity_group": "Medication", "score": 0.95, "word": "PTEN", "start": 0, "end": 4},
        {"entity_group": "Sign_symptom", "score": 0.80, "word": "biomarkers", "start": 49, "end": 59},
    ]

    annotations = annotate_with_d4data(document, response=response)

    assert len(annotations) == 3
    assert all(annotation.source == "d4data" for annotation in annotations)
    assert annotations[0].entity_type == "disease"
    assert annotations[0].span_text == "glioblastoma"
    assert annotations[0].start == 15
    assert annotations[0].end == 27
    assert annotations[1].entity_type == "drug"
    assert annotations[2].entity_type == "sign_symptom"
    assert all(annotation.canonical_id is None for annotation in annotations)


def test_d4data_adapter_uses_request_fn() -> None:
    document = sample_document()
    calls: list[Document] = []

    def fake_request(doc: Document) -> list[dict[str, object]]:
        calls.append(doc)
        return [
            {"entity_group": "Disease_disorder", "score": 0.9, "word": "glioblastoma", "start": 15, "end": 27}
        ]

    annotations = annotate_with_d4data(document, request_fn=fake_request)

    assert calls == [document]
    assert len(annotations) == 1
    assert annotations[0].entity_type == "disease"


def test_d4data_adapter_loads_configured_model() -> None:
    document = sample_document()
    loaded_models: list[str] = []

    class FakePipeline:
        def __call__(self, text: str) -> list[dict[str, object]]:
            assert text == document.text
            return [
                {"entity_group": "Medication", "score": 0.88, "word": "PTEN", "start": 0, "end": 4}
            ]

    def fake_loader(model: str) -> FakePipeline:
        loaded_models.append(model)
        return FakePipeline()

    annotations = annotate_with_d4data(
        document,
        model=DEFAULT_D4DATA_MODEL,
        pipeline_loader=fake_loader,
    )

    assert loaded_models == [DEFAULT_D4DATA_MODEL]
    assert len(annotations) == 1
    assert annotations[0].source == "d4data"
    assert annotations[0].entity_type == "drug"


def test_scispacy_jnlpba_adapter_parses_spacy_entities_and_normalizes_types() -> None:
    document = sample_document()
    response = [
        FakeScispacyEntity("PTEN", "PROTEIN", 0, 4),
        FakeScispacyEntity("miR-21", "RNA", 9, 15),
    ]

    annotations = annotate_with_scispacy_jnlpba(document, response=response)

    assert [annotation.source for annotation in annotations] == [
        "scispacy_jnlpba",
        "scispacy_jnlpba",
    ]
    assert [annotation.entity_type for annotation in annotations] == ["gene", "rna"]
    assert all(annotation.canonical_id is None for annotation in annotations)


def test_scispacy_bc5cdr_adapter_maps_chemical_to_drug() -> None:
    document = sample_document()
    response = [
        FakeScispacyEntity("glioblastoma", "DISEASE", 36, 48),
        FakeScispacyEntity("cisplatin", "CHEMICAL", 0, 9),
    ]

    annotations = annotate_with_scispacy_bc5cdr(document, response=response)

    assert [annotation.source for annotation in annotations] == [
        "scispacy_bc5cdr",
        "scispacy_bc5cdr",
    ]
    assert [annotation.entity_type for annotation in annotations] == ["disease", "drug"]


def test_scispacy_bionlp13cg_adapter_maps_complete_requested_labels() -> None:
    document = sample_document()
    labels = [
        ("AMINO_ACID", "amino_acid"),
        ("ANATOMICAL_SYSTEM", "anatomical_system"),
        ("CANCER", "cancer"),
        ("CELL", "cell"),
        ("CELLULAR_COMPONENT", "cellular_component"),
        ("DEVELOPING_ANATOMICAL_STRUCTURE", "developing_anatomical_structure"),
        ("GENE_OR_GENE_PRODUCT", "gene"),
        ("IMMATERIAL_ANATOMICAL_ENTITY", "immaterial_anatomical_entity"),
        ("MULTI-TISSUE_STRUCTURE", "multi_tissue_structure"),
        ("ORGAN", "organ"),
        ("ORGANISM", "species"),
        ("ORGANISM_SUBDIVISION", "organism_subdivision"),
        ("ORGANISM_SUBSTANCE", "organism_substance"),
        ("PATHOLOGICAL_FORMATION", "pathological_formation"),
        ("SIMPLE_CHEMICAL", "drug"),
        ("TISSUE", "tissue"),
    ]
    response = [
        FakeScispacyEntity(label, label, index, index + len(label))
        for index, (label, _) in enumerate(labels)
    ]

    annotations = annotate_with_scispacy_bionlp13cg(document, response=response)

    assert [annotation.source for annotation in annotations] == [
        "scispacy_bionlp13cg"
    ] * len(labels)
    assert [annotation.entity_type for annotation in annotations] == [
        expected for _, expected in labels
    ]


def test_scispacy_craft_adapter_maps_ontology_labels() -> None:
    document = sample_document()
    labels = [
        ("GGP", "gene"),
        ("CHEBI", "drug"),
        ("CL", "cell_type"),
        ("TAXON", "species"),
        ("GO", "gene_ontology"),
        ("SO", "sequence_ontology"),
    ]
    response = [
        FakeScispacyEntity(label, label, index, index + len(label))
        for index, (label, _) in enumerate(labels)
    ]

    annotations = annotate_with_scispacy_craft(document, response=response)

    assert [annotation.source for annotation in annotations] == [
        "scispacy_craft"
    ] * len(labels)
    assert [annotation.entity_type for annotation in annotations] == [
        expected for _, expected in labels
    ]


def test_scispacy_scibert_adapter_keeps_top_linker_candidate() -> None:
    document = sample_document()
    response = [
        FakeScispacyEntity(
            "glioblastoma",
            "ENTITY",
            36,
            48,
            [("C0017636", 0.91), ("C0278878", 0.42)],
        )
    ]

    annotations = annotate_with_scispacy_scibert(
        document,
        response=response,
        nlp=type(
            "FakeNlp",
            (),
            {"get_pipe": lambda self, name: FakeScispacyLinker()},
        )(),
    )

    assert len(annotations) == 1
    assert annotations[0].source == "scispacy_scibert"
    assert annotations[0].entity_type == "biomedical_entity"
    assert annotations[0].canonical_id == "C0017636"
    assert annotations[0].canonical_name == "Glioblastoma"
    assert annotations[0].confidence == 0.91


def test_scispacy_md_links_entities_to_umls_like_scibert() -> None:
    from bio_annotation.annotators.scispacy import (
        SCISPACY_LINKER_NAME_BY_ANNOTATOR,
        SCISPACY_MODEL_BY_ANNOTATOR,
    )

    # Both general models are linkers defaulting to UMLS; md uses the lighter model.
    assert SCISPACY_LINKER_NAME_BY_ANNOTATOR == {
        "scispacy_scibert": "umls",
        "scispacy_md": "umls",
    }
    assert SCISPACY_MODEL_BY_ANNOTATOR["scispacy_md"] == "en_core_sci_md"

    document = sample_document()
    response = [FakeScispacyEntity("glioblastoma", "ENTITY", 36, 48, [("C0017636", 0.9)])]
    annotations = annotate_with_scispacy_md(
        document,
        response=response,
        nlp=type("FakeNlp", (), {"get_pipe": lambda self, name: FakeScispacyLinker()})(),
    )

    assert len(annotations) == 1
    assert annotations[0].source == "scispacy_md"
    assert annotations[0].entity_type == "biomedical_entity"
    assert annotations[0].canonical_id == "C0017636"
    assert annotations[0].canonical_name == "Glioblastoma"


def test_scispacy_adapter_loads_configured_model() -> None:
    document = sample_document()
    loaded_models: list[str] = []

    class FakeNlp:
        def __call__(self, text: str) -> FakeScispacyDoc:
            assert text == document.text
            return FakeScispacyDoc([FakeScispacyEntity("PTEN", "PROTEIN", 0, 4)])

    def fake_loader(model: str) -> FakeNlp:
        loaded_models.append(model)
        return FakeNlp()

    annotations = annotate_with_scispacy(
        document,
        source="scispacy_jnlpba",
        model=SCISPACY_MODEL_BY_ANNOTATOR["scispacy_jnlpba"],
        model_loader=fake_loader,
    )

    assert loaded_models == [SCISPACY_MODEL_BY_ANNOTATOR["scispacy_jnlpba"]]
    assert annotations[0].source == "scispacy_jnlpba"
    assert annotations[0].entity_type == "gene"


@dataclass
class FakeStanzaEntity:
    text: str
    type: str
    start_char: int
    end_char: int


class FakeStanzaDoc:
    def __init__(self, ents: list[FakeStanzaEntity]) -> None:
        self.ents = ents


class FakeScispacyExtension:
    def __init__(self, kb_ents: list[tuple[str, float]] | None = None) -> None:
        self.kb_ents = kb_ents or []


@dataclass
class FakeScispacyEntity:
    text: str
    label_: str
    start_char: int
    end_char: int
    kb_ents: list[tuple[str, float]] | None = None

    def __post_init__(self) -> None:
        self._ = FakeScispacyExtension(self.kb_ents)


class FakeScispacyDoc:
    def __init__(self, ents: list[FakeScispacyEntity]) -> None:
        self.ents = ents


class FakeScispacyLinkedEntity:
    def __init__(self, canonical_name: str) -> None:
        self.canonical_name = canonical_name


class FakeScispacyLinker:
    def __init__(self) -> None:
        self.kb = type(
            "FakeKb",
            (),
            {"cui_to_entity": {"C0017636": FakeScispacyLinkedEntity("Glioblastoma")}},
        )()


def test_stanza_bc5cdr_normalizes_and_stamps_source() -> None:
    document = sample_document()
    entities = [
        FakeStanzaEntity("glioblastoma", "DISEASE", 15, 27),
        FakeStanzaEntity("cisplatin", "CHEMICAL", 40, 49),
    ]

    annotations = annotate_with_stanza(document, "bc5cdr", entities=entities)

    assert [a.entity_type for a in annotations] == ["disease", "drug"]
    assert all(a.source == "stanza_bc5cdr" for a in annotations)


def test_stanza_bionlp13cg_runs_pipeline() -> None:
    document = sample_document()
    captured: dict[str, str] = {}

    def fake_pipeline(text: str) -> FakeStanzaDoc:
        captured["text"] = text
        return FakeStanzaDoc([FakeStanzaEntity("PTEN", "GENE_OR_GENE_PRODUCT", 0, 4)])

    annotations = annotate_with_stanza(document, "bionlp13cg", pipeline=fake_pipeline)

    assert captured["text"] == document.text
    assert annotations[0].source == "stanza_bionlp13cg"
    assert annotations[0].entity_type == "gene"


def test_stanza_bionlp13cg_maps_documented_entity_types() -> None:
    document = sample_document()
    labels = [
        ("AMINO_ACID", "amino_acid"),
        ("ANATOMICAL_SYSTEM", "anatomical_system"),
        ("CANCER", "cancer"),
        ("CELL", "cell"),
        ("CELLULAR_COMPONENT", "cellular_component"),
        ("DEVELOPING_ANATOMICAL_STRUCTURE", "developing_anatomical_structure"),
        ("GENE_OR_GENE_PRODUCT", "gene"),
        ("IMMATERIAL_ANATOMICAL_ENTITY", "immaterial_anatomical_entity"),
        ("MULTI-TISSUE_STRUCTURE", "multi_tissue_structure"),
        ("ORGAN", "organ"),
        ("ORGANISM", "species"),
        ("ORGANISM_SUBDIVISION", "organism_subdivision"),
        ("ORGANISM_SUBSTANCE", "organism_substance"),
        ("PATHOLOGICAL_FORMATION", "pathological_formation"),
        ("SIMPLE_CHEMICAL", "drug"),
        ("TISSUE", "tissue"),
    ]
    entities = [
        FakeStanzaEntity("PTEN", label, 0, 4)
        for label, _ in labels
    ]

    annotations = annotate_with_stanza(document, "bionlp13cg", entities=entities)

    assert all(annotation.source == "stanza_bionlp13cg" for annotation in annotations)
    assert [annotation.entity_type for annotation in annotations] == [
        expected for _, expected in labels
    ]


def test_stanza_jnlpba_loads_fixed_model_and_keeps_cell_type_distinct() -> None:
    document = sample_document()
    loaded: list[tuple[str, str]] = []

    def fake_loader(package: str, model: str):
        loaded.append((package, model))
        return lambda text: FakeStanzaDoc(
            [
                FakeStanzaEntity("PTEN", "PROTEIN", 0, 4),
                FakeStanzaEntity("DNA", "DNA", 5, 8),
                FakeStanzaEntity("RNA", "RNA", 9, 12),
                FakeStanzaEntity("T cells", "CELL_TYPE", 15, 22),
                FakeStanzaEntity("HeLa", "CELL_LINE", 23, 27),
            ]
        )

    annotations = annotate_with_stanza(
        document, "jnlpba", package="genia", pipeline_loader=fake_loader
    )

    assert loaded == [("genia", "jnlpba")]
    assert all(a.source == "stanza_jnlpba" for a in annotations)
    # CELL_TYPE must stay cell_type, not be mislabeled as cell_line.
    assert [a.entity_type for a in annotations] == [
        "gene",
        "dna",
        "rna",
        "cell_type",
        "cell_line",
    ]


def test_stanza_i2b2_maps_clinical_types_and_stamps_source() -> None:
    document = sample_document()
    entities = [
        FakeStanzaEntity("glioblastoma", "PROBLEM", 15, 27),
        FakeStanzaEntity("MRI", "TEST", 0, 3),
        FakeStanzaEntity("cisplatin", "TREATMENT", 40, 49),
    ]

    annotations = annotate_with_stanza(document, "i2b2", entities=entities)

    assert [a.entity_type for a in annotations] == ["problem", "test", "treatment"]
    assert all(a.source == "stanza_i2b2" for a in annotations)


def test_stanza_i2b2_defaults_to_mimic_tokenizer_package() -> None:
    from bio_annotation.entity_proposal.stanza_proposer import default_package_for_model

    loaded: list[tuple[str, str]] = []

    def fake_loader(package: str, model: str):
        loaded.append((package, model))
        return lambda text: FakeStanzaDoc([])

    annotate_with_stanza(sample_document(), "i2b2", pipeline_loader=fake_loader)

    # i2b2 is clinical, so it must default to the MIMIC tokenizer, not CRAFT.
    assert loaded == [("mimic", "i2b2")]
    assert default_package_for_model("i2b2") == "mimic"
    assert default_package_for_model("bc5cdr") == "craft"


def test_stanza_i2b2_trims_leading_determiners_and_drops_noise() -> None:
    document = sample_document()
    entities = [
        FakeStanzaEntity("a stop codon", "TREATMENT", 0, 12),
        FakeStanzaEntity("This protein", "TEST", 13, 25),
        FakeStanzaEntity("the breast and ovarian cancer", "PROBLEM", 26, 55),
        FakeStanzaEntity("a", "PROBLEM", 56, 57),
        FakeStanzaEntity("-", "PROBLEM", 58, 59),
    ]

    annotations = annotate_with_stanza(document, "i2b2", entities=entities)

    spans = [a.span_text for a in annotations]
    assert spans == ["stop codon", "protein", "breast and ovarian cancer"]


def test_stanza_radiology_maps_clinical_types_and_stamps_source() -> None:
    document = sample_document()
    entities = [
        FakeStanzaEntity("liver", "ANATOMY", 0, 5),
        FakeStanzaEntity("right", "ANATOMY_MODIFIER", 6, 11),
        FakeStanzaEntity("mass", "OBSERVATION", 12, 16),
        FakeStanzaEntity("large", "OBSERVATION_MODIFIER", 17, 22),
        FakeStanzaEntity("possible", "UNCERTAINTY", 23, 31),
    ]

    annotations = annotate_with_stanza(document, "radiology", entities=entities)

    assert [a.entity_type for a in annotations] == [
        "anatomical",
        "anatomy_modifier",
        "observation",
        "observation_modifier",
        "uncertainty",
    ]
    assert all(a.source == "stanza_radiology" for a in annotations)


def test_stanza_radiology_defaults_to_mimic_tokenizer_package() -> None:
    from bio_annotation.entity_proposal.stanza_proposer import default_package_for_model

    loaded: list[tuple[str, str]] = []

    def fake_loader(package: str, model: str):
        loaded.append((package, model))
        return lambda text: FakeStanzaDoc([])

    annotate_with_stanza(sample_document(), "radiology", pipeline_loader=fake_loader)

    # radiology is clinical, so it must default to the MIMIC tokenizer, not CRAFT.
    assert loaded == [("mimic", "radiology")]
    assert default_package_for_model("radiology") == "mimic"
    assert default_package_for_model("bc5cdr") == "craft"


def test_stanza_radiology_trims_leading_determiners_and_drops_noise() -> None:
    document = sample_document()
    entities = [
        FakeStanzaEntity("the large mass", "OBSERVATION", 0, 14),
        FakeStanzaEntity("a", "OBSERVATION", 15, 16),
        FakeStanzaEntity("-", "ANATOMY", 17, 18),
        FakeStanzaEntity("liver", "ANATOMY", 19, 24),
    ]

    annotations = annotate_with_stanza(document, "radiology", entities=entities)

    assert [a.span_text for a in annotations] == ["large mass", "liver"]


def test_stanza_anatem_maps_anatomy_and_stamps_source() -> None:
    document = sample_document()
    entities = [
        FakeStanzaEntity("liver", "ANATOMY", 0, 5),
        FakeStanzaEntity("lymph nodes", "ANATOMY", 6, 17),
    ]

    annotations = annotate_with_stanza(document, "anatem", entities=entities)

    assert [a.entity_type for a in annotations] == ["anatomical", "anatomical"]
    assert all(a.source == "stanza_anatem" for a in annotations)


def test_stanza_anatem_uses_craft_biomedical_tokenizer_package() -> None:
    loaded: list[tuple[str, str]] = []

    def fake_loader(package: str, model: str):
        loaded.append((package, model))
        return lambda text: FakeStanzaDoc([])

    annotate_with_stanza(sample_document(), "anatem", pipeline_loader=fake_loader)

    # AnatEM is biomedical, so it uses the default CRAFT tokenizer (not MIMIC).
    assert loaded == [("craft", "anatem")]


def test_bent_adapter_parses_brat_ner_and_nel_output() -> None:
    document = sample_document()
    response = (
        "T1\tgene 0 4\tPTEN\n"
        "N1\tReference T1 NCBIGene:5728\tPTEN\n"
        "T2\tdisease 15 27\tglioblastoma\n"
        "N2\tReference T2 MESH:D005909\tglioblastoma\n"
        "T3\tchemical 34 40\tmiR-21\n"
    )

    annotations = annotate_with_bent(document, response=response)

    assert len(annotations) == 3
    assert all(annotation.source == "bent" for annotation in annotations)
    assert annotations[0].entity_type == "gene"
    assert annotations[0].start == 0
    assert annotations[0].end == 4
    assert annotations[0].canonical_id == "NCBIGene:5728"
    assert annotations[0].canonical_name == "PTEN"
    assert annotations[1].entity_type == "disease"
    assert annotations[1].canonical_id == "MESH:D005909"
    assert annotations[2].entity_type == "drug"
    assert annotations[2].canonical_id is None


def test_bent_adapter_preserves_reported_offsets_without_relocating() -> None:
    # "glioblastoma" occurs twice (first at offset 15). BENT reports the second
    # mention with a span that does not byte-match the slice. The adapter must
    # keep BENT's reported location instead of silently searching span_text and
    # relocating to the first, unrelated occurrence.
    document = sample_document()
    assert document.text.count("glioblastoma") == 2
    assert document.text[62:75] != "glioblastoma"
    response = "T1\tdisease 62 75\tglioblastoma\nN1\tReference T1 MESH:D005909\tglioblastoma\n"

    annotations = annotate_with_bent(document, response=response)

    assert len(annotations) == 1
    assert (annotations[0].start, annotations[0].end) == (62, 75)
    assert annotations[0].start != 15  # not relocated to the first occurrence


def test_bent_adapter_uses_request_fn() -> None:
    document = sample_document()
    calls: list[Document] = []

    def fake_request(doc: Document) -> str:
        calls.append(doc)
        return "T1\tgene 0 4\tPTEN\nN1\tReference T1 NCBIGene:5728\tPTEN\n"

    annotations = annotate_with_bent(document, request_fn=fake_request)

    assert calls == [document]
    assert len(annotations) == 1
    assert annotations[0].canonical_id == "NCBIGene:5728"


def test_bent_call_runs_isolated_subprocess_and_reads_ann(monkeypatch) -> None:
    document = sample_document()
    commands: list[list[str]] = []

    class Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command: list[str], **kwargs: object) -> Completed:
        commands.append(command)
        out_dir = command[command.index("--output-dir") + 1]
        Path(out_dir, "document.ann").write_text(
            "T1\tgene 0 4\tPTEN\nN1\tReference T1 NCBIGene:5728\tPTEN\n",
            encoding="utf-8",
        )
        return Completed()

    monkeypatch.setattr("bio_annotation.entity_proposal.bent_proposer.subprocess.run", fake_run)

    payload = call_bent(
        document,
        types={"gene": "ncbi_gene", "chemical": "chebi"},
        mode="ner_nel",
        project="tools/bent",
        timeout=12,
    )

    assert "NCBIGene:5728" in payload
    assert commands
    command = commands[0]
    assert command[:3] == ["uv", "run", "--project"]
    # The wrapper script must live inside the resolved project dir, not be hard-coded.
    assert command[3] == str(Path("tools/bent").resolve())
    assert command[command.index("python") + 1] == str(Path("tools/bent").resolve() / "run_bent.py")
    assert command[command.index("--mode") + 1] == "ner_nel"
    assert command[command.index("--types") + 1] == "chemical:chebi,gene:ncbi_gene"


def test_bent_call_derives_script_from_project(tmp_path, monkeypatch) -> None:
    document = sample_document()
    project = tmp_path / "custom_bent"
    project.mkdir()
    (project / "run_bent.py").write_text("# stub wrapper\n", encoding="utf-8")

    commands: list[list[str]] = []

    class Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command: list[str], **kwargs: object) -> Completed:
        commands.append(command)
        out_dir = command[command.index("--output-dir") + 1]
        Path(out_dir, "document.ann").write_text("T1\tgene 0 4\tPTEN\n", encoding="utf-8")
        return Completed()

    monkeypatch.setattr("bio_annotation.entity_proposal.bent_proposer.subprocess.run", fake_run)

    call_bent(document, project=str(project), timeout=12)

    command = commands[0]
    assert command[3] == str(project)
    assert command[command.index("python") + 1] == str(project / "run_bent.py")


def test_bent_call_raises_when_wrapper_script_missing(tmp_path) -> None:
    project = tmp_path / "empty_project"
    project.mkdir()

    with pytest.raises(RuntimeError, match="wrapper script not found"):
        call_bent(sample_document(), project=str(project))


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


def test_cli_accepts_global_log_level_before_subcommand() -> None:
    stream = StringIO()
    with redirect_stdout(stream):
        exit_code = main(["--log-level", "ERROR", "inspect-config"])

    output = json.loads(stream.getvalue())
    assert exit_code == 0
    assert output["input_mode"] == "pmids"


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
