#!/usr/bin/env bash

set -euo pipefail

# Pinned for reproducibility; override with AIONER_COMMIT=... if you need a newer one.
AIONER_REPO_URL="${AIONER_REPO_URL:-https://github.com/ncbi/AIONER.git}"
AIONER_COMMIT="${AIONER_COMMIT:-b8fa941dc8f49e1c99756832da0c61e9c58dcef8}"
MODELS_URL="${MODELS_URL:-https://huggingface.co/lingbionlp/AIONER-0415/resolve/main/pretrained_models.zip}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
AIONER_DIR="${AIONER_DIR:-$REPO_ROOT/AIONER}"

for cmd in git curl unzip uv; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "error: '$cmd' is required but not installed." >&2; exit 1; }
done

echo "==> AIONER source -> $AIONER_DIR (pinned $AIONER_COMMIT)"
if [ ! -d "$AIONER_DIR/.git" ]; then
  git clone "$AIONER_REPO_URL" "$AIONER_DIR"
fi
git -C "$AIONER_DIR" fetch --quiet origin
git -C "$AIONER_DIR" checkout --quiet "$AIONER_COMMIT"

echo "==> Pretrained models -> $AIONER_DIR/pretrained_models"
if [ -d "$AIONER_DIR/pretrained_models" ]; then
  echo "    already present, skipping download."
else
  tmp_zip="$(mktemp --suffix=.zip)"
  trap 'rm -f "$tmp_zip"' EXIT
  echo "    downloading (~1.5 GB) from $MODELS_URL"
  curl -fL --progress-bar -o "$tmp_zip" "$MODELS_URL"
  echo "    unzipping into $AIONER_DIR"
  unzip -q "$tmp_zip" -d "$AIONER_DIR"
  rm -f "$tmp_zip"
  trap - EXIT
fi

echo "==> Provisioning the tools/aioner environment (uv sync)"
uv sync --project "$SCRIPT_DIR"

echo
echo "Done. Set in your pipeline TOML:"
echo "  [annotators.aioner]"
echo "  repo  = \"$AIONER_DIR\""
echo "  model = \"$AIONER_DIR/pretrained_models/AIONER/PubmedBERT-CRF-AIONER.h5\""
