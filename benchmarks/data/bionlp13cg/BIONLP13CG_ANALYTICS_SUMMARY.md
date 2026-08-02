# BioNLP13CG analytics

## TRAIN

- Documents: **300**
- Entity mentions: **11034** across **300** documents

### Entity counts by type

| type                            |   n_mentions |
|:--------------------------------|-------------:|
| Amino_acid                      |           40 |
| Anatomical_system               |           21 |
| Cancer                          |         1245 |
| Cell                            |         1978 |
| Cellular_component              |          294 |
| DNA_domain_or_region            |           61 |
| Developing_anatomical_structure |           13 |
| Gene_or_gene_product            |         4028 |
| Immaterial_anatomical_entity    |           52 |
| Multi-tissue_structure          |          416 |
| Organ                           |          194 |
| Organism                        |          952 |
| Organism_subdivision            |           47 |
| Organism_substance              |          145 |
| Pathological_formation          |           96 |
| Protein_domain_or_region        |           38 |
| Simple_chemical                 |         1097 |
| Tissue                          |          317 |

### Entities per document

|       |     0 |
|:------|------:|
| count | 300   |
| mean  |  36.8 |
| min   |  11   |
| 50%   |  37   |
| max   |  79   |

### Span length (chars)

|       |   span_length |
|:------|--------------:|
| count |       11034   |
| mean  |           9.6 |
| min   |           1   |
| 50%   |           7   |
| max   |          93   |

### Normalization: 0 / 11034 (0.0%)

### Top 5 mentions per entity type (case-insensitive)

#### Amino_acid

| text_joined   |   n |
|:--------------|----:|
| tyrosine      |   8 |
| glutamine     |   5 |
| alanine       |   4 |
| amino acid    |   4 |
| ser88         |   2 |

#### Anatomical_system

| text_joined            |   n |
|:-----------------------|----:|
| central nervous system |   6 |
| cns                    |   4 |
| endocrine              |   3 |
| vasculature            |   2 |
| immune system          |   1 |

#### Cancer

| text_joined    |   n |
|:---------------|----:|
| tumor          | 270 |
| cancer         |  95 |
| tumors         |  85 |
| breast cancer  |  37 |
| gastric cancer |  20 |

#### Cell

| text_joined       |   n |
|:------------------|----:|
| cell              | 232 |
| cells             | 165 |
| cellular          |  53 |
| endothelial cell  |  53 |
| endothelial cells |  51 |

#### Cellular_component

| text_joined          |   n |
|:---------------------|----:|
| dna                  |  64 |
| mitochondrial        |  24 |
| nuclear              |  19 |
| extracellular matrix |  18 |
| mitochondria         |   9 |

#### DNA_domain_or_region

| text_joined                |   n |
|:---------------------------|----:|
| promoter                   |  28 |
| hre                        |   5 |
| epigenetic microsatellite  |   2 |
| epigenetic microsatellites |   2 |
| microsatellites            |   2 |

#### Developing_anatomical_structure

| text_joined    |   n |
|:---------------|----:|
| embryos        |   5 |
| embryonic      |   3 |
| embryo         |   2 |
| fetal          |   1 |
| sns precursors |   1 |

#### Gene_or_gene_product

| text_joined                        |   n |
|:-----------------------------------|----:|
| vegf                               | 201 |
| p53                                |  94 |
| vascular endothelial growth factor |  53 |
| pten                               |  43 |
| akt                                |  41 |

#### Immaterial_anatomical_entity

| text_joined     |   n |
|:----------------|----:|
| intracellular   |  15 |
| intraperitoneal |   6 |
| extracellular   |   5 |
| intravenous     |   3 |
| lumen           |   3 |

#### Multi-tissue_structure

| text_joined   |   n |
|:--------------|----:|
| vascular      |  46 |
| lymph node    |  44 |
| blood vessels |  27 |
| vessel        |  15 |
| blood vessel  |  13 |

#### Organ

