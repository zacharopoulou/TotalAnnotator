# Biomedical and Clinical Annotation Workflow

## Overview

This repository implements a **fully automated biomedical/clinical annotation pipeline** for literature and, later, domain-specific case studies. The system is designed to annotate **entities** and **relations** without manual intervention in the main workflow.

The guiding principle is:

**multi-source candidate generation + ontology grounding + constrained LLM adjudication + deterministic validation + confidence-based output**

This avoids relying on a single model or unconstrained prompting, while keeping the pipeline fully automatic and extensible.

---

## Goals

* Detect biomedical and clinical entities from text.
* Normalize entities to standard ontology or database identifiers.
* Extract relations between validated entities.
* Produce structured, machine-readable annotations.
* Operate without manual annotation in the main pipeline.
* Support later domain-focused evaluation using manually curated papers.

---

## Scope

### Initial entity types

* Gene
* Protein
* miRNA
* Disease
* Drug
* Variant
* Biomarker
* Symptom
* Procedure
* Lab test

### Initial relation types

* associated_with
* regulates
* inhibits
* activates
* treats
* causes
* biomarker_of
* expressed_in
* no_relation

### Optional future attributes

* species
* negation
* temporality
* certainty
* experiencer

---

## High-Level Architecture

```text
Input document
  ↓
Sentence segmentation + offsets
  ↓
[Biomedical NER] + [Dictionary matcher] + [Regex rules] + [Optional LLM proposer]
  ↓
Merged entity candidates
  ↓
Ontology candidate retrieval
  ↓
LLM entity adjudication (accept/reject/type/ID)
  ↓
Deterministic entity validation
  ↓
Accepted normalized entities
  ↓
Type-constrained relation pair generation
  ↓
LLM relation adjudication
  ↓
Deterministic relation validation
  ↓
Confidence aggregation
  ↓
Final annotation JSON
```

---

## Pipeline Stages

## 1. Preprocessing

### Purpose

Prepare each document for downstream processing while preserving the original text and offsets.

### Tasks

* Split text into sections, paragraphs, and sentences.
* Normalize Unicode where needed.
* Preserve original character offsets.
* Keep original casing.
* Attach document metadata such as PMID, title, year, and source.

### Output

Structured sentence-level records with offsets.

Example:

```json
{
  "document_id": "PMID:12345678",
  "sentences": [
    {
      "sentence_id": "s1",
      "text": "PTEN mutations are common in glioblastoma.",
      "start": 0,
      "end": 42
    }
  ]
}
```

---

## 2. Candidate Entity Proposal

The system should favor **high recall** at this stage.

### Sources

#### a. Biomedical NER / linking tools

Examples:

* BERN2
* SciSpacy
* GNormPlus-style tools
* other biomedical entity recognizers

#### b. Dictionary and ontology matching

Examples:

* HGNC
* NCBI Gene
* Ensembl
* miRBase
* DOID
* MeSH
* UMLS
* RxNorm
* DrugBank
* ChEBI
* ClinVar / dbSNP when relevant

#### c. Regex / pattern extraction

Useful for:

* miRNA mentions
* mutation notations
* HGVS variants
* dosages
* lab values
* cell lines
* biomarker patterns

#### d. Optional LLM span proposer

Used only as a **recall booster**.

The LLM may suggest possible entity spans from a constrained label set, but it must **not** be the sole entity detector.

### Output

Entity candidates from all sources.

Example:

```json
{
  "sentence_id": "s1",
  "entity_candidates": [
    {
      "span_text": "PTEN",
      "start": 0,
      "end": 4,
      "proposed_type": "gene",
      "source": "bern2"
    },
    {
      "span_text": "PTEN",
      "start": 0,
      "end": 4,
      "proposed_type": "gene",
      "source": "dictionary"
    }
  ]
}
```

---

## 3. Candidate Merging

Merge overlapping or duplicate candidates before normalization.

### Rules

* Same span + same type → merge sources.
* Same span + different type → keep all type candidates.
* Overlapping spans → keep both if schema allows; otherwise resolve later.
* Nested spans should follow repository labeling policy.

### Output

A consolidated set of candidates.

Example:

