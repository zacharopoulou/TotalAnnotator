#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

command -v uv >/dev/null 2>&1 || { echo "error: 'uv' is required but not installed." >&2; exit 1; }

echo "==> Provisioning the tools/bent environment (uv sync)"
uv sync --project "$SCRIPT_DIR"

BENT_PY="$SCRIPT_DIR/.venv/bin/python"
BENT_BIN="$SCRIPT_DIR/.venv/bin"
BENT_ROOT="$($BENT_PY -c 'import bent.src.cfg as cfg; print(cfg.root_path)')"
export PATH="$BENT_BIN:$PATH"

missing=()
for cmd in wget git make g++ javac; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    missing+=("$cmd")
  fi
done

if [ "${#missing[@]}" -gt 0 ]; then
  echo "error: BENT needs system tools that are not installed: ${missing[*]}" >&2
  echo "Install them first, for example:" >&2
  echo "  sudo apt-get update && sudo apt-get install -y wget git make g++ default-jdk" >&2
  exit 1
fi

echo "==> Applying BENT 0.0.80 compatibility patches"
"$BENT_PY" - <<'PY_BENT_PATCH'
from pathlib import Path
import bent.src.ner as ner_module

ner_path = Path(ner_module.__file__)
source = ner_path.read_text()
old = '        "cell_line_prob",\n        "variant_prob",\n'
new = '        "cell_line_prob",\n        "cell_type_prob",\n        "variant_prob",\n'
if '"cell_type_prob"' not in source:
    if old not in source:
        raise SystemExit(f"Could not patch BENT ner slots in {ner_path}")
    ner_path.write_text(source.replace(old, new))
PY_BENT_PATCH

echo "==> Installing SciSpaCy model into the BENT venv"
if ! "$BENT_PY" -c 'import en_core_sci_lg' >/dev/null 2>&1; then
  py_minor="$($BENT_PY -c 'import sys; print(sys.version_info.minor)')"
  if [ "$py_minor" -ge 10 ]; then
    model_url="https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.3/en_core_sci_lg-0.5.3.tar.gz"
  else
    model_url="https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.4.0/en_core_sci_lg-0.4.0.tar.gz"
  fi
  uv pip install --python "$BENT_PY" "$model_url"
else
  echo "    en_core_sci_lg already installed, skipping."
fi

echo "==> Building BENT abbreviation detector (AB3P)"
ABBR_DIR="$BENT_ROOT/abbreviation_detector"
if [ ! -x "$ABBR_DIR/Ab3P/identify_abbr" ]; then
  mkdir -p "$ABBR_DIR"
  if [ ! -d "$ABBR_DIR/NCBITextLib/.git" ]; then
    git clone https://github.com/ncbi-nlp/NCBITextLib.git "$ABBR_DIR/NCBITextLib"
  fi
  make -C "$ABBR_DIR/NCBITextLib/lib"

  if [ ! -d "$ABBR_DIR/Ab3P/.git" ]; then
    git clone https://github.com/ncbi-nlp/Ab3P.git "$ABBR_DIR/Ab3P"
  fi
  sed -i "s#\*\* location of NCBITextLib \*\*#../NCBITextLib#" "$ABBR_DIR/Ab3P/Makefile"
  sed -i "s#\*\* location of NCBITextLib \*\*#../../NCBITextLib#" "$ABBR_DIR/Ab3P/lib/Makefile"
  make -C "$ABBR_DIR/Ab3P"
else
  echo "    AB3P already built, skipping."
fi

echo "==> Downloading BENT core data"
if [ ! -d "$BENT_ROOT/data/NILINKER" ] || [ ! -d "$BENT_ROOT/data/overlapping_entities" ]; then
  mkdir -p "$BENT_ROOT/data"
  chmod 755 "$BENT_ROOT/get_data.sh"
  bash "$BENT_ROOT/get_data.sh" "$BENT_ROOT"
else
  echo "    core data already present, skipping."
fi

# BENT base setup installs medic and chebi. Include them here because this script
# replaces the upstream bent_setup shell script to keep Python/pip paths correct.
BENT_KBS="${BENT_KBS:-medic,chebi,ncbi_gene,ncbi_taxon,uberon,cellosaurus,go_bp,go_cc,cell_ontology}"
DOWNLOAD_KBS="$BENT_KBS"
# BENT 0.0.80 documents cell_ontology, but its shell downloader names that
# archive cl. Download cl and then expose it under the documented name.
if [[ ",$DOWNLOAD_KBS," == *,cell_ontology,* ]]; then
  DOWNLOAD_KBS="${DOWNLOAD_KBS/cell_ontology/cl}"
fi
if [ -n "$BENT_KBS" ]; then
  echo "==> Downloading BENT KB dictionaries: $BENT_KBS"
  mkdir -p "$BENT_ROOT/data/kbs/dicts"
  "$BENT_PY" -c "from bent.get_kbs import get_additional_kbs; get_additional_kbs([kb.strip() for kb in '$DOWNLOAD_KBS'.split(',') if kb.strip()])"
  if [ -d "$BENT_ROOT/data/kbs/dicts/cl" ] && [ ! -e "$BENT_ROOT/data/kbs/dicts/cell_ontology" ]; then
    mv "$BENT_ROOT/data/kbs/dicts/cl" "$BENT_ROOT/data/kbs/dicts/cell_ontology"
  fi
  missing_kbs=()
  IFS=, read -ra requested_kbs <<< "$BENT_KBS"
  for kb in "${requested_kbs[@]}"; do
    kb="${kb//[[:space:]]/}"
    if [ -n "$kb" ] && [ ! -d "$BENT_ROOT/data/kbs/dicts/$kb" ]; then
      missing_kbs+=("$kb")
    fi
  done
  if [ "${#missing_kbs[@]}" -gt 0 ]; then
    echo "error: missing BENT KB dictionaries after setup: ${missing_kbs[*]}" >&2
    exit 1
  fi
else
  echo "==> Skipping BENT KB downloads (BENT_KBS is empty)."
fi

echo
echo "Done. Enable BENT in your pipeline TOML with:"
echo "  [annotators]"
echo "  enabled = [\"bent\"]"
echo
echo "  [annotators.bent]"
echo "  mode = \"ner_nel\""
echo "  project = \"tools/bent\""
