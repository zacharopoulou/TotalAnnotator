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
)


ENTITY_TYPE_DISPLAY_NAMES: dict[str, str] = {
    "gene": "Gene / protein",
    "disease": "Disease",
    "drug": "Chemical / drug",
    "species": "Species",
    "variant": "Variant / mutation",
    "cell_line": "Cell line",
}
ENTITY_TYPE_CHOICES: tuple[tuple[str, str], ...] = tuple(
    (entity_type, ENTITY_TYPE_DISPLAY_NAMES[entity_type])
    for entity_type in ("gene", "disease", "drug", "species", "variant", "cell_line")
)
ENTITY_TYPE_ALIASES: dict[str, str] = {
    re.sub(r"[^a-z0-9]+", "_", spec.source_entity_type.strip().lower()).strip("_"): spec.canonical_entity_type
    for spec in ANNOTATOR_ENTITY_TYPE_SPECS
}
ENTITY_TYPE_ALIASES.update({canonical: canonical for canonical in ENTITY_TYPE_DISPLAY_NAMES})


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
