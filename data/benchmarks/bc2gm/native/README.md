---
annotations_creators:
- expert-generated
language_creators:
- expert-generated
language:
- en
license:
- unknown
multilinguality:
- monolingual
size_categories:
- 10K<n<100K
source_datasets:
- original
task_categories:
- token-classification
task_ids:
- named-entity-recognition
pretty_name: Bc2GmCorpus
dataset_info:
  config_name: bc2gm_corpus
  features:
  - name: id
    dtype: string
  - name: tokens
    sequence: string
  - name: ner_tags
    sequence:
      class_label:
        names:
          '0': O
          '1': B-GENE
          '2': I-GENE
  splits:
  - name: train
    num_bytes: 6095123
    num_examples: 12500
  - name: validation
    num_bytes: 1215919
    num_examples: 2500
  - name: test
    num_bytes: 2454589
    num_examples: 5000
  download_size: 2154630
  dataset_size: 9765631
configs:
- config_name: bc2gm_corpus
  data_files:
  - split: train
    path: bc2gm_corpus/train-*
  - split: validation
    path: bc2gm_corpus/validation-*
  - split: test
    path: bc2gm_corpus/test-*
  default: true
---

# Dataset Card for bc2gm_corpus

## Table of Contents
- [Dataset Description](#dataset-description)
  - [Dataset Summary](#dataset-summary)
  - [Supported Tasks and Leaderboards](#supported-tasks-and-leaderboards)
  - [Languages](#languages)
- [Dataset Structure](#dataset-structure)
  - [Data Instances](#data-instances)
  - [Data Fields](#data-fields)
  - [Data Splits](#data-splits)
- [Dataset Creation](#dataset-creation)
  - [Curation Rationale](#curation-rationale)
  - [Source Data](#source-data)
  - [Annotations](#annotations)
  - [Personal and Sensitive Information](#personal-and-sensitive-information)
- [Considerations for Using the Data](#considerations-for-using-the-data)
  - [Social Impact of Dataset](#social-impact-of-dataset)
  - [Discussion of Biases](#discussion-of-biases)
  - [Other Known Limitations](#other-known-limitations)
- [Additional Information](#additional-information)
  - [Dataset Curators](#dataset-curators)
  - [Licensing Information](#licensing-information)
  - [Citation Information](#citation-information)
  - [Contributions](#contributions)

## Dataset Description

- **Homepage:** [Github](https://github.com/spyysalo/bc2gm-corpus/)
- **Repository:** [Github](https://github.com/spyysalo/bc2gm-corpus/)
- **Paper:** [NCBI](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2559986/)
- **Leaderboard:**
- **Point of Contact:**

### Dataset Summary

[More Information Needed]

### Supported Tasks and Leaderboards

[More Information Needed]

### Languages

[More Information Needed]

## Dataset Structure

### Data Instances

[More Information Needed]

### Data Fields

- `id`: Sentence identifier.  
- `tokens`: Array of tokens composing a sentence.  
- `ner_tags`: Array of tags, where `0` indicates no disease mentioned, `1` signals the first token of a disease and `2` the subsequent disease tokens.  

### Data Splits

[More Information Needed]

## Dataset Creation

### Curation Rationale

[More Information Needed]

### Source Data

#### Initial Data Collection and Normalization

[More Information Needed]

#### Who are the source language producers?

[More Information Needed]

### Annotations

#### Annotation process

[More Information Needed]

#### Who are the annotators?

[More Information Needed]

### Personal and Sensitive Information

[More Information Needed]

## Considerations for Using the Data

### Social Impact of Dataset

[More Information Needed]

### Discussion of Biases

[More Information Needed]

### Other Known Limitations

[More Information Needed]

## Additional Information

### Dataset Curators

[More Information Needed]

### Licensing Information

[More Information Needed]

### Citation Information

[More Information Needed]

### Contributions

Thanks to [@mahajandiwakar](https://github.com/mahajandiwakar) for adding this dataset.