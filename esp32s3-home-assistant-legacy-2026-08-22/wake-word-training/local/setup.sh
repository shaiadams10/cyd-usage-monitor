#!/usr/bin/env bash
set -euo pipefail

CACHE_ROOT="${HEY_BURDEN_CACHE:-$HOME/.cache/hey-burden-training}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV="$CACHE_ROOT/venv"
CONVERT_VENV="$CACHE_ROOT/convert-venv"
SOURCE_ROOT="$CACHE_ROOT/src"
OWW_ROOT="$SOURCE_ROOT/openWakeWord"
PIPER_ROOT="$SOURCE_ROOT/piper-sample-generator"
PIPER_MODEL="$PIPER_ROOT/models/en_US-libritts_r-medium.pt"
OWW_COMMIT="368c03716d1e92591906a84949bc477f3a834455"
PIPER_COMMIT="2971426a55072f7d22fec416ca7800df8bd23207"

mkdir -p "$SOURCE_ROOT" "$CACHE_ROOT/data" "$CACHE_ROOT/work"

if [[ ! -x "$VENV/bin/python" ]]; then
  python3 -m venv "$VENV"
fi

"$VENV/bin/python" -m pip install --upgrade pip "setuptools<82" wheel
"$VENV/bin/python" -m pip install \
  torch==2.11.0+cu128 torchaudio==2.11.0+cu128 \
  --index-url https://download.pytorch.org/whl/cu128
"$VENV/bin/python" -m pip install "torchcodec==0.11.1"
"$VENV/bin/python" -m pip install -r "$SCRIPT_DIR/requirements.txt"
"$VENV/bin/python" -m pip install "piper-sample-generator==3.2.0"
"$VENV/bin/python" -m pip uninstall -y onnx2tf tensorflow tf-keras >/dev/null 2>&1 || true

if [[ ! -x "$CONVERT_VENV/bin/python" ]]; then
  python3 -m venv "$CONVERT_VENV"
fi
"$CONVERT_VENV/bin/python" -m pip install --upgrade pip "setuptools<82" wheel
"$CONVERT_VENV/bin/python" -m pip install -r "$SCRIPT_DIR/requirements-convert.txt"

if [[ ! -d "$OWW_ROOT/.git" ]]; then
  git clone https://github.com/dscripka/openWakeWord.git "$OWW_ROOT"
fi
git -C "$OWW_ROOT" fetch --depth 1 origin "$OWW_COMMIT"
git -C "$OWW_ROOT" checkout --detach "$OWW_COMMIT"
"$VENV/bin/python" "$SCRIPT_DIR/patch_upstream.py" \
  "$OWW_ROOT/openwakeword/train.py"

if [[ ! -d "$PIPER_ROOT/.git" ]]; then
  git clone https://github.com/rhasspy/piper-sample-generator.git "$PIPER_ROOT"
fi
git -C "$PIPER_ROOT" fetch --depth 1 origin "$PIPER_COMMIT"
git -C "$PIPER_ROOT" checkout --detach "$PIPER_COMMIT"

"$VENV/bin/python" -m pip install --no-deps -e "$OWW_ROOT"

mkdir -p "$PIPER_ROOT/models"
if [[ ! -s "$PIPER_MODEL" ]]; then
  curl --fail --location --retry 3 \
    https://github.com/rhasspy/piper-sample-generator/releases/download/v2.0.0/en_US-libritts_r-medium.pt \
    --output "$PIPER_MODEL"
fi

"$VENV/bin/python" - <<PY
import openwakeword
openwakeword.utils.download_models()
PY

"$VENV/bin/python" "$SCRIPT_DIR/check_environment.py"
printf '\nLocal environment is ready at %s\n' "$CACHE_ROOT"
