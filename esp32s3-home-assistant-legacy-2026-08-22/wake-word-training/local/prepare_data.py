#!/usr/bin/env python3
"""Download public training assets and build the Hey Burden training config."""

import argparse
import io
import os
import subprocess
from pathlib import Path

import pyarrow.parquet as parquet
import soundfile
import yaml
from huggingface_hub import hf_hub_download, snapshot_download
from scipy.signal import resample_poly


def decode_audio(blob: bytes) -> tuple[object, int]:
    try:
        audio, sample_rate = soundfile.read(io.BytesIO(blob), dtype="float32", always_2d=True)
        return audio.mean(axis=1), sample_rate
    except Exception:
        decoded = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
             "-f", "wav", "-ac", "1", "-ar", "16000", "pipe:1"],
            input=blob, check=True, capture_output=True,
        ).stdout
        audio, sample_rate = soundfile.read(io.BytesIO(decoded), dtype="float32")
        return audio, sample_rate


def extract_backgrounds(parquet_path: Path, output_dir: Path, limit: int) -> None:
    existing = list(output_dir.glob("*.wav"))
    if len(existing) >= limit:
        print(f"Background clips already ready: {len(existing)}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    parquet_file = parquet.ParquetFile(parquet_path)
    if "audio" not in parquet_file.schema_arrow.names:
        raise RuntimeError(
            f"AudioSet parquet has no audio column: {parquet_file.schema_arrow.names}"
        )

    written = len(existing)
    for batch in parquet_file.iter_batches(batch_size=16, columns=["audio"]):
        for cell in batch.column(0).to_pylist():
            blob = cell.get("bytes") if isinstance(cell, dict) else None
            if not blob:
                continue
            audio, sample_rate = decode_audio(blob)
            if sample_rate != 16000:
                audio = resample_poly(audio, 16000, sample_rate)
            soundfile.write(output_dir / f"audioset_{written:04d}.wav", audio, 16000, subtype="PCM_16")
            written += 1
            if written % 25 == 0:
                print(f"Extracted {written}/{limit} background clips", flush=True)
            if written >= limit:
                return
    raise RuntimeError(f"Only extracted {written} background clips; expected {limit}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--local-dir", type=Path, required=True)
    parser.add_argument("--background-clips", type=int, default=500)
    args = parser.parse_args()

    data_dir = args.cache / "data"
    work_dir = args.cache / "work"
    hf_cache = args.cache / "huggingface"
    data_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    print("Downloading the 2,000-hour general negative-feature set (~17.3 GB)...")
    negatives = Path(hf_hub_download(
        repo_id="davidscripka/openwakeword_features", repo_type="dataset",
        filename="openwakeword_features_ACAV100M_2000_hrs_16bit.npy", cache_dir=hf_cache,
    ))
    print("Downloading false-positive validation features (~185 MB)...")
    validation = Path(hf_hub_download(
        repo_id="davidscripka/openwakeword_features", repo_type="dataset",
        filename="validation_set_features.npy", cache_dir=hf_cache,
    ))
    print("Downloading room impulse responses...")
    rir_snapshot = Path(snapshot_download(
        repo_id="davidscripka/MIT_environmental_impulse_responses", repo_type="dataset",
        allow_patterns=["16khz/*.wav"], cache_dir=hf_cache,
    ))

    print("Downloading one balanced AudioSet shard for augmentation (~700 MB)...")
    audio_parquet = Path(hf_hub_download(
        repo_id="agkphysics/AudioSet", repo_type="dataset",
        filename="data/bal_train/00.parquet", cache_dir=hf_cache,
    ))
    backgrounds = data_dir / "background_clips"
    extract_backgrounds(audio_parquet, backgrounds, args.background_clips)

    config = {
        "model_name": "hey_burden",
        "target_phrase": ["hey burden"],
        "custom_negative_phrases": [
            "heavy burden", "hey birdie", "hey borden", "close the curtain",
            "everything is ready", "turn on lamp one",
        ],
        "n_samples": 20000,
        "n_samples_val": 2000,
        "tts_batch_size": 64,
        "augmentation_batch_size": 16,
        "piper_sample_generator_path": str(args.local_dir / "piper_compat"),
        "output_dir": str(work_dir),
        "rir_paths": [str(rir_snapshot / "16khz")],
        "background_paths": [str(backgrounds)],
        "background_paths_duplication_rate": [1],
        "false_positive_validation_data_path": str(validation),
        "augmentation_rounds": 1,
        "feature_data_files": {"ACAV100M_sample": str(negatives)},
        "batch_n_per_class": {
            "ACAV100M_sample": 1024, "adversarial_negative": 50, "positive": 50,
        },
        "model_type": "dnn",
        "layer_size": 32,
        "steps": 50000,
        "max_negative_weight": 1500,
        "target_false_positives_per_hour": 0.2,
    }
    config_path = args.cache / "hey_burden.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    print(f"Training configuration ready: {config_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