| text_joined   |   n |
|:--------------|----:|
| skin          |  21 |
| liver         |  17 |
| lung          |  16 |
| heart         |  11 |
| organ         |   7 |

#### Organism

| text_joined   |   n |
|:--------------|----:|
| human         | 232 |
| patients      | 175 |
| mice          |  75 |
| mouse         |  55 |
| rat           |  29 |

#### Organism_subdivision

| text_joined   |   n |
|:--------------|----:|
| oral          |   5 |
| breast        |   4 |
| body          |   4 |
| limb          |   3 |
| betel         |   3 |

#### Organism_substance

| text_joined   |   n |
|:--------------|----:|
| serum         |  39 |
| blood         |  20 |
| cytoplasmic   |  11 |
| plasma        |   9 |
| cytoplasm     |   6 |

#### Pathological_formation

| text_joined   |   n |
|:--------------|----:|
| wound         |  18 |
| ccms          |  12 |
| wounds        |   9 |
| uc            |   6 |
| lesions       |   3 |

#### Protein_domain_or_region

| text_joined   |   n |
|:--------------|----:|
| d5            |   8 |
| tes2          |   4 |
| domain 5      |   2 |
| t251-708      |   2 |
| j domain      |   2 |

#### Simple_chemical

| text_joined   |   n |
|:--------------|----:|
| glucose       |  69 |
| lactate       |  21 |
| doxorubicin   |  21 |
| thalidomide   |  15 |
| ethanol       |  15 |

#### Tissue

| text_joined   |   n |
|:--------------|----:|
| tissue        |  28 |
| tissues       |  18 |
| capillary     |  12 |
| bone          |  12 |
| fat tissue    |   9 |

## VALIDATION

- Documents: **100**
- Entity mentions: **3665** across **100** documents

### Entity counts by type

| type                            |   n_mentions |
|:--------------------------------|-------------:|
| Amino_acid                      |           33 |
| Anatomical_system               |            3 |
| Cancer                          |          434 |
| Cell                            |          546 |
| Cellular_component              |           95 |
| DNA_domain_or_region            |           19 |
| Developing_anatomical_structure |            5 |
| Gene_or_gene_product            |         1360 |
| Immaterial_anatomical_entity    |           19 |
| Multi-tissue_structure          |          138 |
| Organ                           |           71 |
| Organism                        |          306 |
| Organism_subdivision            |           12 |
| Organism_substance              |           36 |
| Pathological_formation          |           44 |
| Protein_domain_or_region        |           12 |
| Simple_chemical                 |          446 |
| Tissue                          |           86 |

### Entities per document

|       |     0 |
|:------|------:|
| count | 100   |
| mean  |  36.6 |
| min   |   9   |
| 50%   |  37.5 |
| max   |  79   |

### Span length (chars)

|       |   span_length |
|:------|--------------:|
| count |        3665   |
| mean  |           9.7 |
| min   |           1   |
| 50%   |           7   |
| max   |          74   |

### Normalization: 0 / 3665 (0.0%)

### Top 5 mentions per entity type (case-insensitive)

#### Amino_acid

| text_joined     |   n |
|:----------------|----:|
| tyrosine        |   8 |
| glutamine       |   8 |
| glutamate       |   3 |
| phosphotyrosine |   2 |
| alanine         |   2 |

#### Anatomical_system

| text_joined    |   n |
|:---------------|----:|
| cardiovascular |   2 |
| vasculature    |   1 |

#### Cancer

| text_joined   |   n |
|:--------------|----:|
| tumor         |  87 |
| tumors        |  37 |
| cancer        |  25 |
| tumour        |  20 |
| breast cancer |  13 |

#### Cell

| text_joined       |   n |
|:------------------|----:|
| cell              |  61 |
| cells             |  59 |
| cellular          |  29 |
| endothelial cells |  14 |
| cancer cells      |  14 |

#### Cellular_component

