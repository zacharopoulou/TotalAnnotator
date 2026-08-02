# BioRED analytics

## TRAIN

- Documents: **400**
- Entity mentions: **13351** across **400** documents

### Entity counts by type

| type                       |   n_mentions |
|:---------------------------|-------------:|
| CellLine                   |          103 |
| ChemicalEntity             |         2853 |
| DiseaseOrPhenotypicFeature |         3646 |
| GeneOrGeneProduct          |         4430 |
| OrganismTaxon              |         1429 |
| SequenceVariant            |          890 |

### Entities per document

|       |     0 |
|:------|------:|
| count | 400   |
| mean  |  33.4 |
| min   |   5   |
| 50%   |  32   |
| max   |  83   |

### Span length (chars)

|       |   span_length |
|:------|--------------:|
| count |       13351   |
| mean  |           9.6 |
| min   |           1   |
| 50%   |           7   |
| max   |         110   |

### Normalization: 13351 / 13351 (100.0%)

| db_name     |   n_ids |
|:------------|--------:|
| Cellosaurus |     103 |
| MESH        |    6548 |
| NCBIGene    |    4951 |
| NCBITaxon   |    1430 |
| OMIM        |      12 |
| custom      |     362 |
| dbSNP       |     528 |

### Top 5 mentions per entity type (case-insensitive)

#### CellLine

| text_joined   |   n |
|:--------------|----:|
| mcf7/adrr     |   5 |
| c4-2b         |   5 |
| lbetat2       |   4 |
| mz-cha-1      |   4 |
| hek293        |   4 |

#### ChemicalEntity

| text_joined   |   n |
|:--------------|----:|
| glucose       |  60 |
| cocaine       |  32 |
| methadone     |  27 |
| dex           |  27 |
| doxorubicin   |  23 |

#### DiseaseOrPhenotypicFeature

| text_joined     |   n |
|:----------------|----:|
| tumor           | 102 |
| prostate cancer |  61 |
| cancer          |  57 |
| hypertension    |  47 |
| seizures        |  40 |

#### GeneOrGeneProduct

| text_joined   |   n |
|:--------------|----:|
| akt           |  39 |
| insulin       |  29 |
| mtor          |  26 |
| il-10         |  25 |
| vegf          |  24 |

#### OrganismTaxon

| text_joined   |   n |
|:--------------|----:|
| patients      | 515 |
| mice          | 185 |
| rats          | 164 |
| human         | 124 |
| patient       | 124 |

#### SequenceVariant

| text_joined   |   n |
|:--------------|----:|
| c1007g        |   9 |
| g-395a        |   8 |
| met326ile     |   8 |
| cys 23 ser    |   8 |
| val175met     |   7 |

## VALIDATION

- Documents: **100**
- Entity mentions: **3533** across **100** documents

### Entity counts by type

| type                       |   n_mentions |
|:---------------------------|-------------:|
| CellLine                   |           22 |
| ChemicalEntity             |          822 |
| DiseaseOrPhenotypicFeature |          982 |
| GeneOrGeneProduct          |         1087 |
| OrganismTaxon              |          370 |
| SequenceVariant            |          250 |

### Entities per document

|       |     0 |
|:------|------:|
| count | 100   |
| mean  |  35.3 |
| min   |   5   |
| 50%   |  35.5 |
| max   |  70   |

### Span length (chars)

|       |   span_length |
|:------|--------------:|
| count |        3533   |
| mean  |           9.9 |
| min   |           1   |
| 50%   |           8   |
| max   |          79   |

### Normalization: 3533 / 3533 (100.0%)

| db_name     |   n_ids |
|:------------|--------:|
| Cellosaurus |      22 |
| MESH        |    1816 |
| NCBIGene    |    1183 |
| NCBITaxon   |     370 |
| OMIM        |       8 |
| custom      |     124 |
| dbSNP       |     126 |

### Top 5 mentions per entity type (case-insensitive)

