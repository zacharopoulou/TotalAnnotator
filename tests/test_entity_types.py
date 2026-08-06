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
        "Cell type",
        "cell_type",
        ("Cell Ontology",),
    ) in {
        (spec.annotator, spec.source_entity_type, spec.canonical_entity_type, spec.database_ids)
        for spec in ANNOTATOR_ENTITY_TYPE_SPECS
    }
    assert (
        "bent",
        "chemical",
        "drug",
        ("ChEBI", "CTD Chemicals"),
    ) in {
        (spec.annotator, spec.source_entity_type, spec.canonical_entity_type, spec.database_ids)
        for spec in ANNOTATOR_ENTITY_TYPE_SPECS
    }
    assert all(spec.canonical_entity_type != "mirna" for spec in ANNOTATOR_ENTITY_TYPE_SPECS)


def test_normalize_entity_type_uses_explicit_table_rows() -> None:
    assert normalize_entity_type("Gene / protein") == "gene"
    assert normalize_entity_type("Chemical / drug") == "drug"
    assert normalize_entity_type("Mutation / variant") == "variant"
    assert normalize_entity_type("Mutation") == "variant"
    assert normalize_entity_type("CellLine") == "cell_line"
    assert normalize_entity_type("Cell line") == "cell_line"
    assert normalize_entity_type("cell_type") == "cell_type"
    assert normalize_entity_type("DNA") == "dna"
    assert normalize_entity_type("RNA") == "rna"
    assert normalize_entity_type("micro_rna") == "micro_rna"
    assert normalize_entity_type("chemical_entity") == "chemical_entity"
    assert normalize_entity_type("AMINO_ACID") == "amino_acid"
    assert normalize_entity_type("GENE_OR_GENE_PRODUCT") == "gene"
    assert normalize_entity_type("SIMPLE_CHEMICAL") == "drug"
    assert normalize_entity_type("CELL") == "cell"
    assert normalize_entity_type("CELL_TYPE") == "cell_type"
    assert normalize_entity_type("PATHOLOGICAL_FORMATION") == "pathological_formation"


def test_annotator_capabilities_include_tasks_and_supported_entity_types() -> None:
    assert ANNOTATOR_CAPABILITIES["pubtator3"].tasks == ("NER", "NEN")
    assert ANNOTATOR_CAPABILITIES["bern2"].tasks == ("NER", "NEN")
    assert ANNOTATOR_CAPABILITIES["flair"].tasks == ("NER",)
    assert annotator_supports_nen("pubtator3") is True
    assert annotator_supports_nen("bern2") is True
    assert annotator_supports_nen("flair") is False
    assert annotator_supports_nen("bent") is True
    assert "variant" in ANNOTATOR_ENTITY_TYPES["bern2"]
    assert {"cell_line", "cell_type", "dna", "rna"} <= ANNOTATOR_ENTITY_TYPES["bern2"]
    assert "cell_type" not in ANNOTATOR_ENTITY_TYPES["pubtator3"]
    assert "dna" not in ANNOTATOR_ENTITY_TYPES["flair"]
    assert "mirna" not in ANNOTATOR_ENTITY_TYPES["flair"]
    assert ANNOTATOR_ENTITY_TYPES["stanza_bc5cdr"] == {"drug", "disease"}
    assert ANNOTATOR_ENTITY_TYPES["stanza_jnlpba"] == {
        "gene",
        "dna",
        "rna",
        "cell_line",
        "cell_type",
    }
    assert {
        "amino_acid",
        "anatomical_system",
        "cancer",
        "cell",
        "cellular_component",
        "developing_anatomical_structure",
        "gene",
        "immaterial_anatomical_entity",
        "multi_tissue_structure",
        "organ",
        "species",
        "organism_subdivision",
        "organism_substance",
        "pathological_formation",
        "drug",
        "tissue",
    } <= ANNOTATOR_ENTITY_TYPES["stanza_bionlp13cg"]
    assert ANNOTATOR_ENTITY_TYPES["scispacy_jnlpba"] == {
        "gene",
        "dna",
        "rna",
        "cell_line",
        "cell_type",
    }
    assert ANNOTATOR_ENTITY_TYPES["scispacy_bc5cdr"] == {"disease", "drug"}
    assert {
        "amino_acid",
        "anatomical_system",
        "cancer",
        "cell",
        "cellular_component",
        "developing_anatomical_structure",
        "gene",
        "immaterial_anatomical_entity",
        "multi_tissue_structure",
        "organ",
        "species",
        "organism_subdivision",
        "organism_substance",
        "pathological_formation",
        "drug",
        "tissue",
    } <= ANNOTATOR_ENTITY_TYPES["scispacy_bionlp13cg"]
    assert ANNOTATOR_ENTITY_TYPES["scispacy_scibert"] == {"biomedical_entity"}
    assert ANNOTATOR_CAPABILITIES["scispacy_scibert"].tasks == ("NER", "NEN")
    assert ANNOTATOR_CAPABILITIES["scispacy_jnlpba"].label == "scispaCy en_ner_jnlpba_md"
    assert ANNOTATOR_CAPABILITIES["scispacy_scibert"].label == "scispaCy en_core_sci_scibert"
    assert "bioprocess" in ANNOTATOR_ENTITY_TYPES["bent"]
    assert "cell_component" in ANNOTATOR_ENTITY_TYPES["bent"]


def test_entity_type_metadata_exposes_labels_and_adapter_normalization_behavior() -> None:
    assert ENTITY_TYPE_DISPLAY_NAMES["gene"] == "Gene / protein"
    assert ENTITY_TYPE_DISPLAY_NAMES["drug"] == "Chemical / drug"
    assert ENTITY_TYPE_DISPLAY_NAMES["biomedical_entity"] == "Biomedical entity"
    assert ENTITY_TYPE_DISPLAY_NAMES["cell"] == "Cell"
    assert ENTITY_TYPE_DISPLAY_NAMES["cancer"] == "Cancer"
    assert ENTITY_TYPE_DISPLAY_NAMES["pathological_formation"] == "Pathological formation"
    assert annotator_normalization_status("pubtator3") == "normalized"
    assert annotator_normalization_status("bern2") == "normalized"
    assert annotator_normalization_status("flair") == "not_returned"
    assert "BioC infons.identifier" in annotator_normalization_fields("pubtator3")
    assert "id" in annotator_normalization_fields("bern2")
    assert annotator_normalization_fields("flair") == ()
    assert annotator_normalization_status("bent") == "normalized"
    assert annotator_normalization_fields("bent") == ("BRAT N Reference lines",)


def test_normalization_databases_are_source_backed() -> None:
    assert normalization_databases("gene", "pubtator3") == ("NCBI Gene",)
    assert normalization_databases("Chemical / drug", "pubtator3") == ("MeSH",)
    assert normalization_databases("variant", "pubtator3") == ("dbSNP", "ClinGen Allele Registry")
    assert normalization_databases("Drug", "bern2") == ("DrugBank",)
    assert normalization_databases("cell_type", "bern2") == ("Cell Ontology",)
    assert normalization_databases("cell_line", "bern2") == ("Cellosaurus",)
    assert normalization_databases("species", "bern2") == ("NCBI Taxonomy",)
    assert normalization_databases("gene", "flair") == ()
    assert normalization_databases("chemical", "bent") == ("ChEBI", "CTD Chemicals")
