# Changelog

All notable changes to the ESP32-S3 Home Assistant voice satellite are documented here.

## Unreleased

- Replaced deployment-specific addresses and Home Assistant entity IDs in the
  rollback sources and dashboard with safe placeholders/configurable macros.
  Real operator values remain in ignored local configuration.

### Added

- Added a resumable local WSL2/CUDA training pipeline for the `hey_burden`
  openWakeWord model, including modern RTX-compatible PyTorch, public dataset
  preparation, Piper 3.x compatibility, staged synthetic generation,
  16 kHz normalization, CUDA augmentation/training, bounded streaming
  validation, TFLite conversion, and real-device recording guidance.
- Added `wake-word-training/`, a self-contained operator workspace with the official Home Assistant trainer launcher, a stable “Hey Burden” profile and acceptance phrases, TensorFlow Lite validation, explicit safe installation, live Wyoming model discovery, and Git exclusions for generated training data.

### Changed

- Restored the physical ESP32-S3-WROOM-1 N16R8 build profile (16 MB QIO flash
  and 8 MB Octal OPI PSRAM) and moved the 144 KB Whisper capture buffer
  explicitly into PSRAM. This prevents internal-heap exhaustion that caused
  wake streaming, dashboard connections, and controls to fail intermittently.
- Changed the speaker master volume at boot to 17% and verified that the same
  master gain controls every generated tone, effect, and streamed TTS sample;
  dashboard volume adjustments still apply for the current session.
- Fixed the embedded dashboard returning an empty HTTP 200 response by serving
  a generated gzip asset directly from flash (roughly 31 KB to 7.6 KB).
- Added browser-visible rolling firmware logs, `/api/status`, `/api/logs`, live
  wake/VAD/STT phase and timer telemetry, exact safe USB monitor commands, and a
  voice-pipeline reset that can cancel an in-flight Whisper wait. Live dashboard
  telemetry now uses the existing WebSocket instead of repeated HTTP polling.
- Batched five 16 ms microphone frames into each native 80 ms openWakeWord
  network chunk, bounded payload writes to 512 bytes, and enabled TCP packet
  coalescing, reducing Wyoming header pressure by 5× and preventing `EAGAIN`
  exhaustion while dashboard diagnostics are open.
- Added an ignored local deployment target configuration with a value-free
  tracked example, preserving the operator SSH route without publishing it.
- Added a dedicated streaming Wyoming openWakeWord client on port 10400. It activates automatically when the configured custom model is present and otherwise retains a strict Whisper wake-phrase fallback.
- Replaced the fixed VAD threshold with an adaptive room-noise floor, start/stop hysteresis, impulse rejection, a 250 ms pre-roll, a 0.6 second minimum capture, and a 4.5 second maximum command window.
- Replaced the long wake chime with a roughly 100 ms earcon and delayed microphone arming until the speaker tail has settled.
- Cleared speaker-contaminated pre-roll after wake feedback and prevented manual recording while the speaker is active.
- Moved Home Assistant REST synchronization to a dedicated queue so direct Govee UDP control and audible feedback are not delayed by HTTP.
- Restricted Whisper fallback wake matching to phrase-start, token-bounded “Hey Burden” variants to reduce false activations.
- Added dashboard telemetry for the active wake engine, adaptive VAD threshold, and measured noise floor.

### Operator action

- Train and install `/share/openwakeword/hey_burden.tflite` to enable the fast dedicated wake path. The firmware checks for it automatically every 30 seconds.
