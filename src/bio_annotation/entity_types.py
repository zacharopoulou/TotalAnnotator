from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

AnnotationTask = Literal["NER", "NEN"]
NormalizationStatus = Literal["normalized", "preserved_if_returned", "not_returned"]


@dataclass(frozen=True)
class AnnotatorEntityTypeSpec:
    annotator: str
    annotator_label: str
    source_entity_type: str
    canonical_entity_type: str
    database_ids: tuple[str, ...]


@dataclass(frozen=True)
class AnnotatorCapability:
    label: str
    tasks: tuple[AnnotationTask, ...]
    entity_types: tuple[str, ...]
    normalization_status: NormalizationStatus
    normalization_databases: dict[str, tuple[str, ...]]
    normalization_fields: tuple[str, ...]


# MACCROBAT clinical label set (41 labels), shared so any clinical NER annotator
# trained on MACCROBAT (Clinical-AI-Apollo/Medical-NER, d4data/biomedical-ner-all,
# ...) can reuse it without duplicating. DISEASE_DISORDER and MEDICATION map to
# this pipeline's canonical types; the rest are declared as their own clinical types.
MACCROBAT_CANONICAL_OVERRIDES: dict[str, str] = {
    "DISEASE_DISORDER": "disease",
    "MEDICATION": "drug",
}
MACCROBAT_LABELS: tuple[str, ...] = (
    "DISEASE_DISORDER",
    "MEDICATION",
    "ACTIVITY",
    "ADMINISTRATION",
    "AGE",
    "AREA",
    "BIOLOGICAL_ATTRIBUTE",
    "BIOLOGICAL_STRUCTURE",
    "CLINICAL_EVENT",
    "COLOR",
    "COREFERENCE",
    "DATE",
    "DETAILED_DESCRIPTION",
    "DIAGNOSTIC_PROCEDURE",
    "DISTANCE",
    "DOSAGE",
    "DURATION",
    "FAMILY_HISTORY",
    "FREQUENCY",
    "HEIGHT",
    "HISTORY",
    "LAB_VALUE",
    "MASS",
    "NONBIOLOGICAL_LOCATION",
    "OCCUPATION",
    "OTHER_ENTITY",
    "OTHER_EVENT",
    "OUTCOME",
    "PERSONAL_BACKGROUND",
    "QUALITATIVE_CONCEPT",
    "QUANTITATIVE_CONCEPT",
    "SEVERITY",
    "SEX",
    "SHAPE",
    "SIGN_SYMPTOM",
    "SUBJECT",
    "TEXTURE",
    "THERAPEUTIC_PROCEDURE",
    "TIME",
    "VOLUME",
    "WEIGHT",
)

STANZA_ENTITY_TYPE_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("stanza_bc5cdr", "Stanza BC5CDR", "Chemical", "drug"),
    ("stanza_bc5cdr", "Stanza BC5CDR", "Disease", "disease"),
    ("stanza_bionlp13cg", "Stanza BioNLP13CG", "Amino acid", "amino_acid"),
    ("stanza_bionlp13cg", "Stanza BioNLP13CG", "Anatomical system", "anatomical_system"),
    ("stanza_bionlp13cg", "Stanza BioNLP13CG", "Cancer", "cancer"),
    ("stanza_bionlp13cg", "Stanza BioNLP13CG", "Cell", "cell"),
    ("stanza_bionlp13cg", "Stanza BioNLP13CG", "Cellular component", "cellular_component"),
    (
        "stanza_bionlp13cg",
        "Stanza BioNLP13CG",
        "Developing anatomical structure",
        "developing_anatomical_structure",
    ),
    ("stanza_bionlp13cg", "Stanza BioNLP13CG", "Gene or gene product", "gene"),
    (
        "stanza_bionlp13cg",
        "Stanza BioNLP13CG",
        "Immaterial anatomical entity",
        "immaterial_anatomical_entity",
    ),
    ("stanza_bionlp13cg", "Stanza BioNLP13CG", "Multi-tissue structure", "multi_tissue_structure"),
    ("stanza_bionlp13cg", "Stanza BioNLP13CG", "Organ", "organ"),
    ("stanza_bionlp13cg", "Stanza BioNLP13CG", "Organism", "species"),
    ("stanza_bionlp13cg", "Stanza BioNLP13CG", "Organism subdivision", "organism_subdivision"),
    ("stanza_bionlp13cg", "Stanza BioNLP13CG", "Organism substance", "organism_substance"),
    ("stanza_bionlp13cg", "Stanza BioNLP13CG", "Pathological formation", "pathological_formation"),
    ("stanza_bionlp13cg", "Stanza BioNLP13CG", "Simple chemical", "drug"),
    ("stanza_bionlp13cg", "Stanza BioNLP13CG", "Tissue", "tissue"),
    ("stanza_jnlpba", "Stanza JNLPBA", "Protein", "gene"),
    ("stanza_jnlpba", "Stanza JNLPBA", "DNA", "dna"),
    ("stanza_jnlpba", "Stanza JNLPBA", "RNA", "rna"),
    ("stanza_jnlpba", "Stanza JNLPBA", "Cell line", "cell_line"),
    ("stanza_jnlpba", "Stanza JNLPBA", "Cell type", "cell_type"),
    # Stanza i2b2 is a clinical model (2010 i2b2/VA) emitting problem / test /
    # treatment, the same clinical categories ClinicalBERT uses.
    ("stanza_i2b2", "Stanza i2b2", "Problem", "problem"),
    ("stanza_i2b2", "Stanza i2b2", "Test", "test"),
    ("stanza_i2b2", "Stanza i2b2", "Treatment", "treatment"),
)