```json
{
  "candidate_id": "c1",
  "span_text": "PTEN",
  "start": 0,
  "end": 4,
  "type_candidates": ["gene"],
  "sources": ["bern2", "dictionary"]
}
```

---

## 4. Ontology Candidate Retrieval

For each merged candidate, retrieve top-k normalized candidates from trusted biomedical resources.

### Goal

Ground all entities to authoritative IDs instead of relying on free-text names.

### Examples

* Genes → HGNC / NCBI Gene / Ensembl
* miRNAs → miRBase
* Diseases → DOID / MeSH / UMLS
* Drugs → RxNorm / DrugBank / ChEBI
* Variants → ClinVar / dbSNP / HGVS-aware mappings

### Important constraint

The LLM must **never invent identifiers**. It may only choose among retrieved candidates or return `unresolved`.

### Output

```json
{
  "candidate_id": "c1",
  "span_text": "PTEN",
  "top_k_ids": [
    {
      "id": "HGNC:9588",
      "name": "PTEN",
      "type": "gene",
      "score": 0.99
    },
    {
      "id": "NCBIGene:5728",
      "name": "PTEN",
      "type": "gene",
      "score": 0.97
    }
  ]
}
```

---

## 5. LLM Entity Adjudication

The LLM is used as a **constrained adjudicator**, not as an unconstrained annotator.

### Input

* sentence or short context
* candidate span
* allowed entity types
* top-k ontology candidates
* explicit `accept`, `reject`, and `unresolved` options

### Tasks

* validate whether the span is a true entity in context
* select the best entity type
* choose the best ontology candidate
* abstain when uncertain

### Prompt design principles

* one candidate at a time
* limited local context only
* fixed label inventory
* strict JSON output
* no free-form reasoning in outputs

### Example output

```json
{
  "decision": "accept",
  "entity_type": "gene",
  "canonical_id": "HGNC:9588",
  "canonical_name": "PTEN",
  "confidence": 0.98
}
```

---

## 6. Entity Validation and Normalization

After LLM adjudication, run deterministic validation.

### Validation checks

* entity type must be in schema
* canonical ID must belong to the correct ontology/type
* span offsets must match the document text
* confidence must be valid numeric output
* malformed records must be rejected or downgraded to unresolved

### Type-specific normalization

* Genes → standardized preferred symbol where applicable
* miRNAs → normalized canonical miRNA naming convention
* Diseases → preferred ontology term
* Drugs → preferred normalized label

### Output

```json
{
  "entity_id": "e1",
  "span_text": "PTEN",
  "start": 0,
  "end": 4,
  "entity_type": "gene",
  "canonical_id": "HGNC:9588",
  "canonical_name": "PTEN",
  "confidence": 0.98,
  "evidence_sources": ["bern2", "dictionary", "llm_entity"]
}
```

---

## 7. Relation Candidate Generation

Generate relation candidates only from validated entities.

### Constraints

* Use only type-compatible pairs.
* Start with sentence-level co-occurrence.
* Optionally extend to nearby-sentence windows later.

### Example pair types

* gene ↔ disease
* miRNA ↔ gene
* drug ↔ disease
* variant ↔ disease
* biomarker ↔ outcome

### Output

```json
[
  {
    "relation_candidate_id": "r1",
    "subject_entity_id": "e1",
    "object_entity_id": "e2",
    "subject_type": "gene",
    "object_type": "disease",
    "sentence_id": "s1"
  }
]
```

---

## 8. LLM Relation Adjudication

The LLM classifies relations from a **fixed allowed label set**.

### Input

* evidence sentence
* subject entity
* object entity
* allowed relation labels
* explicit `no_relation` option

### Rules

* classify one pair at a time
* do not infer beyond the provided context
* output strict JSON only
* default to `no_relation` if the relation is not explicitly supported

### Example output

```json
{
  "relation": "associated_with",
  "confidence": 0.86
}
```

---

## 9. Relation Validation

After relation adjudication, apply deterministic validation.

### Checks

* relation label must be in schema
* subject/object type signature must be valid
* impossible combinations must be rejected
* confidence threshold must be satisfied

### Example

```json
{
  "relation_id": "rel1",
  "subject_entity_id": "e1",
  "object_entity_id": "e2",
  "relation": "associated_with",
  "confidence": 0.86,
  "evidence_sentence": "PTEN mutations are common in glioblastoma.",
  "evidence_sources": ["llm_relation"]
}
```

