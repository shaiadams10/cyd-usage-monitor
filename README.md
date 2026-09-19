# ESP32 Projects Workspace & Usage Monitor

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![ESPHome](https://img.shields.io/badge/voice%20firmware-ESPHome-blue.svg)](esp32s3-home-assistant/device.yaml)
[![ESP32-S3](https://img.shields.io/badge/hardware-ESP32--S3-blueviolet.svg)](esp32s3-home-assistant/HARDWARE.md)
[![CYD](https://img.shields.io/badge/hardware-ESP32--2432S028R-red.svg)](cyd-usage-monitor/README.md#hardware)

A unified workspace of independent ESP32 firmware projects, self-hosted voice AI pipelines, and smart home automation tools.

---

## 🧭 Master Quick Links & Web Portals Directory

| Service / Device | URL / Endpoint | Purpose / Function | Documentation |
| :--- | :--- | :--- | :--- |
| **🎙️ ESP32-S3 Voice Satellite** | Device-local web server | On-device wake detection, Home Assistant Assist audio, and focused diagnostics | [`esp32s3-home-assistant`](esp32s3-home-assistant/README.md) |
| **🏠 Home Assistant Dashboard** | Private operator configuration | Master smart home automation interface, device control, and voice pipelines | [`esp32s3-home-assistant/HARDWARE.md`](esp32s3-home-assistant/HARDWARE.md) |
| **🗣️ Wyoming Piper TTS** | Private Wyoming endpoint | Local neural text-to-speech | [`esp32s3-home-assistant/server`](esp32s3-home-assistant/server/README.md) |
| **🎙️ Wyoming Faster Whisper** | Private Wyoming endpoint | Local speech-to-text | [`esp32s3-home-assistant/server`](esp32s3-home-assistant/server/README.md) |
| **📊 CYD Usage Monitor Dashboard** | `http://127.0.0.1:8000` | Self-hosted CLI quota monitor and interactive WebAssembly CYD preview | [`cyd-usage-monitor`](cyd-usage-monitor/README.md) |

---

## 📦 Active Projects in this Repository

### 1. [ESP32-S3 Home Assistant](esp32s3-home-assistant/README.md) — Primary Home Assistant Project
- **Target Hardware:** ESP32-S3-DevKitC-1 (16MB Flash, 8MB PSRAM), INMP441 I2S Microphone, MAX98357A 3.2W I2S Class D DAC, 4Ω 3W Box Speaker, SSD1306 128×64 OLED Display.
- **Key Features:**
  - ESPHome/ESP-IDF clean-room firmware using on-device microWakeWord detection.
  - Standard encrypted Home Assistant Assist audio and intent pipeline.
  - Immediate 17%-volume listening earcon and explicit OLED voice states.
  - Minimal device-local diagnostics dashboard with logs, lifecycle state,
    reset reason, heap, PSRAM, loop-time, Wi-Fi, and safe recovery controls.
  - Pinned Faster Whisper and Piper staging services with no server-side wake
    stream in the production architecture.

### 2. [CYD Usage Monitor](cyd-usage-monitor/README.md)
- **Target Hardware:** ESP32-2432S028R Cheap Yellow Display (2.8" ILI9341 LCD + XPT2046 Touch).
- **Key Features:**
  - Self-hosted dashboard collecting quota snapshots from OpenAI Codex and Google Antigravity CLIs.
  - Interactive browser-based LVGL WebAssembly preview matching the physical screen.
  - Touchscreen and serial navigation shortcuts with optional WhatsApp outage alerts.

### 3. [ESP32-S3 Standalone Voice Assistant ("assistant")](assistant/README.md)
- **Target Hardware:** ESP32-S3-DevKitC-1, INMP441 I2S Microphone, MAX98357A 3.2W I2S Class D DAC, 4Ω 3W Box Speaker *(No OLED — zero bus latency)*.
- **Key Features:**
  - Dedicated STT and light control firmware: triggers on *"Hey Burden lights on"* / *"Hey Burden lights off"*.
  - Direct local Govee UDP unicast (<5ms) & Home Assistant REST synchronization.
  - Complete wiring documentation covering all 7 amplifier pins (`SD_MODE` pull-up to 3.3V, `GAIN` to GND) and 6 microphone pins.
  - Interactive Serial CLI and real-time Web Dashboard with live VU meter.

## 📌 Pin Mapping Matrix & Schematics

Full pin tables, wire colors, visual Mermaid flowcharts, and ASCII circuit diagrams for the primary voice satellite are available in [`esp32s3-home-assistant/HARDWARE.md`](esp32s3-home-assistant/HARDWARE.md).


## Quick start

### Server

Requirements: a private Linux host, Docker Compose, and host-installed Codex
and Antigravity CLIs.

```sh
cd cyd-usage-monitor
cp .env.example .env
# Fill in the private values and host CLI paths in .env.
docker compose up -d --build
```

Use a unique `MONITOR_ADMIN_PASSWORD` of at least 16 characters and a random
`CYD_API_TOKEN` of at least 24 characters. Keep port 8000 on a private network
or place it behind a TLS reverse proxy; HTTP Basic authentication must not be
exposed over plaintext internet traffic. Administrative writes additionally
require the dashboard's custom CSRF header, and temporary CLI sign-in material
is stored in a private one-time inbox and scrubbed after use.

### Firmware

Copy `cyd-usage-monitor/include/secrets.h.example` to the ignored
`cyd-usage-monitor/include/secrets.h`, then configure Wi-Fi, the private
monitor URL, the server's trusted CA certificate, and the same `CYD_API_TOKEN`
used by the server. Plain HTTP is rejected unless the explicit development-only
opt-in is enabled; use HTTPS for real deployments.

```sh
cd cyd-usage-monitor
pio run
pio run --target upload
```

See the [complete setup, security, hardware, and deployment guide](cyd-usage-monitor/README.md).

## Hardware

| Component | Model |
| --- | --- |
| Board | ESP32-2432S028R Cheap Yellow Display |
| Display | 2.8-inch ILI9341, 320×240 |
| Touch | XPT2046 resistive controller |
| Firmware | Arduino framework, LVGL 8, TFT_eSPI |

Detailed pin assignments are documented in the
[project guide](cyd-usage-monitor/README.md#hardware).

## Project layout

```text
cyd-usage-monitor/
├── src/          ESP32 firmware
├── include/      LVGL configuration and safe secrets template
├── server/       dashboard, API, collector, tests, and WASM assets
├── simulator/    shared LVGL WebAssembly simulator source
├── .env.example  value-free server configuration template
└── README.md     complete operator and hardware guide
```

Real `.env` files, firmware secrets, CLI profiles, runtime snapshots, build
output, logs, and private keys are excluded from version control and Docker
build contexts.

## Development

```sh
python -m unittest discover -s cyd-usage-monitor/server
cd cyd-usage-monitor
pio run
docker compose --env-file .env.example config --quiet
```

Dependencies are version-pinned, and the repository CI repeats the parser/API
tests, Compose validation, container build, firmware build, and deterministic
WebAssembly rebuild. See [CONTRIBUTING.md](CONTRIBUTING.md) and
[SECURITY.md](SECURITY.md) before publishing changes.

## License

Released under the widely used [MIT License](LICENSE). Provider names and the
project's unofficial display artwork are addressed separately in
[NOTICE.md](NOTICE.md); the project is independent and is not endorsed by the
named providers.

## Latest CYD release

The public CYD homepage now covers local Codex Desktop account selection on
message submission, Antigravity primary-profile selection, Stream Deck controls,
shared LVGL animations, OpenRouter telemetry, and current LAN deployment/hardware.
See the [CYD operator guide](cyd-usage-monitor/README.md) and
[fresh-computer recovery guide](cyd-usage-monitor/instructions/CHAT_ACCOUNT_SWITCH_SETUP.md).