| text_joined          |   n |
|:---------------------|----:|
| dna                  |  14 |
| membrane             |  12 |
| matrix               |   7 |
| extracellular matrix |   5 |
| cell surface         |   3 |

#### DNA_domain_or_region

| text_joined   |   n |
|:--------------|----:|
| promoter      |   9 |
| mcr           |   2 |
| codon 12      |   1 |
| codon 18      |   1 |
| codon 3       |   1 |

#### Developing_anatomical_structure

| text_joined        |   n |
|:-------------------|----:|
| embryonic          |   4 |
| transgenic embryos |   1 |

#### Gene_or_gene_product

| text_joined                        |   n |
|:-----------------------------------|----:|
| vegf                               |  50 |
| p53                                |  27 |
| vegf-c                             |  24 |
| akt                                |  19 |
| vascular endothelial growth factor |  15 |

#### Immaterial_anatomical_entity

| text_joined   |   n |
|:--------------|----:|
| intracellular |   7 |
| extracellular |   3 |
| juxtafoveal   |   2 |
| marrow cavity |   1 |
| i.v.          |   1 |

#### Multi-tissue_structure

| text_joined     |   n |
|:----------------|----:|
| lymph node      |  14 |
| vascular        |   8 |
| vessel          |   5 |
| vascular bundle |   4 |
| mucosa          |   4 |

#### Organ

| text_joined   |   n |
|:--------------|----:|
| eyes          |   9 |
| brain         |   6 |
| heart         |   5 |
| pulmonary     |   5 |
| lymphatic     |   5 |

#### Organism

| text_joined   |   n |
|:--------------|----:|
| patients      |  61 |
| human         |  60 |
| mice          |  24 |
| mouse         |  12 |
| sv40          |  11 |

#### Organism_subdivision

| text_joined      |   n |
|:-----------------|----:|
| hindlimb         |   4 |
| limb             |   2 |
| gastrointestinal |   1 |
| vegetables       |   1 |
| body             |   1 |

#### Organism_substance

| text_joined   |   n |
|:--------------|----:|
| gse           |  11 |
| serum         |   7 |
| blood         |   5 |
| cytoplasmic   |   3 |
| cytoplasm     |   2 |

#### Pathological_formation

| text_joined                         |   n |
|:------------------------------------|----:|
| ped                                 |   6 |
| wound                               |   6 |
| lesion                              |   5 |
| lesions                             |   3 |
| prostatic intraepithelial neoplasia |   2 |

#### Protein_domain_or_region

| text_joined           |   n |
|:----------------------|----:|
| plasminogen kringle 1 |   2 |
| y951                  |   1 |
| y996                  |   1 |
| y1059                 |   1 |
| y1175                 |   1 |

#### Simple_chemical

| text_joined   |   n |
|:--------------|----:|
| glucose       |  29 |
| verteporfin   |  14 |
| magnolol      |  10 |
| l-name        |  10 |
| dats          |  10 |

#### Tissue

| text_joined   |   n |
|:--------------|----:|
| tissues       |   5 |
| tube          |   5 |
| microvascular |   5 |
| capillary     |   5 |
| macular       |   4 |

## TEST

- Documents: **200**
- Entity mentions: **6955** across **200** documents

### Entity counts by type

| type                            |   n_mentions |
|:--------------------------------|-------------:|
| Amino_acid                      |           62 |
| Anatomical_system               |           17 |
| Cancer                          |          925 |
| Cell                            |         1054 |
| Cellular_component              |          180 |
| Developing_anatomical_structure |           17 |
| Gene_or_gene_product            |         2520 |
| Immaterial_anatomical_entity    |           31 |
| Multi-tissue_structure          |          303 |
| Organ                           |          156 |
| Organism                        |          543 |
| Organism_subdivision            |           39 |
| Organism_substance              |          102 |
| Pathological_formation          |           89 |
| Simple_chemical                 |          727 |
| Tissue                          |          190 |

### Entities per document

