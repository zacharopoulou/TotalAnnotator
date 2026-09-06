# NLM-Gene analytics

## TRAIN

- Documents: **450**
- Entity mentions: **12798** across **450** documents

### Entity counts by type

| type     |   n_mentions |
|:---------|-------------:|
| Domain   |           18 |
| GENERIF  |         3223 |
| Gene     |         7827 |
| Other    |          108 |
| STARGENE |         1622 |

### Entities per document

|       |     0 |
|:------|------:|
| count | 450   |
| mean  |  28.4 |
| min   |   2   |
| 50%   |  27   |
| max   |  76   |

### Span length (chars)

|       |   span_length |
|:------|--------------:|
| count |       12798   |
| mean  |           7.2 |
| min   |           1   |
| 50%   |           5   |
| max   |         102   |

### Normalization: 12682 / 12798 (99.1%)

| db_name   |   n_ids |
|:----------|--------:|
| NCBIGene  |   14686 |

### Top 5 mentions per entity type (case-insensitive)

#### Domain

| text_joined   |   n |
|:--------------|----:|
| tand          |   6 |
| tkd           |   3 |
| mynd          |   2 |
| socs          |   2 |
| ring          |   1 |

#### GENERIF

| text_joined   |   n |
|:--------------|----:|
| il-10         |  32 |
| nrf2          |  32 |
| cox-2         |  31 |
| mre11         |  29 |
| pparα         |  25 |

#### Gene

| text_joined   |   n |
|:--------------|----:|
| akt           | 105 |
| il-6          |  64 |
| erk           |  63 |
| cd4           |  57 |
| pi3k          |  55 |

#### Other

| text_joined   |   n |
|:--------------|----:|
| nsp           |  12 |
| subab         |   6 |
| cck           |   6 |
| il-1beta      |   6 |
| tbeta4        |   6 |

#### STARGENE

| text_joined   |   n |
|:--------------|----:|
| leptin        |  34 |
| akt           |  33 |
| mtor          |  32 |
| pik3ca        |  20 |
| nf-kappab     |  20 |

## TEST

- Documents: **100**
- Entity mentions: **2755** across **100** documents

### Entity counts by type

| type     |   n_mentions |
|:---------|-------------:|
| Domain   |           10 |
| GENERIF  |          664 |
| Gene     |         1735 |
| Other    |           14 |
| STARGENE |          332 |

### Entities per document

|       |     0 |
|:------|------:|
| count | 100   |
| mean  |  27.6 |
| min   |   4   |
| 50%   |  25   |
| max   |  86   |

### Span length (chars)

|       |   span_length |
|:------|--------------:|
| count |        2755   |
| mean  |           7.5 |
| min   |           1   |
| 50%   |           5   |
| max   |          58   |

### Normalization: 2729 / 2755 (99.1%)

| db_name   |   n_ids |
|:----------|--------:|
| NCBIGene  |    3370 |

### Top 5 mentions per entity type (case-insensitive)

#### Domain

| text_joined                          |   n |
|:-------------------------------------|----:|
| cdr3                                 |   4 |
| cdr3α                                |   4 |
| complementarity-determining region 3 |   1 |
| cdr3αβ                               |   1 |

#### GENERIF

| text_joined   |   n |
|:--------------|----:|
| stat1         |  20 |
| mxra5         |  17 |
| igfbp-1       |  17 |
| pnn           |  16 |
| nek2          |  15 |

#### Gene

| text_joined   |   n |
|:--------------|----:|
| il-6          |  29 |
| akt           |  24 |
| cytokines     |  18 |
| cd4           |  15 |
| stat3         |  14 |

#### Other

| text_joined   |   n |
|:--------------|----:|
| ova           |  13 |
| ovalbumin     |   1 |

#### STARGENE

| text_joined   |   n |
|:--------------|----:|
| tgf-β1        |   9 |
| il-17         |   8 |
| cd151         |   8 |
| il-17a        |   8 |
| ing5          |   8 |
