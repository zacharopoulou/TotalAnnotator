# GNormPlus analytics

## TRAIN

- Documents: **432**
- Entity mentions: **5794** across **418** documents

### Entity counts by type

| type        |   n_mentions |
|:------------|-------------:|
| DomainMotif |          295 |
| FamilyName  |         1275 |
| Gene        |         4224 |

### Entities per document

|       |     0 |
|:------|------:|
| count | 418   |
| mean  |  13.9 |
| min   |   1   |
| 50%   |  12   |
| max   |  56   |

### Span length (chars)

|       |   span_length |
|:------|--------------:|
| count |        5794   |
| mean  |          10.6 |
| min   |           1   |
| 50%   |           6   |
| max   |          81   |

### Normalization: 4234 / 5794 (73.1%)

| db_name   |   n_ids |
|:----------|--------:|
| NCBIGene  |    4358 |

### Top 5 mentions per entity type (case-insensitive)

#### DomainMotif

| text_joined           |   n |
|:----------------------|----:|
| extracellular domain  |   8 |
| catalytic domain      |   7 |
| ecd                   |   7 |
| amino-terminal domain |   6 |
| c-terminal domain     |   5 |

#### FamilyName

| text_joined   |   n |
|:--------------|----:|
| golgi         |  14 |
| tgf-beta      |  13 |
| ap-1          |  12 |
| sox           |  11 |
| tfiid         |   9 |

#### Gene

| text_joined   |   n |
|:--------------|----:|
| slco1b1       |  21 |
| separase      |  19 |
| cd34          |  18 |
| brca1         |  18 |
| nnmt          |  18 |

## TEST

- Documents: **262**
- Entity mentions: **4845** across **261** documents

### Entity counts by type

| type        |   n_mentions |
|:------------|-------------:|
| DomainMotif |          361 |
| FamilyName  |         1252 |
| Gene        |         3232 |

### Entities per document

|       |     0 |
|:------|------:|
| count | 261   |
| mean  |  18.6 |
| min   |   1   |
| 50%   |  17   |
| max   |  57   |

### Span length (chars)

|       |   span_length |
|:------|--------------:|
| count |        4845   |
| mean  |           9.9 |
| min   |           1   |
| 50%   |           6   |
| max   |          82   |

### Normalization: 3223 / 4845 (66.5%)

| db_name   |   n_ids |
|:----------|--------:|
| NCBIGene  |    3298 |

### Top 5 mentions per entity type (case-insensitive)

#### DomainMotif

| text_joined        |   n |
|:-------------------|----:|
| catalytic domain   |   8 |
| cytoplasmic domain |   6 |
| c-terminal domain  |   5 |
| death domain       |   5 |
| catalytic domains  |   4 |

#### FamilyName

| text_joined   |   n |
|:--------------|----:|
| nf-kappab     |  18 |
| golgi         |  16 |
| il-1          |  16 |
| fa            |  12 |
| notch         |  12 |

#### Gene

| text_joined   |   n |
|:--------------|----:|
| p53           |  46 |
| p63           |  37 |
| c1qrp         |  32 |
| bcl-g         |  24 |
| slap-2        |  19 |