|       |     0 |
|:------|------:|
| count | 200   |
| mean  |  34.8 |
| min   |   6   |
| 50%   |  34   |
| max   |  68   |

### Span length (chars)

|       |   span_length |
|:------|--------------:|
| count |        6955   |
| mean  |           9.6 |
| min   |           1   |
| 50%   |           7   |
| max   |         117   |

### Normalization: 0 / 6955 (0.0%)

### Top 5 mentions per entity type (case-insensitive)

#### Amino_acid

| text_joined   |   n |
|:--------------|----:|
| tyrosine      |   9 |
| s727          |   7 |
| y705f         |   7 |
| val600lys     |   5 |
| y705          |   5 |

#### Anatomical_system

| text_joined      |   n |
|:-----------------|----:|
| vasculature      |   4 |
| immune system    |   3 |
| vascular network |   2 |
| respiratory      |   2 |
| pulmonary system |   1 |

#### Cancer

| text_joined   |   n |
|:--------------|----:|
| tumor         | 164 |
| tumors        |  45 |
| cancer        |  44 |
| tumour        |  36 |
| tumours       |  24 |

#### Cell

| text_joined       |   n |
|:------------------|----:|
| cells             | 109 |
| cell              | 105 |
| endothelial cell  |  39 |
| endothelial cells |  35 |
| cellular          |  35 |

#### Cellular_component

| text_joined          |   n |
|:---------------------|----:|
| dna                  |  36 |
| mitochondrial        |  18 |
| extracellular matrix |  11 |
| nuclear              |  10 |
| chromosomal          |   7 |

#### Developing_anatomical_structure

| text_joined    |   n |
|:---------------|----:|
| fetal          |   4 |
| embryonic      |   3 |
| embryos        |   2 |
| fatal          |   1 |
| mutant embryos |   1 |

#### Gene_or_gene_product

| text_joined   |   n |
|:--------------|----:|
| p53           | 116 |
| vegf          |  67 |
| il-8          |  35 |
| bfgf          |  31 |
| e-cadherin    |  28 |

#### Immaterial_anatomical_entity

| text_joined   |   n |
|:--------------|----:|
| intracellular |   8 |
| extracellular |   3 |
| intercellular |   2 |
| intramuscular |   2 |
| i.v.          |   2 |

#### Multi-tissue_structure

| text_joined   |   n |
|:--------------|----:|
| vascular      |  47 |
| lymph node    |  33 |
| blood vessels |  15 |
| vasculature   |  11 |
| bone marrow   |  10 |

#### Organ

| text_joined   |   n |
|:--------------|----:|
| brain         |  17 |
| lung          |  14 |
| bone          |  12 |
| skin          |   9 |
| pulmonary     |   9 |

#### Organism

| text_joined   |   n |
|:--------------|----:|
| patients      | 113 |
| human         |  93 |
| mice          |  38 |
| mouse         |  21 |
| rat           |  17 |

#### Organism_subdivision

| text_joined   |   n |
|:--------------|----:|
| neck          |   7 |
| breast        |   4 |
| body          |   4 |
| foot          |   3 |
| caruncles     |   3 |

#### Organism_substance

| text_joined   |   n |
|:--------------|----:|
| serum         |  30 |
| blood         |  12 |
| urine         |  11 |
| prp           |   6 |
| plasma        |   5 |

#### Pathological_formation

| text_joined   |   n |
|:--------------|----:|
| wound         |  17 |
| edema         |   8 |
| wounds        |   6 |
| pa            |   3 |
| benign        |   3 |

#### Simple_chemical

| text_joined   |   n |
|:--------------|----:|
| glucose       |  48 |
| heparin       |  20 |
| dmba          |  18 |
| atp           |  18 |
| 3-brpa        |  11 |

#### Tissue

| text_joined   |   n |
|:--------------|----:|
| tissue        |  27 |
| microvessel   |  12 |
| breast tissue |   8 |
| tissues       |   8 |
| microvascular |   5 |
