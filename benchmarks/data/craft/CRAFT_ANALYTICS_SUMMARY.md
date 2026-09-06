# CRAFT analytics

## TRAIN

- Documents: **60**
- Entity mentions: **60384** across **60** documents

### Entity counts by type

| type      |   n_mentions |
|:----------|-------------:|
| CHEBI     |         4213 |
| CL        |         3462 |
| GO_BP     |         7625 |
| GO_CC     |         3513 |
| GO_MF     |          325 |
| MONDO     |         1835 |
| MOP       |          221 |
| NCBITaxon |         6683 |
| PR        |        14036 |
| SO        |         7700 |
| UBERON    |        10771 |

### Entities per document

|       |      0 |
|:------|-------:|
| count |   60   |
| mean  | 1006.4 |
| min   |  298   |
| 50%   |  935.5 |
| max   | 1920   |

### Span length (chars)

|       |   span_length |
|:------|--------------:|
| count |         60384 |
| mean  |             8 |
| min   |             1 |
| 50%   |             6 |
| max   |           105 |

### Normalization: 60384 / 60384 (100.0%)

| db_name   |   n_ids |
|:----------|--------:|
| CHEBI     |    4213 |
| CL        |    3462 |
| GO_BP     |    7625 |
| GO_CC     |    3513 |
| GO_MF     |     325 |
| MONDO     |    1835 |
| MOP       |     221 |
| NCBITaxon |    6683 |
| PR        |   14036 |
| SO        |    7700 |
| UBERON    |   10771 |

### Top 5 mentions per entity type (case-insensitive)

#### CHEBI

| text_joined   |   n |
|:--------------|----:|
| cholesterol   | 114 |
| amyloid       | 105 |
| water         | 104 |
| glucose       | 100 |
| dox           |  91 |

#### CL

| text_joined     |   n |
|:----------------|----:|
| es cells        | 293 |
| neurons         | 157 |
| cone            | 131 |
| apoptotic cells | 110 |
| neuronal        | 103 |

#### GO_BP

| text_joined     |    n |
|:----------------|-----:|
| expression      | 1436 |
| olfactory       |  434 |
| expressed       |  407 |
| expressing      |  148 |
| gene expression |  147 |

#### GO_CC

| text_joined   |   n |
|:--------------|----:|
| antibody      | 297 |
| nuclear       | 235 |
| antibodies    | 153 |
| mitochondrial | 133 |
| membrane      | 112 |

#### GO_MF

| text_joined    |   n |
|:---------------|----:|
| hybridization  | 184 |
| hybridized     |  49 |
| annealing      |  18 |
| hybridisation  |  18 |
| hybridizations |  13 |

#### MONDO

| text_joined   |   n |
|:--------------|----:|
| disease       | 161 |
| cf            | 116 |
| bc            |  86 |
| obesity       |  69 |
| msud          |  49 |

#### MOP

| text_joined   |   n |
|:--------------|----:|
| conjugated    |  41 |
| oxidation     |  32 |
| oxidative     |  31 |
| biotinylated  |  11 |
| coupled       |  10 |

#### NCBITaxon

| text_joined   |    n |
|:--------------|-----:|
| mice          | 3053 |
| mouse         | 1089 |
| human         |  465 |
| animals       |  440 |
| animal        |  148 |

#### PR

| text_joined   |   n |
|:--------------|----:|
| pgc-1α        | 405 |
| atrx          | 363 |
| ptdsr         | 310 |
| glur-b        | 306 |
| sam68         | 261 |

#### SO

| text_joined   |    n |
|:--------------|-----:|
| gene          | 1139 |
| genes         |  844 |
| allele        |  368 |
| domain        |  285 |
| genetic       |  267 |

#### UBERON

| text_joined   |   n |
|:--------------|----:|
| embryos       | 706 |
| embryonic     | 368 |
| tissue        | 248 |
| liver         | 225 |
| blood         | 210 |

## VALIDATION

- Documents: **7**
- Entity mentions: **9710** across **7** documents

### Entity counts by type

| type      |   n_mentions |
|:----------|-------------:|
| CHEBI     |          335 |
| CL        |          581 |
| GO_BP     |         1655 |
| GO_CC     |          562 |
| GO_MF     |           50 |
| MONDO     |          232 |
| MOP       |           19 |
| NCBITaxon |          679 |
| PR        |         3002 |
| SO        |         1097 |
| UBERON    |         1498 |

### Entities per document

|       |      0 |
|:------|-------:|
| count |    7   |
| mean  | 1387.1 |
| min   |  642   |
| 50%   | 1391   |
| max   | 2062   |

### Span length (chars)

|       |   span_length |
|:------|--------------:|
| count |        9710   |
| mean  |           7.7 |
| min   |           1   |
| 50%   |           6   |
| max   |          58   |

### Normalization: 9710 / 9710 (100.0%)

| db_name   |   n_ids |
|:----------|--------:|
| CHEBI     |     335 |
| CL        |     581 |
| GO_BP     |    1655 |
| GO_CC     |     562 |
| GO_MF     |      50 |
| MONDO     |     232 |
| MOP       |      19 |
| NCBITaxon |     679 |
| PR        |    3002 |
| SO        |    1097 |
| UBERON    |    1498 |

### Top 5 mentions per entity type (case-insensitive)

#### CHEBI

| text_joined     |   n |
|:----------------|----:|
| dapi            |  27 |
| brdu            |  17 |
| solution        |  15 |
| molecules       |  12 |
| acridine orange |  12 |

#### CL

| text_joined    |   n |
|:---------------|----:|
| spermatocytes  |  80 |
| germ cells     |  31 |
| neurons        |  23 |
| oocytes        |  19 |
| ganglion cells |  19 |