ANNOTATOR_ENTITY_TYPE_SPECS: tuple[AnnotatorEntityTypeSpec, ...] = (
    AnnotatorEntityTypeSpec("pubtator3", "PubTator3", "Gene / protein", "gene", ("NCBI Gene",)),
    AnnotatorEntityTypeSpec("pubtator3", "PubTator3", "Disease", "disease", ("MeSH",)),
    AnnotatorEntityTypeSpec("pubtator3", "PubTator3", "Chemical / drug", "drug", ("MeSH",)),
    AnnotatorEntityTypeSpec("pubtator3", "PubTator3", "Species", "species", ("NCBI Taxonomy",)),
    AnnotatorEntityTypeSpec(
        "pubtator3",
        "PubTator3",
        "Variant / mutation",
        "variant",
        ("dbSNP", "ClinGen Allele Registry"),
    ),
    AnnotatorEntityTypeSpec("pubtator3", "PubTator3", "Cell line", "cell_line", ("Cellosaurus",)),
    AnnotatorEntityTypeSpec("bern2", "BERN2", "Gene / protein", "gene", ("NCBI Gene",)),
    AnnotatorEntityTypeSpec("bern2", "BERN2", "Disease", "disease", ("MeSH",)),
    AnnotatorEntityTypeSpec("bern2", "BERN2", "Drug", "drug", ("DrugBank",)),
    AnnotatorEntityTypeSpec("bern2", "BERN2", "Species", "species", ("NCBI Taxonomy",)),
    AnnotatorEntityTypeSpec("bern2", "BERN2", "Mutation / variant", "variant", ("dbSNP",)),
    AnnotatorEntityTypeSpec("bern2", "BERN2", "Cell line", "cell_line", ("Cellosaurus",)),
    AnnotatorEntityTypeSpec("bern2", "BERN2", "Cell type", "cell_type", ("Cell Ontology",)),
    AnnotatorEntityTypeSpec("bern2", "BERN2", "DNA", "dna", ()),
    AnnotatorEntityTypeSpec("bern2", "BERN2", "RNA", "rna", ()),
    AnnotatorEntityTypeSpec("flair", "Flair / HunFlair", "Gene / protein", "gene", ()),
    AnnotatorEntityTypeSpec("flair", "Flair / HunFlair", "Disease", "disease", ()),
    AnnotatorEntityTypeSpec("flair", "Flair / HunFlair", "Chemical / drug", "drug", ()),
    AnnotatorEntityTypeSpec("flair", "Flair / HunFlair", "Species", "species", ()),
    AnnotatorEntityTypeSpec("flair", "Flair / HunFlair", "Cell line", "cell_line", ()),
    AnnotatorEntityTypeSpec("aioner", "AIONER", "Gene", "gene", ()),
    AnnotatorEntityTypeSpec("aioner", "AIONER", "Chemical", "drug", ()),
    AnnotatorEntityTypeSpec("aioner", "AIONER", "Disease", "disease", ()),
    AnnotatorEntityTypeSpec("aioner", "AIONER", "Species", "species", ()),
    AnnotatorEntityTypeSpec("aioner", "AIONER", "Variant", "variant", ()),
    AnnotatorEntityTypeSpec("aioner", "AIONER", "CellLine", "cell_line", ()),
    # ClinicalBERT (i2b2) emits problem / test / treatment. These are clinical
    # categories with no exact match in the canonical biomedical set (problem is
    # broader than disease, treatment broader than drug), so they are kept as their
    # own types rather than forced into disease/drug.
    AnnotatorEntityTypeSpec("clinicalbert", "ClinicalBERT", "problem", "problem", ()),
    AnnotatorEntityTypeSpec("clinicalbert", "ClinicalBERT", "test", "test", ()),
    AnnotatorEntityTypeSpec("clinicalbert", "ClinicalBERT", "treatment", "treatment", ()),
    # Clinical-AI-Apollo/Medical-NER entity types are generated from the shared
    # MACCROBAT_LABELS: DISEASE_DISORDER/MEDICATION map to canonical disease/drug,
    # every other clinical label becomes its own first-class type.
    *(
        AnnotatorEntityTypeSpec(
            "apollo",
            "Clinical-AI-Apollo Medical-NER",
            label.replace("_", " "),
            MACCROBAT_CANONICAL_OVERRIDES.get(label, label.lower()),
            (),
        )
        for label in MACCROBAT_LABELS
    ),
    # d4data/biomedical-ner-all uses the same MACCROBAT clinical label family.
    *(
        AnnotatorEntityTypeSpec(
            "d4data",
            "d4data biomedical-ner-all",
            label.replace("_", " "),
            MACCROBAT_CANONICAL_OVERRIDES.get(label, label.lower()),
            (),
        )
        for label in MACCROBAT_LABELS
    ),
    *(
        AnnotatorEntityTypeSpec(annotator, annotator_label, source_type, canonical_type, ())
        for annotator, annotator_label, source_type, canonical_type in STANZA_ENTITY_TYPE_SPECS
    ),
)


