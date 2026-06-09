# BC5CDR analytics

## TRAIN

- Documents: **500**
- Entity mentions: **9570** across **500** documents
- Relations: **15072**

### Entity counts by type

| type     |   n_mentions |
|:---------|-------------:|
| Chemical |         5207 |
| Disease  |         4363 |

### Entities per document

|       |     0 |
|:------|------:|
| count | 500   |
| mean  |  19.1 |
| min   |   4   |
| 50%   |  18   |
| max   |  60   |

### Span length (chars)

|       |   span_length |
|:------|--------------:|
| count |        9570   |
| mean  |          11.9 |
| min   |           1   |
| 50%   |          10   |
| max   |         105   |

### Normalization: 9494 / 9570 (99.2%)

| db_name   |   n_ids |
|:----------|--------:|
| MESH      |    9599 |

### Top 5 mentions per entity type (case-insensitive)

#### Chemical

| text_joined   |   n |
|:--------------|----:|
| cocaine       | 108 |
| dopamine      |  63 |
| nicotine      |  58 |
| morphine      |  53 |
| lithium       |  49 |

#### Disease

| text_joined   |   n |
|:--------------|----:|
| pain          |  88 |
| toxicity      |  78 |
| proteinuria   |  66 |
| hypotension   |  61 |
| seizures      |  61 |

### Relations (CID = Chemical-Induced-Disease)

| type   |   n_relations |
|:-------|--------------:|
| CID    |         15072 |

#### Relations per document

|       |     0 |
|:------|------:|
| count | 500   |
| mean  |  30.1 |
| min   |   1   |
| 50%   |  20   |
| max   | 288   |

#### Top 10 chemical to disease pairs (case-insensitive)

| pair                                         |   n |
|:---------------------------------------------|----:|
| sirolimus -> proteinuria                     | 296 |
| warfarin -> artery calcification             | 224 |
| tam -> hemolysis                             | 180 |
| cocaine -> seizures                          | 160 |
| srl -> proteinuria                           | 134 |
| ticlopidine -> cholestatic hepatitis         | 120 |
| capsaicin -> pain                            |  74 |
| heparin -> pain                              |  72 |
| heparin -> bruising                          |  72 |
| oral contraceptives -> myocardial infarction |  70 |

## VALIDATION

- Documents: **500**
- Entity mentions: **9773** across **500** documents
- Relations: **16491**

### Entity counts by type

| type     |   n_mentions |
|:---------|-------------:|
| Chemical |         5352 |
| Disease  |         4421 |

### Entities per document

|       |     0 |
|:------|------:|
| count | 500   |
| mean  |  19.5 |
| min   |   3   |
| 50%   |  18   |
| max   |  59   |

### Span length (chars)

|       |   span_length |
|:------|--------------:|
| count |        9773   |
| mean  |          11.4 |
| min   |           1   |
| 50%   |          10   |
| max   |         105   |

### Normalization: 9713 / 9773 (99.4%)

| db_name   |   n_ids |
|:----------|--------:|
| MESH      |    9817 |

### Top 5 mentions per entity type (case-insensitive)

#### Chemical

| text_joined   |   n |
|:--------------|----:|
| doxorubicin   |  62 |
| morphine      |  60 |
| lithium       |  53 |
| cocaine       |  50 |
| heparin       |  48 |

#### Disease

| text_joined   |   n |
|:--------------|----:|
| seizures      |  81 |
| hypotension   |  66 |
| toxicity      |  63 |
| catalepsy     |  45 |
| pain          |  45 |

### Relations (CID = Chemical-Induced-Disease)

| type   |   n_relations |
|:-------|--------------:|
| CID    |         16491 |

#### Relations per document

|       |   0 |
|:------|----:|
| count | 500 |
| mean  |  33 |
| min   |   1 |
| 50%   |  22 |
| max   | 266 |

#### Top 10 chemical to disease pairs (case-insensitive)

| pair                                  |   n |
|:--------------------------------------|----:|
| heparin -> thrombocytopenia           | 161 |
| verapamil -> af                       | 130 |
| morphine -> catalepsy                 |  96 |
| morphine -> sphincter of oddi spasm   |  96 |
| fluconazole -> tdp                    |  90 |
| enalapril -> decreased renal function |  88 |
| levodopa -> dyskinesias               |  85 |
| ntg -> hypotension                    |  84 |
| propofol -> pain                      |  81 |
| levodopa -> lid                       |  80 |

## TEST

- Documents: **500**
- Entity mentions: **9928** across **500** documents
- Relations: **16250**

### Entity counts by type

| type     |   n_mentions |
|:---------|-------------:|
| Chemical |         5394 |
| Disease  |         4534 |

### Entities per document

|       |     0 |
|:------|------:|
| count | 500   |
| mean  |  19.9 |
| min   |   3   |
| 50%   |  18   |
| max   |  69   |

### Span length (chars)

|       |   span_length |
|:------|--------------:|
| count |        9928   |
| mean  |          11.2 |
| min   |           1   |
| 50%   |          10   |
| max   |         120   |

### Normalization: 9837 / 9928 (99.1%)

| db_name   |   n_ids |
|:----------|--------:|
| MESH      |    9919 |

### Top 5 mentions per entity type (case-insensitive)

#### Chemical

| text_joined   |   n |
|:--------------|----:|
| cocaine       |  98 |
| doxorubicin   |  67 |
| pilocarpine   |  64 |
| propranolol   |  55 |
| levodopa      |  53 |

#### Disease

| text_joined    |   n |
|:---------------|----:|
| seizures       | 104 |
| hypertension   |  63 |
| hypotension    |  60 |
| toxicity       |  59 |
| cardiotoxicity |  57 |

### Relations (CID = Chemical-Induced-Disease)

| type   |   n_relations |
|:-------|--------------:|
| CID    |         16250 |

#### Relations per document

|       |     0 |
|:------|------:|
| count | 500   |
| mean  |  32.5 |
| min   |   1   |
| 50%   |  19.5 |
| max   | 266   |

#### Top 10 chemical to disease pairs (case-insensitive)

| pair                               |   n |
|:-----------------------------------|----:|
| levodopa -> dyskinesia             | 156 |
| d,l-sotalol -> torsades de pointes | 140 |
| acetaminophen -> alf               | 132 |
| pilocarpine -> seizures            | 129 |
| ocs -> vte                         | 120 |
| haloperidol -> catalepsy           | 117 |
| heparin -> thrombocytopenia        | 115 |
| pilocarpine -> status epilepticus  | 113 |
| flecainide -> delirium             | 105 |
| cocaine -> seizures                | 100 |
