# JNLPBA analytics

## TRAIN

- Documents: **18546**
- Entity mentions: **51301** across **16664** documents

### Entity counts by type

| type      |   n_mentions |
|:----------|-------------:|
| DNA       |         9533 |
| RNA       |          951 |
| cell_line |         3830 |
| cell_type |         6718 |
| protein   |        30269 |

### Entities per document

|       |       0 |
|:------|--------:|
| count | 16664   |
| mean  |     3.1 |
| min   |     1   |
| 50%   |     3   |
| max   |    23   |

### Span length (chars)

|       |   span_length |
|:------|--------------:|
| count |       51301   |
| mean  |          14.3 |
| min   |           1   |
| 50%   |          11   |
| max   |         125   |

### Normalization: 0 / 51301 (0.0%)

### Top 5 mentions per entity type (case-insensitive)

#### DNA

| text_joined   |   n |
|:--------------|----:|
| ltr           |  88 |
| il-2 promoter |  81 |
| c-fos         |  81 |
| c-jun         |  74 |
| promoter      |  62 |

#### RNA

| text_joined   |   n |
|:--------------|----:|
| mrna          |  78 |
| gr mrna       |  21 |
| c-jun mrna    |  21 |
| mrnas         |  19 |
| il-2 mrna     |  18 |

#### cell_line

| text_joined    |   n |
|:---------------|----:|
| jurkat cells   |  86 |
| jurkat t cells |  81 |
| u937 cells     |  78 |
| hela cells     |  62 |
| cell lines     |  50 |

#### cell_type

| text_joined   |   n |
|:--------------|----:|
| t cells       | 545 |
| monocytes     | 277 |
| b cells       | 177 |
| lymphocytes   | 151 |
| t lymphocytes | 146 |

#### protein

| text_joined           |   n |
|:----------------------|----:|
| nf-kappa b            | 862 |
| nf-kappab             | 540 |
| il-2                  | 534 |
| transcription factors | 343 |
| ap-1                  | 317 |

## VALIDATION

- Documents: **3856**
- Entity mentions: **8662** across **3202** documents

### Entity counts by type

| type      |   n_mentions |
|:----------|-------------:|
| DNA       |         1056 |
| RNA       |          118 |
| cell_line |          500 |
| cell_type |         1921 |
| protein   |         5067 |

### Entities per document

|       |      0 |
|:------|-------:|
| count | 3202   |
| mean  |    2.7 |
| min   |    1   |
| 50%   |    2   |
| max   |   15   |

### Span length (chars)

|       |   span_length |
|:------|--------------:|
| count |        8662   |
| mean  |          15.2 |
| min   |           1   |
| 50%   |          12   |
| max   |          94   |

### Normalization: 0 / 8662 (0.0%)

### Top 5 mentions per entity type (case-insensitive)

#### DNA

| text_joined   |   n |
|:--------------|----:|
| il-2 promoter |  28 |
| ap-1 site     |  15 |
| il-2 gene     |  12 |
| gadd45gamma   |  12 |
| ltr           |  11 |

#### RNA

| text_joined    |   n |
|:---------------|----:|
| tnf-alpha mrna |   5 |
| cytokine mrna  |   4 |
| mcp-1 mrna     |   4 |
| er mrna        |   3 |
| rxralpha mrna  |   3 |

#### cell_line

| text_joined    |   n |
|:---------------|----:|
| jurkat t cells |  14 |
| hl-60 cells    |  14 |
| jurkat cells   |  10 |
| thp-1 cells    |   6 |
| cell lines     |   6 |

#### cell_type

| text_joined   |   n |
|:--------------|----:|
| t cells       |  95 |
| lymphocytes   |  63 |
| b cells       |  54 |
| monocytes     |  47 |
| t cell        |  30 |

#### protein

| text_joined              |   n |
|:-------------------------|----:|
| nf-kappab                |  92 |
| glucocorticoid receptor  |  71 |
| nf-kappa b               |  70 |
| glucocorticoid receptors |  65 |
| il-2                     |  62 |
