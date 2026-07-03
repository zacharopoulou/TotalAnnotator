from __future__ import annotations

import sys

# build/parse are platform-independent and live in the base module; only the
# subprocess runner differs on Windows (see aioner_windows for why).
from bio_annotation.entity_proposal.aioner_proposer import (
    build_aioner_pubtator_input,
    parse_aioner_response,
)

if sys.platform == "win32":
    from bio_annotation.entity_proposal.aioner_windows import (
        annotate_with_aioner,
        call_aioner,
    )
else:
    from bio_annotation.entity_proposal.aioner_proposer import (
        annotate_with_aioner,
        call_aioner,
    )

__all__ = [
    "annotate_with_aioner",
    "build_aioner_pubtator_input",
    "call_aioner",
    "parse_aioner_response",
]
