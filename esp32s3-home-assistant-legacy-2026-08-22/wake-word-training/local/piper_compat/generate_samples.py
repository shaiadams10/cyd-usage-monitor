"""Compatibility bridge between openWakeWord and Piper Sample Generator 3.x."""

import os
import sys
from pathlib import Path


def generate_samples(*args, **kwargs):
    """Supply the model argument that openWakeWord's legacy caller omits."""
    model_path = os.environ.get("HEY_BURDEN_PIPER_MODEL")
    if not model_path:
        raise RuntimeError("HEY_BURDEN_PIPER_MODEL is not set")
    source_root = str(Path(model_path).resolve().parents[1])
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    from piper_sample_generator.__main__ import generate_samples as piper_generate_samples

    kwargs.setdefault("model", Path(model_path))
    kwargs.setdefault("max_speakers", 800)
    return piper_generate_samples(*args, **kwargs)
