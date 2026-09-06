# tmVar3 analytics

## TEST

- Documents: **500**
- Entity mentions: **7837** across **493** documents

### Entity counts by type

| type            |   n_mentions |
|:----------------|-------------:|
| AcidChange      |           93 |
| CellLine        |           47 |
| DNAAllele       |           69 |
| DNAMutation     |          634 |
| Gene            |         4059 |
| OtherMutation   |          258 |
| ProteinAllele   |           67 |
| ProteinMutation |          719 |
| SNP             |          135 |
| Species         |         1756 |

### Entities per document

|       |     0 |
|:------|------:|
| count | 493   |
| mean  |  15.9 |
| min   |   1   |
| 50%   |  15   |
| max   |  62   |

### Span length (chars)

|       |   span_length |
|:------|--------------:|
| count |        7837   |
| mean  |           8.6 |
| min   |           1   |
| 50%   |           6   |
| max   |         110   |

### Normalization: 6034 / 7837 (77.0%)

| db_name   |   n_ids |
|:----------|--------:|
| NCBI Gene |    6023 |
| dbSNP     |    2861 |

### Top 5 mentions per entity type (case-insensitive)

#### AcidChange

| text_joined   |   n |
|:--------------|----:|
| g/c           |   8 |
| g/a           |   7 |
| c/t           |   4 |
| c to t        |   3 |
| ile/val       |   3 |

#### CellLine

| text_joined   |   n |
|:--------------|----:|
| nb-c201       |   6 |
| hek293t       |   3 |
| hek293        |   3 |
| cos-7         |   3 |
| a549          |   3 |

#### DNAAllele

| text_joined   |   n |
|:--------------|----:|
| -1021t        |   5 |
| g118          |   4 |
| -352g         |   3 |
| 111g          |   3 |
| 10034 t       |   2 |

#### DNAMutation

| text_joined   |   n |
|:--------------|----:|
| g-395a        |   8 |
| 677c>t        |   5 |
| 657del5       |   5 |
| a1166c        |   5 |
| 1494del6      |   5 |

#### Gene

| text_joined   |   n |
|:--------------|----:|
| ace           |  83 |
| apoe          |  45 |
| ccr5          |  40 |
| ts            |  26 |
| egfr          |  25 |

#### OtherMutation

| text_joined    |   n |
|:---------------|----:|
| delta32        |  18 |
| delta30        |   7 |
| dd32 deletion  |   6 |
| 13-bp deletion |   6 |
| 57 kb deletion |   5 |

#### ProteinAllele

| text_joined   |   n |
|:--------------|----:|
| 573x          |   5 |
| his113        |   4 |
| p.t11         |   3 |
| v244          |   3 |
| m244          |   3 |

#### ProteinMutation

| text_joined   |   n |
|:--------------|----:|
| r114h         |  13 |
| met326ile     |   8 |
| cys 23 ser    |   8 |
| val175met     |   7 |
| f826y         |   6 |

#### SNP

| text_joined   |   n |
|:--------------|----:|
| rs6232        |   7 |
| rs6235        |   6 |
| rs8099917     |   4 |
| rs4810424     |   4 |
| rs2234671     |   3 |

#### Species

| text_joined   |   n |
|:--------------|----:|
| patients      | 880 |
| patient       | 248 |
| human         | 111 |
| children      |  76 |
| women         |  59 |
