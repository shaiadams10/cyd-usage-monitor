"""Train an ESPHome microWakeWord model from the cached Hey Burden corpus.

Large/generated data stays in WSL's ext4 cache. Only the final TFLite model and
ESPHome manifest are copied into the ignored local artifacts directory.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess

from mmap_ninja.ragged import RaggedMmap
import yaml

from microwakeword.audio.augmentation import Augmentation
from microwakeword.audio.clips import Clips
from microwakeword.audio.spectrograms import SpectrogramGeneration


def generate_mmap(
    destination: Path,
    clips: Clips,
    split: str,
    augmenter: Augmentation | None,
    *,
    slide_frames: int | None = None,
    split_duration: float | None = None,
) -> None:
    if destination.exists():
        print(f"Reusing {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    generator = SpectrogramGeneration(
        clips=clips,
        augmenter=augmenter,
        slide_frames=slide_frames,
        split_spectrogram_duration_s=split_duration,
        step_ms=10,
    ).spectrogram_generator(split=split, repeat=1)
    RaggedMmap.from_generator(
        out_dir=str(destination),
        sample_generator=generator,
        batch_size=100,
        verbose=True,
    )


def generate_features(cache: Path) -> Path:
    corpus = cache / "work" / "hey_burden"
    background = cache / "data" / "background_clips"
    output = cache / "micro-wake-word" / "features-v1"

    for required in (corpus / "positive_train", corpus / "negative_train", background):
        if not required.is_dir():
            raise FileNotFoundError(f"Required cached corpus is missing: {required}")

    positives = Clips(
        str(corpus / "positive_train"), "*.wav", random_split_seed=1337, split_count=0.10
    )
    hard_negatives = Clips(
        str(corpus / "negative_train"), "*.wav", random_split_seed=7331, split_count=0.10
    )
    ambient = Clips(str(background), "*.wav", random_split_seed=2026, split_count=0.25)

    augmenter = Augmentation(
        augmentation_duration_s=3.2,
        augmentation_probabilities={
            "SevenBandParametricEQ": 0.15,
            "TanhDistortion": 0.05,
            "PitchShift": 0.10,
            "BandStopFilter": 0.05,
            "AddColorNoise": 0.15,
            "AddBackgroundNoise": 0.75,
            "Gain": 1.0,
            "GainTransition": 0.10,
            "RIR": 0.0,
        },
        background_paths=[str(background)],
        background_min_snr_db=-5,
        background_max_snr_db=15,
        min_gain_db=-30,
        max_gain_db=-1,
        min_jitter_s=0.15,
        max_jitter_s=0.25,
    )

    for split, slides in (("train", 3), ("validation", 2), ("test", 1)):
        directory = {"train": "training", "validation": "validation", "test": "testing"}[split]
        generate_mmap(
            output / "positive" / directory / "wakeword_mmap",
            positives,
            split,
            augmenter,
            slide_frames=slides,
        )
        generate_mmap(
            output / "hard_negative" / directory / "hard_negative_mmap",
            hard_negatives,
            split,
            augmenter,
            slide_frames=1,
        )

    generate_mmap(
        output / "ambient" / "training" / "ambient_mmap",
        ambient,
        "train",
        None,
    )
    generate_mmap(
        output / "ambient" / "validation_ambient" / "ambient_mmap",
        ambient,
        "validation",
        None,
    )
    generate_mmap(
        output / "ambient" / "testing_ambient" / "ambient_mmap",
        ambient,
        "test",
        None,
    )
    return output


def write_training_config(cache: Path, features: Path) -> Path:
    work = cache / "micro-wake-word"
    work.mkdir(parents=True, exist_ok=True)
    config_path = work / "training_parameters.yaml"
    config = {
        "window_step_ms": 10,
        "train_dir": str(work / "trained_models" / "hey_burden"),
        "features": [
            {
                "features_dir": str(features / "positive"),
                "sampling_weight": 3.0,
                "penalty_weight": 1.0,
                "truth": True,
                "truncation_strategy": "truncate_start",
                "type": "mmap",
            },
            {
                "features_dir": str(features / "hard_negative"),
                "sampling_weight": 10.0,
                "penalty_weight": 2.0,
                "truth": False,
                "truncation_strategy": "random",
                "type": "mmap",
            },
            {
                "features_dir": str(features / "ambient"),
                "sampling_weight": 5.0,
                "penalty_weight": 1.0,
                "truth": False,
                "truncation_strategy": "split",
                "type": "mmap",
            },
        ],
        "training_steps": [12_000, 8_000],
        "learning_rates": [0.001, 0.0002],
        "positive_class_weight": [1.0, 1.0],
        "negative_class_weight": [20.0, 30.0],
        "mix_up_augmentation_prob": [0.05, 0.0],
        "freq_mix_augmentation_prob": [0.05, 0.0],
        "time_mask_max_size": [5, 3],
        "time_mask_count": [2, 1],
        "freq_mask_max_size": [5, 3],
        "freq_mask_count": [2, 1],
        "batch_size": 128,
        "eval_step_interval": 500,
        "clip_duration_ms": 1500,
        "target_minimization": 0.10,
        "minimization_metric": "ambient_false_positives_per_hour",
        "maximization_metric": "average_viable_recall",
    }
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return config_path


def train(config: Path, resume: bool) -> None:
    command = [
        "python", "-m", "microwakeword.model_train_eval",
        "--training_config", str(config),
        "--train", "1",
        "--restore_checkpoint", "1" if resume else "0",
        "--test_tf_nonstreaming", "0",
        "--test_tflite_nonstreaming", "0",
        "--test_tflite_nonstreaming_quantized", "0",
        "--test_tflite_streaming", "0",
        "--test_tflite_streaming_quantized", "1",
        "--use_weights", "best_weights",
        "mixednet",
        "--pointwise_filters", "64,64,64,64",
        "--repeat_in_block", "1,1,1,1",
        "--mixconv_kernel_sizes", "[5], [7,11], [9,15], [23]",
        "--residual_connection", "0,0,0,0",
        "--first_conv_filters", "32",
        "--first_conv_kernel_size", "5",
        "--stride", "3",
    ]
    subprocess.run(command, check=True)


def export(cache: Path, artifacts: Path) -> None:
    trained = cache / "micro-wake-word" / "trained_models" / "hey_burden"
    source = trained / "tflite_stream_state_internal_quant" / "stream_state_internal_quant.tflite"
    if not source.is_file():
        raise FileNotFoundError(f"Trained streaming model not found: {source}")
    artifacts.mkdir(parents=True, exist_ok=True)
    model = artifacts / "hey_burden.tflite"
    model.write_bytes(source.read_bytes())
    manifest = {
        "type": "micro",
        "wake_word": "Hey Burden",
        "author": "Local operator",
        "model": "hey_burden.tflite",
        "version": 2,
        "trained_languages": ["en"],
        "micro": {
            # Independent quantized streaming test: 0 false accepts/hour at
            # 0.87 versus 2/hour at 0.86. Start with the conservative cutoff.
            "probability_cutoff": 0.87,
            "sliding_window_size": 5,
            "feature_step_size": 10,
            "tensor_arena_size": 30000,
            "minimum_esphome_version": "2026.7.0",
        },
    }
    (artifacts / "hey_burden.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Exported {model} ({model.stat().st_size} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("features", "train", "export", "all"), default="all")
    parser.add_argument("--cache", type=Path, default=Path.home() / ".cache/hey-burden-training")
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    features = args.cache / "micro-wake-word" / "features-v1"
    if args.stage in ("features", "all"):
        features = generate_features(args.cache)
    config = write_training_config(args.cache, features)
    if args.stage in ("train", "all"):
        train(config, args.resume)
    if args.stage in ("export", "all"):
        export(args.cache, args.artifacts)


if __name__ == "__main__":
    main()
