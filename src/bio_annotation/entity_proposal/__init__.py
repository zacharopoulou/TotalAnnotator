"""Annotator adapters and runner utilities."""

from __future__ import annotations

import sys
from typing import Any

from bio_annotation.entity_proposal.apollo_proposer import annotate_with_apollo
from bio_annotation.entity_proposal.bent_proposer import annotate_with_bent
from bio_annotation.entity_proposal.bern2_proposer import annotate_with_bern2
from bio_annotation.entity_proposal.biobert_proposer import annotate_with_biobert
from bio_annotation.entity_proposal.clinicalbert_proposer import annotate_with_clinicalbert
from bio_annotation.entity_proposal.d4data_proposer import annotate_with_d4data
from bio_annotation.entity_proposal.flair_proposer import annotate_with_flair
from bio_annotation.entity_proposal.medcat_proposer import annotate_with_medcat
from bio_annotation.entity_proposal.pubtator3_proposer import annotate_with_pubtator3
from bio_annotation.entity_proposal.scispacy_proposer import (
    annotate_with_scispacy_bc5cdr,
    annotate_with_scispacy_bionlp13cg,
    annotate_with_scispacy_craft,
    annotate_with_scispacy_jnlpba,
    annotate_with_scispacy_md,
    annotate_with_scispacy_scibert,
)
from bio_annotation.entity_proposal.stanza_proposer import (
    STANZA_ANNOTATORS,
    annotate_with_stanza,
    stanza_source,
)
from bio_annotation.schemas.document import Document
from bio_annotation.schemas.entity import Annotation

# AIONER's subprocess runner differs on Windows (see aioner_windows); resolve the
# same platform-specific implementation the annotators.aioner shim uses so this
# package's public API and run_all_annotators don't bypass it on Windows.
if sys.platform == "win32":
    from bio_annotation.entity_proposal.aioner_windows import annotate_with_aioner
else:
    from bio_annotation.entity_proposal.aioner_proposer import annotate_with_aioner