---

## 10. Confidence Aggregation

Aggregate evidence from all stages into final confidence scores.

### Entity confidence inputs

* proposer agreement
* ontology retrieval score
* dictionary match strength
* LLM confidence
* type consistency

### Relation confidence inputs

* LLM confidence
* type signature validity
* sentence-level locality
* optional trigger lexicon support

### Example entity scoring formula

```text
entity_final_score =
  0.30 * proposer_agreement +
  0.25 * ontology_match_score +
  0.25 * llm_confidence +
  0.20 * type_consistency
```

### Final decision classes

* accepted_high_confidence
* accepted_medium_confidence
* unresolved

Because this pipeline is fully automatic, unresolved outputs may be excluded from final exports.

---

## 11. Final Output Format

The final artifact should be a structured JSON document.

Example:

```json
{
  "document_id": "PMID:12345678",
  "entities": [
    {
      "entity_id": "e1",
      "span_text": "PTEN",
      "start": 0,
      "end": 4,
      "entity_type": "gene",
      "canonical_id": "HGNC:9588",
      "canonical_name": "PTEN",
      "confidence": 0.98,
      "evidence_sources": ["bern2", "dictionary", "llm_entity"]
    },
    {
      "entity_id": "e2",
      "span_text": "glioblastoma",
      "start": 30,
      "end": 42,
      "entity_type": "disease",
      "canonical_id": "DOID:3068",
      "canonical_name": "glioblastoma",
      "confidence": 0.96,
      "evidence_sources": ["bern2", "dictionary", "llm_entity"]
    }
  ],
  "relations": [
    {
      "relation_id": "rel1",
      "subject_entity_id": "e1",
      "object_entity_id": "e2",
      "relation": "associated_with",
      "confidence": 0.86,
      "evidence_sentence": "PTEN mutations are common in glioblastoma.",
      "evidence_sources": ["llm_relation"]
    }
  ]
}
```

---

## Design Principles

* Prefer high recall in candidate generation.
* Prefer high precision in final acceptance.
* Use multiple automatic sources instead of a single annotator.
* Keep the LLM constrained and candidate-based.
* Never allow the LLM to invent ontology IDs.
* Favor abstention over forced decisions.
* Keep all outputs structured and auditable.

---

## Recommended Operating Modes

### High-precision production mode

* strict thresholds
* only strong annotations retained
* unresolved candidates dropped

### Discovery mode

* looser thresholds
* more candidates retained
* useful for exploratory case studies

---

## Future Domain-Specific Case Study

Later, a curated paper collection from one domain can be used for:

* evaluation against gold-standard annotations
* ontology subset restriction
* domain-specific alias expansion
* prompt tuning
* model fine-tuning or distillation

### Suggested strategy

1. Run the general fully automatic pipeline.
2. Compare results to the curated domain corpus.
3. Analyze error buckets and ontology gaps.
4. Build a domain-specialized variant.
5. Fine-tune a smaller model if needed.

---

## Suggested Repository Module Layout

```text
src/
  preprocess.py
  entity_propose.py
  candidate_merge.py
  ontology_retrieve.py
  llm_entity_adjudicate.py
  entity_validate.py
  relation_generate.py
  llm_relation_adjudicate.py
  relation_validate.py
  confidence_score.py
  export_json.py
```

---

## Minimal MVP

The first working version should implement:

1. preprocessing with sentence segmentation and offsets
2. entity proposal from biomedical NER + dictionary matching + regex
3. candidate merging
4. ontology candidate retrieval
5. LLM entity adjudication
6. deterministic entity validation
7. JSON export of normalized entities

After that, extend to relation extraction and confidence scoring.

---

## Summary

This workflow defines a fully automated annotation system for biomedical and clinical literature.

The pipeline combines:

* biomedical tools,
* ontology grounding,
* constrained LLM adjudication,
* deterministic validation,
* and confidence-based filtering.

It is designed to be practical now, extensible later, and suitable for future domain-specific benchmarking and specialization.

## Future work

User-friendly, search by keyword and keyword-type -> return bibliography, return relations of keyword