#### CellLine

| text_joined   |   n |
|:--------------|----:|
| t98g          |   5 |
| u87mg         |   3 |
| hct-116       |   2 |
| sw480         |   2 |
| llc-pk1       |   2 |

#### ChemicalEntity

| text_joined   |   n |
|:--------------|----:|
| 5-fu          |  24 |
| caffeine      |  17 |
| iron          |  14 |
| olanzapine    |  14 |
| quetiapine    |  14 |

#### DiseaseOrPhenotypicFeature

| text_joined   |   n |
|:--------------|----:|
| hypoxia       |  21 |
| inflammatory  |  18 |
| hypertension  |  17 |
| tumor         |  16 |
| pd            |  12 |

#### GeneOrGeneProduct

| text_joined   |   n |
|:--------------|----:|
| egfr          |  22 |
| psoriasin     |  18 |
| apoe          |  17 |
| foxp3         |  13 |
| ova           |  13 |

#### OrganismTaxon

| text_joined   |   n |
|:--------------|----:|
| patients      | 137 |
| mice          |  58 |
| patient       |  52 |
| rats          |  38 |
| human         |  24 |

#### SequenceVariant

| text_joined   |   n |
|:--------------|----:|
| m404v         |   6 |
| f826y         |   6 |
| dd32 deletion |   6 |
| 657del5       |   5 |
| r140q         |   5 |

## TEST

- Documents: **100**
- Entity mentions: **3535** across **100** documents

### Entity counts by type

| type                       |   n_mentions |
|:---------------------------|-------------:|
| CellLine                   |           50 |
| ChemicalEntity             |          754 |
| DiseaseOrPhenotypicFeature |          917 |
| GeneOrGeneProduct          |         1180 |
| OrganismTaxon              |          393 |
| SequenceVariant            |          241 |

### Entities per document

|       |     0 |
|:------|------:|
| count | 100   |
| mean  |  35.4 |
| min   |   9   |
| 50%   |  31.5 |
| max   |  88   |

### Span length (chars)

|       |   span_length |
|:------|--------------:|
| count |        3535   |
| mean  |           9.5 |
| min   |           2   |
| 50%   |           7   |
| max   |          75   |

### Normalization: 3535 / 3535 (100.0%)

| db_name     |   n_ids |
|:------------|--------:|
| Cellosaurus |      50 |
| MESH        |    1688 |
| NCBIGene    |    1272 |
| NCBITaxon   |     393 |
| custom      |     111 |
| dbSNP       |     130 |

### Top 5 mentions per entity type (case-insensitive)

#### CellLine

| text_joined   |   n |
|:--------------|----:|
| het-1a        |   7 |
| u87           |   7 |
| bep2d         |   6 |
| mcf-7         |   3 |
| a549          |   3 |

#### ChemicalEntity

| text_joined   |   n |
|:--------------|----:|
| alcohol       |  21 |
| lithium       |  17 |
| metoprolol    |  15 |
| flecainide    |  15 |
| vcm           |  12 |

#### DiseaseOrPhenotypicFeature

| text_joined   |   n |
|:--------------|----:|
| tumor         |  18 |
| breast cancer |  17 |
| cancer        |  13 |
| hypotension   |  11 |
| gdm           |  10 |

#### GeneOrGeneProduct

| text_joined   |   n |
|:--------------|----:|
| pik3ca        |  18 |
| ppara         |  18 |
| dach1         |  17 |
| cbr3          |  15 |
| igf-1         |  15 |

#### OrganismTaxon

| text_joined   |   n |
|:--------------|----:|
| patients      | 163 |
| patient       |  39 |
| mice          |  37 |
| rats          |  37 |
| human         |  35 |

#### SequenceVariant

| text_joined   |   n |
|:--------------|----:|
| rs7356506     |   6 |
| v244m         |   5 |
| n372h         |   5 |
| 6bins         |   5 |
| g118          |   4 |
