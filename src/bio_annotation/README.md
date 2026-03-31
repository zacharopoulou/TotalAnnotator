# Source Package

This package contains the main implementation of the annotation system.

## Main areas

- `preprocessing/`: document loading, sentence splitting, offsets
- `entity_proposal/`: candidate generation from tools, dictionaries, regex, optional LLM
- `candidate_merging/`: merge overlapping or duplicate candidates
- `ontology/`: alias databases, candidate retrieval, normalization
- `adjudication/`: LLM adjudication for entities and relations
- `validation/`: schema and rule-based validation
- `relations/`: relation pair generation and constraints
- `scoring/`: confidence aggregation
- `pipelines/`: orchestration of end-to-end flows
- `evaluation/`: metrics and case-study evaluation
- `io/`: readers and exporters
