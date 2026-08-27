#!/usr/bin/env python3
"""Normalize generated Piper WAV files to openWakeWord's 16 kHz contract."""

import argparse
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly
from tqdm import tqdm


def normalize(path_text: str) -> bool:
    path = Path(path_text)
    sample_rate, audio = wavfile.read(path)
    if sample_rate == 16000:
        return False
    converted = resample_poly(audio.astype(np.float32), 16000, sample_rate)
    converted = np.clip(np.rint(converted), -32768, 32767).astype(np.int16)
    temporary = path.with_suffix(".16khz.tmp.wav")
    wavfile.write(temporary, 16000, converted)
    os.replace(temporary, path)
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    marker = args.root / ".normalized-16khz"
    if marker.exists():
        print("Generated clips are already normalized to 16 kHz.")
        return 0

    clips = [str(path) for path in args.root.glob("*/*.wav")]
    if not clips:
        raise RuntimeError(f"No generated WAV files found below {args.root}")
    workers = max(1, min(8, (os.cpu_count() or 2) // 2))
    changed = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for was_changed in tqdm(
            pool.map(normalize, clips, chunksize=32), total=len(clips), desc="Normalizing 16 kHz"
        ):
            changed += int(was_changed)
    marker.write_text(f"clips={len(clips)} changed={changed}\n", encoding="utf-8")
    print(f"Normalized {changed}/{len(clips)} generated clips to 16 kHz.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

