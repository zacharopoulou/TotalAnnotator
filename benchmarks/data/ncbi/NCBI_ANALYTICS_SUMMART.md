# NCBI Disease analytics

## TRAIN

- Documents: **592**
- Entity mentions: **5134** across **592** documents

### By type

| type             |   n_mentions |
|:-----------------|-------------:|
| CompositeMention |          115 |
| DiseaseClass     |          769 |
| Modifier         |         1288 |
| SpecificDisease  |         2962 |

### Entities per document

|       |     0 |
|:------|------:|
| count | 592   |
| mean  |   8.7 |
| min   |   1   |
| 50%   |   8   |
| max   |  30   |

### Span length (chars)

|       |   span_length |
|:------|--------------:|
| count |        5134   |
| mean  |          15.2 |
| min   |           1   |
| 50%   |          14   |
| max   |          80   |

### Normalization: 5134 / 5134 (100.0%)

| db_name   |   n_ids |
|:----------|--------:|
| MESH      |    4867 |
| OMIM      |     391 |

### Top 5 mentions per entity type (case-insensitive)

#### CompositeMention

| text_joined                            |   n |
|:---------------------------------------|----:|
| breast and ovarian cancer              |  15 |
| breast and/or ovarian cancer           |   7 |
| breast or ovarian cancer               |   5 |
| breast and ovarian cancers             |   5 |
| duchenne and becker muscular dystrophy |   4 |

#### DiseaseClass

| text_joined                  |   n |
|:-----------------------------|----:|
| tumors                       |  27 |
| cancer                       |  24 |
| mental retardation           |  21 |
| autosomal recessive disorder |  14 |
| tumours                      |   9 |

#### Modifier

| text_joined   |   n |
|:--------------|----:|
| apc           |  86 |
| dm            |  67 |
| dmd           |  64 |
| vhl           |  39 |
| tumor         |  34 |

#### SpecificDisease

| text_joined        |   n |
|:-------------------|----:|
| g6pd deficiency    |  57 |
| ald                |  56 |
| dm                 |  53 |
| pws                |  53 |
| myotonic dystrophy |  50 |

## VALIDATION

- Documents: **100**
- Entity mentions: **787** across **100** documents

### By type

| type             |   n_mentions |
|:-----------------|-------------:|
| CompositeMention |           35 |
| DiseaseClass     |          126 |
| Modifier         |          214 |
| SpecificDisease  |          412 |

### Entities per document

|       |     0 |
|:------|------:|
| count | 100   |
| mean  |   7.9 |
| min   |   1   |
| 50%   |   7   |
| max   |  25   |

### Span length (chars)

|       |   span_length |
|:------|--------------:|
| count |         787   |
| mean  |          15.7 |
| min   |           2   |
| 50%   |          15   |
| max   |          74   |

### Normalization: 787 / 787 (100.0%)

| db_name   |   n_ids |
|:----------|--------:|
| MESH      |     739 |
| OMIM      |      78 |

### Top 5 mentions per entity type (case-insensitive)

#### CompositeMention

| text_joined                          |   n |
|:-------------------------------------|----:|
| breast and ovarian cancer            |   5 |
| breast and/or ovarian cancer         |   4 |
| breast and ovarian cancers           |   2 |
| classical and duarte galactosemia    |   2 |
| hereditary breast and ovarian cancer |   2 |

#### DiseaseClass

| text_joined    |   n |
|:---------------|----:|
| cancers        |   7 |
| tumours        |   7 |
| tumors         |   6 |
| cancer         |   6 |
| bone dysplasia |   5 |

#### Modifier

| text_joined           |   n |
|:----------------------|----:|
| vhl                   |  17 |
| tumor                 |  15 |
| dm                    |  14 |
| ataxia-telangiectasia |  10 |
| hd                    |  10 |

#### SpecificDisease

| text_joined           |   n |
|:----------------------|----:|
| breast cancer         |  25 |
| ataxia-telangiectasia |  10 |
| hd                    |   9 |
| ovarian cancer        |   8 |
| iddm                  |   7 |

## TEST

- Documents: **100**
- Entity mentions: **960** across **100** documents

### By type

| type             |   n_mentions |
|:-----------------|-------------:|
| CompositeMention |           20 |
| DiseaseClass     |          121 |
| Modifier         |          264 |
| SpecificDisease  |          555 |

### Entities per document

|       |     0 |
|:------|------:|
| count | 100   |
| mean  |   9.6 |
| min   |   2   |
| 50%   |   8   |
| max   |  29   |

### Span length (chars)

|       |   span_length |
|:------|--------------:|
| count |         960   |
| mean  |          14.5 |
| min   |           2   |
| 50%   |          13   |
| max   |          64   |

### Normalization: 960 / 960 (100.0%)

| db_name   |   n_ids |
|:----------|--------:|
| MESH      |     881 |
| OMIM      |      98 |

### Top 5 mentions per entity type (case-insensitive)

#### CompositeMention

| text_joined                                             |   n |
|:--------------------------------------------------------|----:|
| colorectal adenomas and carcinoma                       |   2 |
| breast and/or ovarian cancer                            |   1 |
| hereditary breast and/or ovarian cancer                 |   1 |
| bannayan-zonana (bzs) or ruvalcaba-riley-smith syndrome |   1 |
| spinocerebellar ataxias 1 and 2                         |   1 |

#### DiseaseClass

| text_joined                |   n |
|:---------------------------|----:|
| tumors                     |   9 |
| cancer                     |   6 |
| autosomal dominant disease |   4 |
| adenomas                   |   4 |
| cognitive impairment       |   4 |

#### Modifier

| text_joined           |   n |
|:----------------------|----:|
| apc                   |  21 |
| dm                    |  20 |
| a-t                   |  19 |
| tumor                 |  13 |
| ataxia-telangiectasia |   8 |

#### SpecificDisease

| text_joined        |   n |
|:-------------------|----:|
| dm                 |  16 |
| colorectal cancer  |  11 |
| myotonic dystrophy |   9 |
| fap                |   8 |
| pws                |   8 |