#### GO_BP

| text_joined   |   n |
|:--------------|----:|
| expression    | 178 |
| expressed     |  96 |
| meiotic       |  83 |
| pachytene     |  80 |
| apoptosis     |  50 |

#### GO_CC

| text_joined   |   n |
|:--------------|----:|
| xy body       |  82 |
| antibody      |  51 |
| antibodies    |  49 |
| nuclear       |  41 |
| sex chromatin |  39 |

#### GO_MF

| text_joined    |   n |
|:---------------|----:|
| hybridization  |  29 |
| hybridizations |   5 |
| hybridized     |   5 |
| annealing      |   5 |
| hybridisation  |   2 |

#### MONDO

| text_joined   |   n |
|:--------------|----:|
| disease       |  46 |
| arthritis     |  41 |
| sca15         |  23 |
| ra            |  17 |
| ataxia        |  13 |

#### MOP

| text_joined    |   n |
|:---------------|----:|
| conjugated     |   7 |
| breaks         |   4 |
| reducing       |   2 |
| polymerization |   2 |
| acetylated     |   1 |

#### NCBITaxon

| text_joined   |   n |
|:--------------|----:|
| mice          | 233 |
| mouse         |  86 |
| animals       |  61 |
| mammalian     |  32 |
| mammals       |  29 |

#### PR

| text_joined   |   n |
|:--------------|----:|
| rb            | 259 |
| bmp2          | 251 |
| dmrt7         | 214 |
| bmp4          | 204 |
| pygo2         | 163 |

#### SO

| text_joined   |   n |
|:--------------|----:|
| genes         | 214 |
| gene          | 120 |
| allele        |  69 |
| qtl           |  61 |
| genome        |  38 |

#### UBERON

| text_joined   |   n |
|:--------------|----:|
| retina        | 110 |
| limbs         |  52 |
| testis        |  51 |
| embryos       |  50 |
| kidneys       |  49 |

## TEST

- Documents: **30**
- Entity mentions: **29529** across **30** documents

### Entity counts by type

| type      |   n_mentions |
|:----------|-------------:|
| CHEBI     |         2200 |
| CL        |         1749 |
| GO_BP     |         3681 |
| GO_CC     |         1184 |
| GO_MF     |           94 |
| MONDO     |         1013 |
| MOP       |          101 |
| NCBITaxon |         3101 |
| PR        |         6409 |
| SO        |         3446 |
| UBERON    |         6551 |

### Entities per document

|       |      0 |
|:------|-------:|
| count |   30   |
| mean  |  984.3 |
| min   |  433   |
| 50%   |  974   |
| max   | 1779   |

### Span length (chars)

|       |   span_length |
|:------|--------------:|
| count |       29529   |
| mean  |           7.8 |
| min   |           1   |
| 50%   |           7   |
| max   |          96   |

### Normalization: 29529 / 29529 (100.0%)

| db_name   |   n_ids |
|:----------|--------:|
| CHEBI     |    2200 |
| CL        |    1749 |
| GO_BP     |    3681 |
| GO_CC     |    1184 |
| GO_MF     |      94 |
| MONDO     |    1013 |
| MOP       |     101 |
| NCBITaxon |    3101 |
| PR        |    6409 |
| SO        |    3446 |
| UBERON    |    6551 |

### Top 5 mentions per entity type (case-insensitive)

#### CHEBI

| text_joined   |   n |
|:--------------|----:|
| glucose       | 200 |
| ca2+          | 110 |
| estrogen      |  66 |
| gaba          |  60 |
| doxycycline   |  56 |

#### CL

| text_joined   |   n |
|:--------------|----:|
| neurons       | 140 |
| es cells      |  81 |
| α-cell        |  55 |
| v             |  47 |
| p             |  47 |

#### GO_BP

| text_joined   |   n |
|:--------------|----:|
| expression    | 687 |
| expressed     | 188 |
| expressing    | 136 |
| transfected   |  77 |
| express       |  70 |

#### GO_CC

| text_joined   |   n |
|:--------------|----:|
| antibody      | 139 |
| antibodies    | 101 |
| cilia         |  81 |
| nuclear       |  76 |
| katp channel  |  43 |

#### GO_MF

| text_joined   |   n |
|:--------------|----:|
| hybridization |  43 |
| hybridized    |  19 |
| hybridisation |  17 |
| annealing     |   5 |
| annealed      |   2 |

#### MONDO

| text_joined   |   n |
|:--------------|----:|
| om            |  82 |
| tumor         |  49 |
| disease       |  37 |
| colitis       |  32 |
| cap           |  31 |

#### MOP

| text_joined   |   n |
|:--------------|----:|
| conjugated    |  19 |
| acetylated    |  19 |
| oxidative     |  18 |
| polymerized   |   9 |
| cleaved       |   6 |

#### NCBITaxon

| text_joined   |    n |
|:--------------|-----:|
| mice          | 1530 |
| mouse         |  594 |
| human         |  225 |
| animals       |  126 |
| animal        |   51 |

#### PR

| text_joined   |   n |
|:--------------|----:|
| pten          | 354 |
| ephrin-b1     | 306 |
| sox1          | 298 |
| erk5          | 238 |
| sirt1         | 220 |

#### SO

| text_joined   |   n |
|:--------------|----:|
| gene          | 462 |
| allele        | 216 |
| genes         | 182 |
| exon          | 151 |
| genetic       | 112 |

#### UBERON

| text_joined   |   n |
|:--------------|----:|
| embryos       | 599 |
| brain         | 184 |
| embryo        | 183 |
| embryonic     | 155 |
| tissue        | 112 |
