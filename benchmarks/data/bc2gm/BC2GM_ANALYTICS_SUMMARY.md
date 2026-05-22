# BC2GM analytics

## TRAIN

- Sentences: **12500**
- Tokens (total): **355405**
- Gene mentions: **15197**

### Tag distribution

|        |   n_tokens |
|:-------|-----------:|
| O      |     318104 |
| B-GENE |      15197 |
| I-GENE |      22104 |

### Gene mentions per sentence

|       |        0 |
|:------|---------:|
| count | 12500    |
| mean  |     1.22 |
| min   |     0    |
| 50%   |     1    |
| max   |    35    |

### Mention length (tokens)

|       |   n_tokens |
|:------|-----------:|
| count |   15197    |
| mean  |       2.45 |
| min   |       1    |
| 50%   |       2    |
| max   |      26    |

### Top 10 mentions (case-insensitive)

| mention     |   n |
|:------------|----:|
| insulin     |  70 |
| ras         |  64 |
| sp1         |  51 |
| p53         |  39 |
| ap - 1      |  38 |
| cat         |  34 |
| nf - kappab |  32 |
| c - fos     |  31 |
| jnk         |  31 |
| mapk        |  28 |

## VALIDATION

- Sentences: **2500**
- Tokens (total): **71042**
- Gene mentions: **3061**

### Tag distribution

|        |   n_tokens |
|:-------|-----------:|
| O      |      63544 |
| B-GENE |       3061 |
| I-GENE |       4437 |

### Gene mentions per sentence

|       |       0 |
|:------|--------:|
| count | 2500    |
| mean  |    1.22 |
| min   |    0    |
| 50%   |    1    |
| max   |   14    |

### Mention length (tokens)

|       |   n_tokens |
|:------|-----------:|
| count |    3061    |
| mean  |       2.45 |
| min   |       1    |
| 50%   |       2    |
| max   |      21    |

### Top 10 mentions (case-insensitive)

| mention   |   n |
|:----------|----:|
| sp1       |  14 |
| creb      |  12 |
| c - fos   |  10 |
| c - jun   |  10 |
| epo       |   8 |
| insulin   |   8 |
| sh3       |   8 |
| p53       |   8 |
| ras       |   8 |
| stat3     |   8 |

## TEST

- Sentences: **5000**
- Tokens (total): **143465**
- Gene mentions: **6325**

### Tag distribution

|        |   n_tokens |
|:-------|-----------:|
| O      |     128364 |
| B-GENE |       6325 |
| I-GENE |       8776 |

### Gene mentions per sentence

|       |       0 |
|:------|--------:|
| count | 5000    |
| mean  |    1.26 |
| min   |    0    |
| 50%   |    1    |
| max   |   22    |

### Mention length (tokens)

|       |   n_tokens |
|:------|-----------:|
| count |    6325    |
| mean  |       2.39 |
| min   |       1    |
| 50%   |       2    |
| max   |      19    |

### Top 10 mentions (case-insensitive)

| mention   |   n |
|:----------|----:|
| insulin   |  37 |
| ras       |  24 |
| cat       |  21 |
| sp1       |  19 |
| p53       |  17 |
| mapk      |  16 |
| ap - 1    |  15 |
| igg       |  15 |
| c - jun   |  14 |
| raf       |  14 |
