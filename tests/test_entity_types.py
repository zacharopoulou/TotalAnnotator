from __future__ import annotations

from bio_annotation.entity_types import (
    ANNOTATOR_CAPABILITIES,
    ANNOTATOR_ENTITY_TYPE_SPECS,
    ANNOTATOR_ENTITY_TYPES,
    ENTITY_TYPE_DISPLAY_NAMES,
    annotator_normalization_fields,
    annotator_normalization_status,
    annotator_supports_nen,
    normalize_entity_type,
    normalization_databases,
)


def test_entity_type_specs_are_the_source_of_truth() -> None:
    assert (
        "pubtator3",
        "Variant / mutation",
        "variant",
        ("dbSNP", "ClinGen Allele Registry"),
    ) in {
        (spec.annotator, spec.source_entity_type, spec.canonical_entity_type, spec.database_ids)
        for spec in ANNOTATOR_ENTITY_TYPE_SPECS
    }
    assert (
        "bern2",
        "Drug",
        "drug",
        ("DrugBank",),
    ) in {
        (spec.annotator, spec.source_entity_type, spec.canonical_entity_type, spec.database_ids)
        for spec in ANNOTATOR_ENTITY_TYPE_SPECS
    }
    assert all(spec.canonical_entity_type != "mirna" for spec in ANNOTATOR_ENTITY_TYPE_SPECS)


def test_normalize_entity_type_uses_explicit_table_rows() -> None:
    assert normalize_entity_type("Gene / protein") == "gene"
    assert normalize_entity_type("Chemical / drug") == "drug"
    assert normalize_entity_type("Mutation / variant") == "variant"
    assert normalize_entity_type("Cell line") == "cell_line"
    assert normalize_entity_type("micro_rna") == "micro_rna"
    assert normalize_entity_type("chemical_entity") == "chemical_entity"


def test_normalize_entity_type_maps_pubtator3_raw_labels() -> None:
    assert normalize_entity_type("Chemical") == "drug"
    assert normalize_entity_type("Mutation") == "variant"
    assert normalize_entity_type("CellLine") == "cell_line"
    assert normalize_entity_type("ProteinMutation") == "variant"
    assert normalize_entity_type("DNAMutation") == "variant"
    assert normalize_entity_type("SNP") == "variant"


def test_annotator_capabilities_include_tasks_and_supported_entity_types() -> None:
    assert ANNOTATOR_CAPABILITIES["pubtator3"].tasks == ("NER", "NEN")
    assert ANNOTATOR_CAPABILITIES["bern2"].tasks == ("NER", "NEN")
    assert ANNOTATOR_CAPABILITIES["flair"].tasks == ("NER",)
    assert annotator_supports_nen("pubtator3") is True
    assert annotator_supports_nen("bern2") is True
    assert annotator_supports_nen("flair") is False
    assert "variant" in ANNOTATOR_ENTITY_TYPES["bern2"]
    assert "cell_line" not in ANNOTATOR_ENTITY_TYPES["bern2"]
    assert "mirna" not in ANNOTATOR_ENTITY_TYPES["flair"]


def test_entity_type_metadata_exposes_labels_and_adapter_normalization_behavior() -> None:
    assert ENTITY_TYPE_DISPLAY_NAMES["gene"] == "Gene / protein"
    assert ENTITY_TYPE_DISPLAY_NAMES["drug"] == "Chemical / drug"
    assert annotator_normalization_status("pubtator3") == "normalized"
    assert annotator_normalization_status("bern2") == "normalized"
    assert annotator_normalization_status("flair") == "not_returned"
    assert "BioC infons.identifier" in annotator_normalization_fields("pubtator3")
    assert "id" in annotator_normalization_fields("bern2")
    assert annotator_normalization_fields("flair") == ()


def test_normalization_databases_are_source_backed() -> None:
    assert normalization_databases("gene", "pubtator3") == ("NCBI Gene",)
    assert normalization_databases("Chemical / drug", "pubtator3") == ("MeSH",)
    assert normalization_databases("variant", "pubtator3") == ("dbSNP", "ClinGen Allele Registry")
    assert normalization_databases("Drug", "bern2") == ("DrugBank",)
    assert normalization_databases("species", "bern2") == ("NCBI Taxonomy",)
    assert normalization_databases("gene", "flair") == ()