ENTITY_TYPE_DISPLAY_NAMES: dict[str, str] = {
    "gene": "Gene / protein",
    "disease": "Disease",
    "drug": "Chemical / drug",
    "species": "Species",
    "variant": "Variant / mutation",
    "cell_line": "Cell line",
    "cell_type": "Cell type",
    "dna": "DNA",
    "rna": "RNA",
    "cell": "Cell",
    "cancer": "Cancer",
    "amino_acid": "Amino acid",
    "anatomical_system": "Anatomical system",
    "cellular_component": "Cellular component",
    "developing_anatomical_structure": "Developing anatomical structure",
    "immaterial_anatomical_entity": "Immaterial anatomical entity",
    "multi_tissue_structure": "Multi-tissue structure",
    "organ": "Organ",
    "organism_subdivision": "Organism subdivision",
    "organism_substance": "Organism substance",
    "pathological_formation": "Pathological formation",
    "tissue": "Tissue",
}
ENTITY_TYPE_CHOICES: tuple[tuple[str, str], ...] = tuple(
    (entity_type, ENTITY_TYPE_DISPLAY_NAMES[entity_type])
    for entity_type in (
        "gene",
        "disease",
        "drug",
        "species",
        "variant",
        "cell_line",
        "cell_type",
        "dna",
        "rna",
    )
)
ENTITY_TYPE_ALIASES: dict[str, str] = {
    re.sub(r"[^a-z0-9]+", "_", spec.source_entity_type.strip().lower()).strip("_"): spec.canonical_entity_type
    for spec in ANNOTATOR_ENTITY_TYPE_SPECS
}
ENTITY_TYPE_ALIASES.update({canonical: canonical for canonical in ENTITY_TYPE_DISPLAY_NAMES})
ENTITY_TYPE_ALIASES.update(
    {
        "cellline": "cell_line",
        "cell_line": "cell_line",
        "celltype": "cell_type",
        "cell_type": "cell_type",
        "chemical": "drug",
        "drug": "drug",
        "gene": "gene",
        "protein": "gene",
        "mutation": "variant",
        "variant": "variant",
        "dna": "dna",
        "rna": "rna",
    }
)