def run_all_annotators(
    document: Document,
    *,
    bern2_response: Any = None,
    bern2_request_fn: Any = None,
    bern2_endpoint: str | None = None,
    flair_spans: Any = None,
    flair_tagger: Any = None,
    flair_sentence_factory: Any = None,
    pubtator3_response: Any = None,
    pubtator3_request_fn: Any = None,
    pubtator3_endpoint: str | None = None,
    aioner_response: Any = None,
    aioner_request_fn: Any = None,
    bent_response: Any = None,
    bent_request_fn: Any = None,
    clinicalbert_response: Any = None,
    clinicalbert_request_fn: Any = None,
    clinicalbert_pipeline: Any = None,
    biobert_response: Any = None,
    biobert_request_fn: Any = None,
    biobert_pipelines: Any = None,
    apollo_response: Any = None,
    apollo_request_fn: Any = None,
    apollo_pipeline: Any = None,
    d4data_response: Any = None,
    d4data_request_fn: Any = None,
    d4data_pipeline: Any = None,
    medcat_response: Any = None,
    medcat_request_fn: Any = None,
    medcat_endpoint: str | None = None,
    scispacy_jnlpba_response: Any = None,
    scispacy_jnlpba_request_fn: Any = None,
    scispacy_jnlpba_nlp: Any = None,
    scispacy_bc5cdr_response: Any = None,
    scispacy_bc5cdr_request_fn: Any = None,
    scispacy_bc5cdr_nlp: Any = None,
    scispacy_bionlp13cg_response: Any = None,
    scispacy_bionlp13cg_request_fn: Any = None,
    scispacy_bionlp13cg_nlp: Any = None,
    scispacy_craft_response: Any = None,
    scispacy_craft_request_fn: Any = None,
    scispacy_craft_nlp: Any = None,
    scispacy_scibert_response: Any = None,
    scispacy_scibert_request_fn: Any = None,
    scispacy_scibert_nlp: Any = None,
    scispacy_md_response: Any = None,
    scispacy_md_request_fn: Any = None,
    scispacy_md_nlp: Any = None,
    stanza_entities: dict[str, Any] | None = None,  # model name -> entities
) -> dict[str, list[Annotation]]:
    """Run all configured annotator adapters and return normalized outputs."""

    results = {
        "bern2": annotate_with_bern2(
            document,
            response=bern2_response,
            request_fn=bern2_request_fn,
            endpoint=bern2_endpoint,
        ),
        "flair": annotate_with_flair(
            document,
            spans=flair_spans,
            tagger=flair_tagger,
            sentence_factory=flair_sentence_factory,
        ),
        "pubtator3": annotate_with_pubtator3(
            document,
            response=pubtator3_response,
            request_fn=pubtator3_request_fn,
            endpoint=pubtator3_endpoint,
        ),
    }
    # Only invoke AIONER when a response or request function is provided.
    if aioner_response is not None or aioner_request_fn is not None:
        results["aioner"] = annotate_with_aioner(
            document,
            response=aioner_response,
            request_fn=aioner_request_fn,
        )
    # Only invoke BENT when a response or request function is provided.
    if bent_response is not None or bent_request_fn is not None:
        results["bent"] = annotate_with_bent(
            document,
            response=bent_response,
            request_fn=bent_request_fn,
        )
    # Only invoke ClinicalBERT when a response, request function, or pipeline is provided.
    if (
        clinicalbert_response is not None
        or clinicalbert_request_fn is not None
        or clinicalbert_pipeline is not None
    ):
        results["clinicalbert"] = annotate_with_clinicalbert(
            document,
            response=clinicalbert_response,
            request_fn=clinicalbert_request_fn,
            pipeline=clinicalbert_pipeline,
        )
    # Only invoke BioBERT when a response, request function, or pipelines are provided.
    if (
        biobert_response is not None
        or biobert_request_fn is not None
        or biobert_pipelines is not None
    ):
        results["biobert"] = annotate_with_biobert(
            document,
            response=biobert_response,
            request_fn=biobert_request_fn,
            pipelines=biobert_pipelines,
        )
    # Only invoke apollo when a response, request function, or pipeline is provided.
    if (
        apollo_response is not None
        or apollo_request_fn is not None
        or apollo_pipeline is not None
    ):
        results["apollo"] = annotate_with_apollo(
            document,
            response=apollo_response,
            request_fn=apollo_request_fn,
            pipeline=apollo_pipeline,
        )
    # Only invoke d4data when a response, request function, or pipeline is provided.
    if (
        d4data_response is not None
        or d4data_request_fn is not None
        or d4data_pipeline is not None
    ):
        results["d4data"] = annotate_with_d4data(
            document,
            response=d4data_response,
            request_fn=d4data_request_fn,
            pipeline=d4data_pipeline,
        )
    # Only invoke MedCAT when a response, request function, or endpoint is provided.
    if (
        medcat_response is not None
        or medcat_request_fn is not None
        or medcat_endpoint is not None
    ):
        results["medcat"] = annotate_with_medcat(
            document,
            response=medcat_response,
            request_fn=medcat_request_fn,
            endpoint=medcat_endpoint,
        )
    if (
        scispacy_jnlpba_response is not None
        or scispacy_jnlpba_request_fn is not None
        or scispacy_jnlpba_nlp is not None
    ):
        results["scispacy_jnlpba"] = annotate_with_scispacy_jnlpba(
            document,
            response=scispacy_jnlpba_response,
            request_fn=scispacy_jnlpba_request_fn,
            nlp=scispacy_jnlpba_nlp,
        )
    if (
        scispacy_bc5cdr_response is not None
        or scispacy_bc5cdr_request_fn is not None
        or scispacy_bc5cdr_nlp is not None
    ):
        results["scispacy_bc5cdr"] = annotate_with_scispacy_bc5cdr(
            document,
            response=scispacy_bc5cdr_response,
            request_fn=scispacy_bc5cdr_request_fn,
            nlp=scispacy_bc5cdr_nlp,
        )
    if (
        scispacy_bionlp13cg_response is not None
        or scispacy_bionlp13cg_request_fn is not None
        or scispacy_bionlp13cg_nlp is not None
    ):
        results["scispacy_bionlp13cg"] = annotate_with_scispacy_bionlp13cg(
            document,
            response=scispacy_bionlp13cg_response,
            request_fn=scispacy_bionlp13cg_request_fn,
            nlp=scispacy_bionlp13cg_nlp,
        )
    if (
        scispacy_craft_response is not None
        or scispacy_craft_request_fn is not None
        or scispacy_craft_nlp is not None
    ):
        results["scispacy_craft"] = annotate_with_scispacy_craft(
            document,
            response=scispacy_craft_response,
            request_fn=scispacy_craft_request_fn,
            nlp=scispacy_craft_nlp,
        )
    if (
        scispacy_scibert_response is not None
        or scispacy_scibert_request_fn is not None
        or scispacy_scibert_nlp is not None
    ):
        results["scispacy_scibert"] = annotate_with_scispacy_scibert(
            document,
            response=scispacy_scibert_response,
            request_fn=scispacy_scibert_request_fn,
            nlp=scispacy_scibert_nlp,
        )
    if (
        scispacy_md_response is not None
        or scispacy_md_request_fn is not None
        or scispacy_md_nlp is not None
    ):
        results["scispacy_md"] = annotate_with_scispacy_md(
            document,
            response=scispacy_md_response,
            request_fn=scispacy_md_request_fn,
            nlp=scispacy_md_nlp,
        )
    for model, ents in (stanza_entities or {}).items():
        results[stanza_source(model)] = annotate_with_stanza(
            document, model, entities=ents
        )
    return results


def flatten_annotations(results: dict[str, list[Annotation]]) -> list[Annotation]:
    annotations: list[Annotation] = []
    for source in (
        "bern2",
        "flair",
        "pubtator3",
        "aioner",
        "bent",
        "clinicalbert",
        "biobert",
        "apollo",
        "d4data",
        "medcat",
        "scispacy_jnlpba",
        "scispacy_bc5cdr",
        "scispacy_bionlp13cg",
        "scispacy_craft",
        "scispacy_scibert",
        "scispacy_md",
        *STANZA_ANNOTATORS,
    ):
        annotations.extend(results.get(source, []))
    return annotations


__all__ = [
    "annotate_with_aioner",
    "annotate_with_apollo",
    "annotate_with_bent",
    "annotate_with_bern2",
    "annotate_with_biobert",
    "annotate_with_clinicalbert",
    "annotate_with_d4data",
    "annotate_with_flair",
    "annotate_with_medcat",
    "annotate_with_pubtator3",
    "annotate_with_scispacy_bc5cdr",
    "annotate_with_scispacy_bionlp13cg",
    "annotate_with_scispacy_craft",
    "annotate_with_scispacy_jnlpba",
    "annotate_with_scispacy_md",
    "annotate_with_scispacy_scibert",
    "annotate_with_stanza",
    "flatten_annotations",
    "run_all_annotators",
]
