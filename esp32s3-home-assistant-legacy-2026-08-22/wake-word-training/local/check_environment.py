#!/usr/bin/env python3
"""Fail-fast diagnostics for the local Hey Burden training environment."""

import shutil
import sys
from pathlib import Path

import numpy
import torch
import torchaudio


def main() -> int:
    print(f"Python:       {sys.version.split()[0]}")
    print(f"PyTorch:      {torch.__version__}")
    print(f"TorchAudio:   {torchaudio.__version__}")
    print(f"NumPy:        {numpy.__version__}")
    print(f"CUDA runtime: {torch.version.cuda}")
    print(f"CUDA ready:   {torch.cuda.is_available()}")
    print(f"ffmpeg:       {shutil.which('ffmpeg') or 'missing'}")

    if not torch.cuda.is_available():
        print("ERROR: PyTorch cannot see the NVIDIA GPU.", file=sys.stderr)
        return 2

    device = torch.cuda.get_device_properties(0)
    print(f"GPU:          {device.name}")
    print(f"VRAM:         {device.total_memory / (1024 ** 3):.1f} GiB")
    print(f"Capability:   {device.major}.{device.minor}")

    probe = torch.randn((2048, 2048), device="cuda")
    result = probe @ probe
    torch.cuda.synchronize()
    print(f"CUDA probe:   OK ({result.shape[0]}x{result.shape[1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