ANNOTATOR_CAPABILITIES: dict[str, AnnotatorCapability] = {
    "pubtator3": AnnotatorCapability(
        label="PubTator3",
        tasks=("NER", "NEN"),
        entity_types=tuple(
            spec.canonical_entity_type
            for spec in ANNOTATOR_ENTITY_TYPE_SPECS
            if spec.annotator == "pubtator3"
        ),
        normalization_status="normalized",
        normalization_databases={
            spec.canonical_entity_type: spec.database_ids
            for spec in ANNOTATOR_ENTITY_TYPE_SPECS
            if spec.annotator == "pubtator3"
        },
        normalization_fields=(
            "BioC infons.identifier",
            "annotation.identifier",
            "annotation.id",
            "PubAnnotation denotations[].obj suffix",
            "PubTator text column 6",
        ),
    ),
    "bern2": AnnotatorCapability(
        label="BERN2",
        tasks=("NER", "NEN"),
        entity_types=tuple(
            spec.canonical_entity_type
            for spec in ANNOTATOR_ENTITY_TYPE_SPECS
            if spec.annotator == "bern2"
        ),
        normalization_status="normalized",
        normalization_databases={
            spec.canonical_entity_type: spec.database_ids
            for spec in ANNOTATOR_ENTITY_TYPE_SPECS
            if spec.annotator == "bern2"
        },
        normalization_fields=("id", "db_id", "identifier", "normalizedName"),
    ),
    "flair": AnnotatorCapability(
        label="Flair / HunFlair",
        tasks=("NER",),
        entity_types=tuple(
            spec.canonical_entity_type
            for spec in ANNOTATOR_ENTITY_TYPE_SPECS
            if spec.annotator == "flair"
        ),
        normalization_status="not_returned",
        normalization_databases={
            spec.canonical_entity_type: spec.database_ids
            for spec in ANNOTATOR_ENTITY_TYPE_SPECS
            if spec.annotator == "flair"
        },
        normalization_fields=(),
    ),
    "aioner": AnnotatorCapability(
        label="AIONER",
        tasks=("NER",),
        entity_types=tuple(
            spec.canonical_entity_type
            for spec in ANNOTATOR_ENTITY_TYPE_SPECS
            if spec.annotator == "aioner"
        ),
        normalization_status="not_returned",
        normalization_databases={
            spec.canonical_entity_type: spec.database_ids
            for spec in ANNOTATOR_ENTITY_TYPE_SPECS
            if spec.annotator == "aioner"
        },
        normalization_fields=(),
    ),
    "clinicalbert": AnnotatorCapability(
        label="ClinicalBERT",
        tasks=("NER",),
        entity_types=tuple(
            spec.canonical_entity_type
            for spec in ANNOTATOR_ENTITY_TYPE_SPECS
            if spec.annotator == "clinicalbert"
        ),
        normalization_status="not_returned",
        normalization_databases={
            spec.canonical_entity_type: spec.database_ids
            for spec in ANNOTATOR_ENTITY_TYPE_SPECS
            if spec.annotator == "clinicalbert"
        },
        normalization_fields=(),
    ),
    "apollo": AnnotatorCapability(
        label="Clinical-AI-Apollo Medical-NER",
        tasks=("NER",),
        entity_types=tuple(
            spec.canonical_entity_type
            for spec in ANNOTATOR_ENTITY_TYPE_SPECS
            if spec.annotator == "apollo"
        ),
        normalization_status="not_returned",
        normalization_databases={
            spec.canonical_entity_type: spec.database_ids
            for spec in ANNOTATOR_ENTITY_TYPE_SPECS
            if spec.annotator == "apollo"
        },
        normalization_fields=(),
    ),
    "d4data": AnnotatorCapability(
        label="d4data biomedical-ner-all",
        tasks=("NER",),
        entity_types=tuple(
            spec.canonical_entity_type
            for spec in ANNOTATOR_ENTITY_TYPE_SPECS
            if spec.annotator == "d4data"
        ),
        normalization_status="not_returned",
        normalization_databases={
            spec.canonical_entity_type: spec.database_ids
            for spec in ANNOTATOR_ENTITY_TYPE_SPECS
            if spec.annotator == "d4data"
        },
        normalization_fields=(),
    ),
    "medcat": AnnotatorCapability(
        label="MedCAT",
        tasks=("NER", "NEN"),
        # MedCAT's entity types depend on the loaded model pack (UMLS/SNOMED), so
        # they pass through as returned rather than mapping to the canonical set.
        entity_types=tuple(
            spec.canonical_entity_type
            for spec in ANNOTATOR_ENTITY_TYPE_SPECS
            if spec.annotator == "medcat"
        ),
        normalization_status="normalized",
        normalization_databases={
            spec.canonical_entity_type: spec.database_ids
            for spec in ANNOTATOR_ENTITY_TYPE_SPECS
            if spec.annotator == "medcat"
        },
        normalization_fields=("cui",),
    ),
    "stanza_bc5cdr": AnnotatorCapability(
        label="Stanza BC5CDR",
        tasks=("NER",),
        entity_types=tuple(
            dict.fromkeys(
                spec.canonical_entity_type
                for spec in ANNOTATOR_ENTITY_TYPE_SPECS
                if spec.annotator == "stanza_bc5cdr"
            )
        ),
        normalization_status="not_returned",
        normalization_databases={
            spec.canonical_entity_type: spec.database_ids
            for spec in ANNOTATOR_ENTITY_TYPE_SPECS
            if spec.annotator == "stanza_bc5cdr"
        },
        normalization_fields=(),
    ),
    "stanza_bionlp13cg": AnnotatorCapability(
        label="Stanza BioNLP13CG",
        tasks=("NER",),
        entity_types=tuple(
            dict.fromkeys(
                spec.canonical_entity_type
                for spec in ANNOTATOR_ENTITY_TYPE_SPECS
                if spec.annotator == "stanza_bionlp13cg"
            )
        ),
        normalization_status="not_returned",
        normalization_databases={
            spec.canonical_entity_type: spec.database_ids
            for spec in ANNOTATOR_ENTITY_TYPE_SPECS
            if spec.annotator == "stanza_bionlp13cg"
        },
        normalization_fields=(),
    ),
    "stanza_jnlpba": AnnotatorCapability(
        label="Stanza JNLPBA",
        tasks=("NER",),
        entity_types=tuple(
            dict.fromkeys(
                spec.canonical_entity_type
                for spec in ANNOTATOR_ENTITY_TYPE_SPECS
                if spec.annotator == "stanza_jnlpba"
            )
        ),
        normalization_status="not_returned",
        normalization_databases={
            spec.canonical_entity_type: spec.database_ids
            for spec in ANNOTATOR_ENTITY_TYPE_SPECS
            if spec.annotator == "stanza_jnlpba"
        },
        normalization_fields=(),
    ),
    "stanza_i2b2": AnnotatorCapability(
        label="Stanza i2b2",
        tasks=("NER",),
        entity_types=tuple(
            dict.fromkeys(
                spec.canonical_entity_type
                for spec in ANNOTATOR_ENTITY_TYPE_SPECS
                if spec.annotator == "stanza_i2b2"
            )
        ),
        normalization_status="not_returned",
        normalization_databases={
            spec.canonical_entity_type: spec.database_ids
            for spec in ANNOTATOR_ENTITY_TYPE_SPECS
            if spec.annotator == "stanza_i2b2"
        },
        normalization_fields=(),
    ),
}

