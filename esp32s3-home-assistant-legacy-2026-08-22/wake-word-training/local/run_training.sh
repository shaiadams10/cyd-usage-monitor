#!/usr/bin/env bash
set -euo pipefail

CACHE_ROOT="${HEY_BURDEN_CACHE:-$HOME/.cache/hey-burden-training}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV="$CACHE_ROOT/venv"
CONVERT_VENV="$CACHE_ROOT/convert-venv"
OWW_ROOT="$CACHE_ROOT/src/openWakeWord"
PIPER_MODEL="$CACHE_ROOT/src/piper-sample-generator/models/en_US-libritts_r-medium.pt"
CONFIG="$CACHE_ROOT/hey_burden.yaml"
ARTIFACT_DIR="${1:?Pass the WSL path to the artifacts directory}"
STAGE="${2:-all}"

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "Run scripts/setup-local.ps1 first." >&2
  exit 2
fi

mkdir -p "$ARTIFACT_DIR" "$CACHE_ROOT/logs"
export HEY_BURDEN_PIPER_MODEL="$PIPER_MODEL"
export PYTHONUNBUFFERED=1
export PYTHONPATH="$SCRIPT_DIR/runtime_compat${PYTHONPATH:+:$PYTHONPATH}"
# Direct HTTP is more reliable for multi-gigabyte resumable downloads in WSL
# than the optional Xet transfer helper, which can stall while finalizing files.
export HF_HUB_DISABLE_XET=1

if [[ "$STAGE" == "prepare" || "$STAGE" == "all" ]]; then
  "$VENV/bin/python" "$SCRIPT_DIR/prepare_data.py" \
    --cache "$CACHE_ROOT" --local-dir "$SCRIPT_DIR"
fi

if [[ "$STAGE" == "generate" || "$STAGE" == "all" ]]; then
  rm -f -- "$CACHE_ROOT/work/hey_burden/.normalized-16khz"
  "$VENV/bin/python" "$OWW_ROOT/openwakeword/train.py" \
    --training_config "$CONFIG" --generate_clips
fi

if [[ "$STAGE" == "augment" || "$STAGE" == "all" ]]; then
  "$VENV/bin/python" "$SCRIPT_DIR/normalize_clips.py" \
    "$CACHE_ROOT/work/hey_burden"
  "$VENV/bin/python" "$OWW_ROOT/openwakeword/train.py" \
    --training_config "$CONFIG" --augment_clips --overwrite
fi

if [[ "$STAGE" == "train" || "$STAGE" == "all" ]]; then
  "$VENV/bin/python" "$OWW_ROOT/openwakeword/train.py" \
    --training_config "$CONFIG" --train_model
  cp "$CACHE_ROOT/work/hey_burden.onnx" "$ARTIFACT_DIR/hey_burden.onnx"
fi

if [[ "$STAGE" == "convert" || "$STAGE" == "all" ]]; then
  ONNX_MODEL="$CACHE_ROOT/work/hey_burden.onnx"
  CONVERSION_DIR="$CACHE_ROOT/work/tflite_conversion"
  [[ -s "$ONNX_MODEL" ]] || { echo "Missing $ONNX_MODEL; run the train stage first." >&2; exit 2; }
  case "$CONVERSION_DIR" in
    "$CACHE_ROOT"/work/*) rm -rf -- "$CONVERSION_DIR" ;;
    *) echo "Refusing to clear unexpected conversion path: $CONVERSION_DIR" >&2; exit 4 ;;
  esac
  "$CONVERT_VENV/bin/onnx2tf" -i "$ONNX_MODEL" -o "$CONVERSION_DIR" -kat onnx____Flatten_0
  TFLITE_MODEL="$(find "$CONVERSION_DIR" -maxdepth 1 -name '*_float32.tflite' -print -quit)"
  [[ -s "$TFLITE_MODEL" ]] || { echo "onnx2tf did not produce a float32 TFLite model." >&2; exit 3; }
  cp "$TFLITE_MODEL" "$ARTIFACT_DIR/hey_burden.tflite"
  echo "Deployable model: $ARTIFACT_DIR/hey_burden.tflite"
fi

echo "Stage '$STAGE' finished. Generated data remains in $CACHE_ROOT/work."
