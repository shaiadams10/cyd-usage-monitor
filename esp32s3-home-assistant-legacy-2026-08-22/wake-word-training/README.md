# Hey Burden wake-word training workspace

This folder manages the repeatable parts of creating, checking, installing, and
testing the custom `hey_burden` openWakeWord model. The primary workflow now runs
locally in Ubuntu 22.04 under WSL2 with NVIDIA CUDA. Colab remains only an
optional fallback. Large downloads, generated clips, and Python packages stay in
the WSL cache at `~/.cache/hey-burden-training`; only final models are copied to
`artifacts/`.

## How it works

The trainer creates many synthetic examples of “Hey Burden,” mixes them with
background and non-wake audio, converts them to openWakeWord features, and trains
a small classifier. It exports `.tflite` and `.onnx` models. Home Assistant's
openWakeWord app uses the `.tflite` model; the ESP32 continues streaming 16 kHz
microphone frames to the app and receives a Wyoming `detection` event when the
classifier fires. The firmware then plays its short listening earcon and starts
command capture locally.

## Local GPU workflow

Requirements are WSL2, Ubuntu 22.04, Git, ffmpeg, and a recent NVIDIA driver.
Allow roughly 25 GB for dependencies and source datasets plus additional working
space for generated clips and features. The checked-in launcher uses a CUDA 12.8
PyTorch build appropriate for recent RTX GPUs.

1. Build the isolated environment and verify the GPU:

   ```powershell
   .\scripts\setup-local.ps1
   ```

   A successful check ends with `CUDA probe: OK` and identifies the NVIDIA GPU.

2. Run the full resumable pipeline:

   ```powershell
   .\scripts\train-local.ps1 -Stage all
   ```

   Progress is printed in that PowerShell terminal. The stages are `prepare`,
   `generate`, `augment`, `train`, and `convert`; a failed or interrupted run can
   resume at the failed stage. The initial `prepare` stage downloads the general
   2,000-hour openWakeWord negative-feature set (about 17.3 GB), validation data,
   room responses, and one AudioSet background shard. The recipe generates
   20,000 positive and adversarial clips and trains for up to 50,000 steps.
   A guarded local patch streams the large false-positive validation set in
   bounded batches instead of materializing the upstream recipe's tens-of-GiB
   sliding-window array in system memory.

3. Validate the resulting model:

   ```powershell
   .\scripts\validate-model.ps1 -ModelPath .\artifacts\hey_burden.tflite
   ```

4. Expose Home Assistant's `/share/openwakeword` directory through Samba or
   another explicit local mount, then preview and perform the copy:

   ```powershell
   .\scripts\install-model.ps1 -ModelPath .\artifacts\hey_burden.tflite -OpenWakeWordSharePath "X:\openwakeword" -WhatIf
   .\scripts\install-model.ps1 -ModelPath .\artifacts\hey_burden.tflite -OpenWakeWordSharePath "X:\openwakeword"
   ```

5. Restart the openWakeWord app and reload the Wyoming integration. Verify the
   service advertises the model:

   ```powershell
   .\scripts\check-service.ps1 -HostName "<home-assistant-host>"
   ```

   Omit `-HostName` only when `homeassistant.local` resolves on this computer.

The firmware probes port 10400 every 30 seconds and switches from its Whisper
fallback to the dedicated model automatically; no firmware rebuild is required.

## Where your voice recordings fit

The base model should not be trained only from a few recordings of one person.
The synthetic generator supplies thousands of voices, speeds, rooms, and noise
conditions so the wake word remains robust. Your recordings are the deployment
validation set: after the first model exists, record 10–20 natural “Hey Burden”
attempts from the actual ESP32 microphone at the distances and angles you use,
plus ordinary speech and the negative phrases in `training-profile.json`.

Those recordings tell us whether to adjust the Home Assistant openWakeWord
`threshold`/`trigger_level`, add hard-negative phrases, or run another model
iteration. A speaker-specific verifier can be added later, but the stock Home
Assistant openWakeWord app deploys the `.tflite` wake model and does not expose
openWakeWord's optional `.pkl` verifier configuration.

## Optional Colab fallback

`scripts/start-training.ps1` still opens Home Assistant's maintained Colab
trainer. Do not mix that notebook's package installation cells with the local
environment; the local workflow avoids Colab's repeated imported-NumPy restart
cycle.

## Accuracy and speed tuning

Use the positive and negative phrases in `training-profile.json` from several
distances and angles. Record at least 20 wake attempts and 20 ordinary phrases
per test position. Tune only one openWakeWord setting at a time:

- Increase `threshold` or `trigger_level` when ordinary speech causes false wakes.
- Decrease them slightly when clear wake phrases are missed.
- Keep the phrase distinctive and the listening earcon short; wake detection is
  local to openWakeWord, while Whisper is reserved for the command after the wake.
- Test with the real fan/TV/background noise expected in the room. Synthetic
  training is the starting point; room-level acceptance testing decides the final
  operating threshold.

Do not commit generated models, recordings, datasets, local share paths, device
addresses, or credentials. The local artifacts are excluded by `.gitignore`.