ANNOTATOR_CHOICES: tuple[tuple[str, str], ...] = tuple(
    (annotator, capability.label)
    for annotator, capability in ANNOTATOR_CAPABILITIES.items()
)
ANNOTATOR_DISPLAY_NAMES: dict[str, str] = {
    annotator: capability.label for annotator, capability in ANNOTATOR_CAPABILITIES.items()
}
ANNOTATOR_ENTITY_TYPES: dict[str, set[str]] = {
    annotator: set(capability.entity_types)
    for annotator, capability in ANNOTATOR_CAPABILITIES.items()
}


def normalize_entity_type(label: Any) -> str:
    if label is None:
        return "unknown"

    normalized = re.sub(r"[^a-z0-9]+", "_", str(label).strip().lower()).strip("_")
    if not normalized:
        return "unknown"

    return ENTITY_TYPE_ALIASES.get(normalized, normalized)


def annotator_tasks(annotator: str) -> tuple[AnnotationTask, ...]:
    capability = ANNOTATOR_CAPABILITIES.get(annotator)
    return capability.tasks if capability else ()


def annotator_supports_nen(annotator: str) -> bool:
    return "NEN" in annotator_tasks(annotator)


def annotator_normalization_fields(annotator: str) -> tuple[str, ...]:
    capability = ANNOTATOR_CAPABILITIES.get(annotator)
    return capability.normalization_fields if capability else ()


def annotator_normalization_status(annotator: str) -> NormalizationStatus | None:
    capability = ANNOTATOR_CAPABILITIES.get(annotator)
    return capability.normalization_status if capability else None


def normalization_databases(entity_type: str, annotator: str | None = None) -> tuple[str, ...] | dict[str, tuple[str, ...]]:
    canonical = normalize_entity_type(entity_type)
    if canonical not in ENTITY_TYPE_DISPLAY_NAMES:
        return () if annotator is not None else {}
    if annotator is not None:
        capability = ANNOTATOR_CAPABILITIES.get(annotator)
        if capability is None:
            return ()
        return capability.normalization_databases.get(canonical, ())
    return {
        name: capability.normalization_databases.get(canonical, ())
        for name, capability in ANNOTATOR_CAPABILITIES.items()
    }
