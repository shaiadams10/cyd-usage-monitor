# Codebase Map

> Auto-maintained by agents. Run `brain check` to verify freshness.

## File Manifest

| File | Purpose | Last Updated |
|------|---------|--------------|
| `cyd-usage-monitor/scripts/install-antigravity-startup.ps1` | Per-user scheduled watcher startup with battery support, unlimited runtime and restart recovery | 2026-09-06 |
| `cyd-usage-monitor/scripts/test_stream_deck_security.py` | Windows synthetic-token HTTP tests for redirect rejection, endpoint validation and direct helper transport | 2026-09-06 |
| `cyd-usage-monitor/instructions/CHAT_ACCOUNT_SWITCH_SETUP.md` | Desktop recovery, MSIX-safe startup, native-hook investigation and bounded diagnostics | 2026-09-06 |
| `cyd-usage-monitor/scripts/watch-antigravity-messages.py` | Windowless file-event watcher with heartbeat, receiver failure detection and scheduled recovery | 2026-09-06 |
| `cyd-usage-monitor/scripts/install-chat-account-switch.py` | Installs shared-home mappings, trusted hooks, optional native probe and scheduled watcher | 2026-09-06 |
| `cyd-usage-monitor/scripts/test_chat_account_switch.py` | Tests message ordering, bundled-CLI update recovery, bounded private diagnostics, failure phases and LAN requests | 2026-09-09 |
| `cyd-usage-monitor/scripts/chat-account-switch.py` | Desktop selector with safe bundled-CLI rediscovery, bounded metadata history and on-demand process/server diagnostics | 2026-09-09 |
| `esp32s3-home-assistant/audio/speaker_tests.h` | Bounded nonblocking local sound and speech test playback, mono/stereo comparison, and level steps | 2026-09-04 |
| `esp32s3-home-assistant/audio/speaker_samples.h` | Generated synthetic 16 kHz speech samples normalized to -1 dBFS | 2026-09-04 |
| `esp32s3-home-assistant/scripts/build-speaker-samples.ps1` | Generates embedded synthetic speech with Windows System.Speech | 2026-09-04 |
| `docs/map.md` | Codebase file manifest and architecture map | 2026-09-09 |
| `docs/map.local.md` | Ignored operator map including fixed-address deployment recovery, desktop launchers and isolated-release Git divergence | 2026-09-13 |
| `.github/workflows/ci.yml` | Server, Windows helper transport, firmware, real LVGL motion and WASM release checks | 2026-09-06 |
| `.gitignore` | Git ignore patterns for private operator data, generated firmware/caches, and root diagnostic audio captures | 2026-08-27 |
| `AGENTS.md` | AI agent instructions, Brain pre-flight, and optional local-operator-map discovery | 2026-08-22 |
| `CODE_OF_CONDUCT.md` | Documentation | 2026-08-09 |
| `CONTRIBUTING.md` | Documentation | 2026-08-09 |
| `cyd-usage-monitor/.dockerignore` | Project file | 2026-08-09 |
| `cyd-usage-monitor/.env` | Environment variables (local) | 2026-08-09 |
| `cyd-usage-monitor/.env.example` | Value-free server, private-LAN listener, dashboard Tunnel, WAHA, TLS SMTP fallback, timezone propagation, and consecutive-failure alert configuration template | 2026-09-05 |
| `cyd-usage-monitor/.gitignore` | Excludes credentials, runtime data, local message-hook mappings and backups | 2026-09-06 |
| `cyd-usage-monitor/AGENTS.md` | Security, shared runtime, Windows MSIX-safe installation and deployment contract | 2026-09-06 |
| `cyd-usage-monitor/CHANGELOG.md` | Change history including shared-home startup and Codex bundled-CLI update recovery | 2026-09-09 |
| `cyd-usage-monitor/data/factory_backup.bin` | Full 4MB binary flash backup of the factory vendor firmware and LVGL widget demo | 2026-08-26 |
| `cyd-usage-monitor/diagram.json` | Wokwi visual layout and pin connection diagram for ESP32-2432S028R | 2026-08-09 |
| `cyd-usage-monitor/docker-compose.yml` | Hardened app/collector/Tunnel orchestration with container TZ, private device binding, WAHA, and host-only TLS SMTP fallback configuration | 2026-09-05 |
| `cyd-usage-monitor/Dockerfile` | Python 3.14 server image definition including the protected flashing guide artifact | 2026-08-09 |
| `cyd-usage-monitor/include/lv_conf.h` | Physical LVGL 8.4 Canvas, Arc, Chart, layout, memory, font, and theme configuration | 2026-08-09 |
| `cyd-usage-monitor/include/mascot_img.h` | Project file | 2026-08-09 |
| `cyd-usage-monitor/include/secrets.h` | Project file | 2026-08-09 |
| `cyd-usage-monitor/include/secrets.h.example` | Value-free firmware Wi-Fi, private-LAN endpoint, and Bearer-token template | 2026-08-09 |
| `cyd-usage-monitor/instructions/DEPLOYMENT_RUNBOOK.md` | Public-safe remote deployment, dashboard/host SMTP setup, display-command verification, rollback, and release runbook | 2026-08-26 |
| `cyd-usage-monitor/instructions/FLASHING_GUIDE.md` | Canonical secure E32R40T preparation, conservative CH340C flashing, verification, and recovery guide | 2026-08-26 |
| `cyd-usage-monitor/instructions/TOKEN_GUIDE.md` | Credential boundaries and shared-home private desktop mappings | 2026-09-06 |
| `cyd-usage-monitor/platformio.ini` | Shared physical-CYD/Wokwi firmware target with pinned dependencies, E32R40T ST7796S flags, and conservative CH340C upload speed | 2026-08-26 |
| `cyd-usage-monitor/README.md` | Operator guide including scheduled desktop, bundled-CLI update and switch-history recovery | 2026-09-09 |
| `cyd-usage-monitor/scripts/stream-deck-next-account.ps1` | Secure private-LAN account selection/discovery with diagnostic source attribution | 2026-09-06 |
| `cyd-usage-monitor/scripts/stream-deck-next-account.vbs` | Windowless secure private-LAN selection with diagnostic source attribution | 2026-09-06 |
| `cyd-usage-monitor/server/collector.py` | CLI/OpenRouter collector with local timezone propagation, dual Codex quotas, durable identity, incidents, WAHA retry, and environment/dashboard TLS SMTP fallback | 2026-09-05 |
| `cyd-usage-monitor/server/dashboard.html` | Upright synchronized LVGL preview, physical-orientation indicator, protected display controls, email setup, alert health, and favicon/touch icons | 2026-08-27 |
| `cyd-usage-monitor/server/server.py` | Route-isolated account/display APIs with bounded source-attributed selection history | 2026-09-06 |
| `cyd-usage-monitor/server/static/apple-touch-icon.png` | 180x180 high-DPI iOS/mobile touch icon asset | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-badge-icon-32.png` | 32x32 compact Stream Deck cycle-action badge icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-badge-icon-192.png` | 192x192 Stream Deck cycle-action badge icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-badge-icon-512.png` | 512x512 high-resolution cycle-action badge icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-badge-icon-1024.png` | 1024x1024 master cycle-action badge icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-icon-32.png` | 32x32 compact account-cycle action icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-icon-180.png` | 180x180 account-cycle touch/launcher icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-icon-192.png` | 192x192 account-cycle action icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-icon-512.png` | 512x512 high-resolution account-cycle action icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-icon-1024.png` | 1024x1024 master pixel-art CYD Usage Monitor icon with integrated cycle indicator | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-icon-1024.png` | 1024x1024 master high-resolution CYD Usage Monitor app branding icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-sync-icon-32.png` | 32x32 compact dashboard/device synchronization action icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-sync-icon-180.png` | 180x180 dashboard/device synchronization touch/launcher icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-sync-icon-192.png` | 192x192 dashboard/device synchronization action icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-sync-icon-512.png` | 512x512 high-resolution dashboard/device synchronization action icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-sync-icon-1024.png` | 1024x1024 master dashboard/device synchronization action icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/favicon-16x16.png` | 16x16 crisp raster favicon asset | 2026-08-27 |
| `cyd-usage-monitor/server/static/favicon-32x32.png` | 32x32 standard browser tab raster favicon asset | 2026-08-27 |
| `cyd-usage-monitor/server/static/favicon.ico` | Multi-resolution 16/32/48/64px Windows and browser ICO favicon asset | 2026-08-27 |
| `cyd-usage-monitor/server/static/favicon.svg` | Scalable vector SVG favicon with dark theme, glowing arc meter, and CYD monogram | 2026-08-27 |
| `cyd-usage-monitor/server/static/icon-192.png` | 192x192 PWA web app manifest icon asset | 2026-08-27 |
| `cyd-usage-monitor/server/static/icon-512.png` | 512x512 high-resolution app icon asset | 2026-08-27 |
| `cyd-usage-monitor/server/static/lvgl/cyd_lvgl.js` | Generated loader for animated shared LVGL preview | 2026-09-06 |
| `cyd-usage-monitor/server/static/lvgl/cyd_lvgl.wasm` | Generated animated launcher, ChatGPT, Antigravity and OpenRouter LVGL runtime | 2026-09-06 |
| `cyd-usage-monitor/server/storage.py` | Python module | 2026-08-09 |
| `cyd-usage-monitor/server/test_collector.py` | Isolated collector runtime, credential boundaries, timezone, quota, incident and notification regression tests | 2026-09-06 |
| `cyd-usage-monitor/server/test_server.py` | Security, selection, history privacy/retention and display-command contract tests | 2026-09-06 |
| `cyd-usage-monitor/server/test_storage.py` | Python module | 2026-08-09 |
| `cyd-usage-monitor/server/__init__.py` | Python module | 2026-08-09 |
| `cyd-usage-monitor/simulator/test_motion.c` | Real LVGL/WASM regression checks for animation state, bounds, refreshes, errors and rapid navigation | 2026-09-06 |
| `cyd-usage-monitor/simulator/build-wasm.ps1` | Pinned production WASM build and real LVGL motion tests with failure propagation | 2026-09-05 |
| `cyd-usage-monitor/simulator/lvgl_cyd_sim.c` | WASM launcher, quota and OpenRouter screens with shared motion and pointer navigation | 2026-09-06 |
| `cyd-usage-monitor/simulator/lv_conf.h` | WebAssembly LVGL 8.4 Canvas, Arc, Chart, layout, memory, font, and theme configuration | 2026-08-09 |
| `cyd-usage-monitor/src/ui_motion.h` | Shared LVGL motion with coalesced strip reveals, stable arrival values, quota sweeps, counters and charts | 2026-09-06 |
| `cyd-usage-monitor/src/main.cpp` | Physical CYD with strip transitions, HTTP worker, retry backoff, Wi-Fi/reset/memory/render diagnostics | 2026-09-06 |
| `cyd-usage-monitor/src/mascot_img.h` | Project file | 2026-08-09 |
| `cyd-usage-monitor/wokwi.toml` | Wokwi simulator mapping to the shared LAN-only firmware target | 2026-08-09 |
| `assistant/.gitignore` | Git ignore patterns for assistant build artifacts | 2026-08-17 |
| `assistant/CHANGELOG.md` | Standalone assistant change history, including public-safe configuration cleanup | 2026-08-23 |
| `assistant/diagram.json` | Wokwi visual layout and pin connection diagram for ESP32-S3, MAX98357A, and INMP441 | 2026-08-17 |
| `docs/context.md` | Current project state, recent changes, validation and deployment results | 2026-09-13 |
| `assistant/include/secrets.h` | Project file (private local configuration) | 2026-08-17 |
| `assistant/include/secrets.h.example` | Value-free Wi-Fi, documented network placeholders, and configurable Home Assistant entity template | 2026-08-23 |
| `assistant/inmp441.chip.json` | Wokwi custom chip definition for INMP441 MEMS microphone | 2026-08-17 |
| `assistant/max98357a.chip.json` | Wokwi custom chip definition for MAX98357A I2S DAC amplifier | 2026-08-17 |
| `assistant/platformio.ini` | PlatformIO configuration for standalone ESP32-S3 voice assistant | 2026-08-17 |
| `assistant/README.md` | Complete hardware pin mapping matrix, public-safe configuration boundary, Mermaid flowchart, ASCII schematic, and voice trigger guide | 2026-08-23 |
| `assistant/src/main.cpp` | Dedicated voice assistant firmware with dual I2S, VAD, Whisper STT, and configurable Govee/HA light control | 2026-08-23 |
| `assistant/wokwi.toml` | Wokwi simulator configuration for assistant | 2026-08-17 |
| `esp32s3-home-assistant/.gitignore` | Excludes ESPHome build/tool environments, local secrets, and firmware artifacts | 2026-08-22 |
| `esp32s3-home-assistant/CHANGELOG.md` | Clean-room v2 firmware, full-scale speaker control, exhaustive voice review queue, research retention, direct Assist TTS restoration, dashboard, and physical validation changes | 2026-09-04 |
| `esp32s3-home-assistant/circuit/.gitignore` | Excludes project-local dependencies, caches, checks, and generated circuit exports | 2026-08-24 |
| `esp32s3-home-assistant/circuit/.npmrc` | Configuration pointing @tsci packages to the official TSCircuit registry | 2026-08-24 |
| `esp32s3-home-assistant/circuit/__snapshots__/index.circuit-pcb.snap.svg` | Validated entrypoint PCB visual regression snapshot | 2026-08-24 |
| `esp32s3-home-assistant/circuit/__snapshots__/index.circuit-schematic.snap.svg` | Validated entrypoint schematic visual regression snapshot | 2026-08-24 |
| `esp32s3-home-assistant/circuit/__snapshots__/VoiceSatelliteCarrier.circuit-pcb.snap.svg` | Direct carrier PCB visual regression snapshot | 2026-08-24 |
| `esp32s3-home-assistant/circuit/__snapshots__/VoiceSatelliteCarrier.circuit-schematic.snap.svg` | Direct carrier schematic visual regression snapshot | 2026-08-24 |
| `esp32s3-home-assistant/circuit/package-lock.json` | Exact project-local tscircuit, evaluator, TypeScript, and transitive dependency lock | 2026-08-24 |
| `esp32s3-home-assistant/circuit/package.json` | Exact project-local tscircuit tooling plus validation, preview, and manufacturing export scripts | 2026-08-24 |
| `esp32s3-home-assistant/circuit/tsconfig.json` | TypeScript configuration supporting JSX for TSCircuit components | 2026-08-24 |
| `esp32s3-home-assistant/circuit/tscircuit.config.json` | TSCircuit configuration schema | 2026-08-24 |
| `esp32s3-home-assistant/circuit/README.md` | Audited electrical design, local-only tool workflow, safe power selection, fabrication gate, and enclosure path | 2026-08-24 |
| `esp32s3-home-assistant/circuit/index.circuit.tsx` | Main entrypoint exporting the VoiceSatelliteCarrier board | 2026-08-24 |
| `esp32s3-home-assistant/circuit/VoiceSatelliteCarrier.circuit.tsx` | Validated carrier layout with peripheral-only power selection, schematic sections, radial bulk capacitor, and widened power routing | 2026-08-24 |
| `esp32s3-home-assistant/circuit/components/Esp32S3DevKit.tsx` | Official DevKitC-1 J1/J3 mapping, 22.86 mm row spacing, and 25.4 x 62.74 mm body outline | 2026-08-24 |
| `esp32s3-home-assistant/circuit/components/Inmp441Mic.tsx` | 6-pin socket component for INMP441 I2S MEMS microphone module | 2026-08-24 |
| `esp32s3-home-assistant/circuit/components/Max98357aAmp.tsx` | 7-pin socket for the MAX98357A breakout; speaker output remains on its bridge-tied onboard terminal | 2026-08-24 |
| `esp32s3-home-assistant/circuit/components/Ssd1306Oled.tsx` | 4-pin I2C socket component for SSD1306 OLED display | 2026-08-24 |
| `esp32s3-home-assistant/circuit/components/Ws2812Connector.tsx` | 3-pin connector with 330 ohm protection resistor for WS2812 LED ring | 2026-08-24 |
| `esp32s3-home-assistant/circuit/scripts/export-artifacts.ps1` | Failure-aware local-CLI export of Gerbers/BOM/PnP, KiCad, SVG, and GLB artifacts | 2026-08-24 |
| `esp32s3-home-assistant/components/buffered_microphone/__init__.py` | Local external-component package marker for the one-breath command audio bridge | 2026-08-23 |
| `esp32s3-home-assistant/components/buffered_microphone/microphone.py` | ESPHome microphone-platform schema and code generation for the PSRAM pre-roll proxy | 2026-08-23 |
| `esp32s3-home-assistant/components/buffered_microphone/buffered_microphone.h` | Buffered microphone interface, wake marker, and replay diagnostics | 2026-08-23 |
| `esp32s3-home-assistant/components/buffered_microphone/buffered_microphone.cpp` | Continuous physical-mic history and chronological wake-command replay implementation | 2026-08-23 |
| `esp32s3-home-assistant/dashboard-bundle.js` | Generated offline ESPHome v3 bundle containing the responsive 0–100% voice console, recovery handoff, and explicit-flag Voice Lab evidence inbox | 2026-09-04 |
| `esp32s3-home-assistant/dashboard-bootstrap.css` | Tiny first-load stylesheet that masks the stock ESPHome shell until the custom dashboard is ready | 2026-09-03 |
| `esp32s3-home-assistant/dashboard.js` | Responsive voice console with 0–100% volume, varied local sound/speech and mono/stereo test controls, recovery actions, and Voice Lab evidence inbox | 2026-09-04 |
| `esp32s3-home-assistant/device.yaml` | ESPHome/ESP-IDF N16R8 satellite with Hey Burden, full-scale volume, direct 16 kHz Assist, ring power relief, guarded nonblocking sound/speech tests, diagnostics, and OLED states | 2026-09-04 |
| `esp32s3-home-assistant/HARDWARE.md` | Canonical voice-satellite guide with per-device wiring, bridged `2025-V1.4` `IN-OUT`/4.8 V power path, low-distortion MAX98357A gain/decoupling/power layout, safety notes, diagrams, and peripheral specifications | 2026-09-04 |
| `esp32s3-home-assistant/README.md` | v2 hardware, full-scale speaker behavior, native mDNS-aware reconnection, direct Assist confirmation playback with TTS fail-safe recovery, focused local voice pipeline, exhaustive review queue, dashboard, build, flash, debugging, and architecture guide | 2026-09-04 |
| `esp32s3-home-assistant/wake-word-training/.gitignore` | Excludes generated local microWakeWord artifacts while retaining their staging documentation | 2026-08-23 |
| `esp32s3-home-assistant/wake-word-training/README.md` | Reproducible on-device Hey Burden corpus, feature, training, threshold, and export workflow | 2026-08-23 |
| `esp32s3-home-assistant/wake-word-training/artifacts/README.md` | Explains the private/ignored custom microWakeWord deployment artifacts | 2026-08-23 |
| `esp32s3-home-assistant/wake-word-training/artifacts/hey_burden.json` | Ignored local ESPHome manifest for the trained Hey Burden model and conservative streaming threshold | 2026-08-23 |
| `esp32s3-home-assistant/wake-word-training/artifacts/hey_burden.tflite` | Ignored local quantized streaming microWakeWord model compiled into the operator firmware | 2026-08-23 |
| `esp32s3-home-assistant/wake-word-training/requirements.txt` | Pinned TensorFlow, TensorBoard, dataset, and audio-metadata dependencies for model training | 2026-08-23 |
| `esp32s3-home-assistant/wake-word-training/setup-micro-wake-word.ps1` | Portable WSL environment setup pinned to the tested OHF micro-wake-word revision | 2026-08-23 |
| `esp32s3-home-assistant/wake-word-training/train-micro-wake-word.ps1` | Portable PowerShell launcher for feature generation, training, resume, and export stages | 2026-08-23 |
| `esp32s3-home-assistant/wake-word-training/train_micro_wake_word.py` | Generates memory-mapped features, trains/evaluates the mixed network, and exports the ESPHome artifact pair | 2026-08-23 |
| `esp32s3-home-assistant/scripts/apply-esphome-speaker-race-fix.ps1` | Idempotent guarded ESPHome 2026.7.0 startup-race workaround plus removal of the retired forced-stereo Assist patch | 2026-08-23 |
| `esp32s3-home-assistant/scripts/build-dashboard-bundle.ps1` | Regenerates the cleanly separated offline dashboard from official ESPHome v3 UI code, a bounded stock-UI fail-open, and explicitly UTF-8-decoded maintained enhancements | 2026-09-04 |
| `esp32s3-home-assistant/scripts/export-voice-sessions.py` | Credential-free JSON/CSV packager for session-indexed voice telemetry retained in a Home Assistant Recorder SQLite database | 2026-08-23 |
| `esp32s3-home-assistant/scripts/flash.ps1` | Reproducible dependency-patch, dashboard-build, compile, flash, and log wrapper | 2026-08-22 |
| `esp32s3-home-assistant/scripts/migrate-legacy-secrets.ps1` | Credential-safe migration of ignored legacy Wi-Fi values plus fresh ESPHome API/OTA credentials | 2026-08-22 |
| `esp32s3-home-assistant/secrets.yaml` | Ignored local ESPHome Wi-Fi, encrypted API, and OTA credentials | 2026-08-22 |
| `esp32s3-home-assistant/secrets.yaml.example` | Value-free Wi-Fi, API encryption, and OTA configuration template | 2026-08-22 |
| `esp32s3-home-assistant/server/.dockerignore` | Excludes credentials, persistent models/diagnostics, caches, and logs from the derived recognizer build context | 2026-08-23 |
| `esp32s3-home-assistant/server/.env.example` | Value-free focused-local voice ports, count/storage-only diagnostic retention settings, Home Assistant endpoint, and private-token placeholder | 2026-08-24 |
| `esp32s3-home-assistant/server/.gitignore` | Excludes server environment and persistent model data | 2026-08-22 |
| `esp32s3-home-assistant/server/Dockerfile.speech-to-phrase-diagnostics` | Reproducibly derives the diagnostic recognizer from the pinned upstream Speech-to-Phrase 1.4.3 image | 2026-08-23 |
| `esp32s3-home-assistant/server/diagnostics/transcribe_kaldi.py` | Instrumented upstream-compatible Kaldi path writing atomic WAV, N-best/cost, fuzzy, timing/confidence, and signal evidence for service-owned retention | 2026-08-24 |
| `esp32s3-home-assistant/server/diagnostics_server.py` | Private-LAN diagnostics/review API with locked report-before-prune retention, deterministic findings, and report-analysis tracking | 2026-08-24 |
| `esp32s3-home-assistant/server/docker-compose.yml` | Pinned focused-local Speech-to-Phrase/Piper stack plus writable annotation/report volumes and count/storage research retention service | 2026-08-24 |
| `esp32s3-home-assistant/server/README.md` | Focused-local architecture, host-networked Home Assistant/Wyoming routing, exhaustive diagnostic-ledger queue behavior, research lifecycle, safe staging, acoustic privacy, and version policy | 2026-09-04 |
| `esp32s3-home-assistant/server/custom_sentences/en/lights.yaml` | Finite Speech-to-Phrase grammar for plural light on/off, both natural turn/switch verb orders, and acoustically distinct up/out alternatives | 2026-08-23 |
| `esp32s3-home-assistant/server/test_diagnostics_server.py` | Unit coverage for record loading, no-age-expiry, annotation preservation, and report-before-prune ordering | 2026-08-24 |
| `esp32s3-home-assistant-legacy-2026-08-22/.gitignore` | Legacy Arduino build exclusions | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/diagram.json` | Legacy Wokwi hardware layout | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/CHANGELOG.md` | Legacy implementation history and public-safe configuration cleanup | 2026-08-23 |
| `esp32s3-home-assistant-legacy-2026-08-22/include/dashboard_gz.h` | Legacy generated dashboard asset rebuilt from the public-safe web source | 2026-08-23 |
| `esp32s3-home-assistant-legacy-2026-08-22/include/secrets.h` | Legacy ignored local configuration | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/include/secrets.h.example` | Legacy value-free configuration template with documented address and entity placeholders | 2026-08-23 |
| `esp32s3-home-assistant-legacy-2026-08-22/inmp441.chip.json` | Legacy Wokwi INMP441 chip definition | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/max98357a.chip.json` | Legacy Wokwi MAX98357A chip definition | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/platformio.ini` | Legacy Arduino N16R8 build configuration | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/README.md` | Legacy hardware and public-safe operator documentation | 2026-08-23 |
| `esp32s3-home-assistant-legacy-2026-08-22/scripts/build-dashboard.ps1` | Legacy dashboard asset builder | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/src/main.cpp` | Rollback-only custom Arduino/Wyoming voice firmware with configurable public-safe deployment defaults | 2026-08-23 |
| `esp32s3-home-assistant-legacy-2026-08-22/web/index.html` | Legacy custom diagnostics/control dashboard using generic lamp aliases and documentation addresses | 2026-08-23 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/.gitignore` | Legacy generated wake-asset and local-deployment exclusions | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/README.md` | Legacy openWakeWord training and deployment guide | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/artifacts/README.md` | Legacy generated model staging instructions | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/deployment.example.json` | Legacy value-free deployment target example | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/deployment.local.json` | Legacy ignored private deployment target | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/local/check_environment.py` | Legacy CUDA and audio environment probe | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/local/normalize_clips.py` | Legacy generated-audio normalizer | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/local/patch_upstream.py` | Legacy openWakeWord compatibility patcher | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/local/piper_compat/generate_samples.py` | Legacy Piper sample-generation adapter | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/local/prepare_data.py` | Legacy public training-data preparer | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/local/requirements-convert.txt` | Legacy conversion dependency pins | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/local/requirements.txt` | Legacy training dependency pins | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/local/run_training.sh` | Legacy resumable training stage runner | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/local/runtime_compat/sitecustomize.py` | Legacy runtime compatibility shim | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/local/setup.sh` | Legacy WSL/CUDA environment bootstrap | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/recordings/README.md` | Legacy real-device recording protocol | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/scripts/check-service.ps1` | Legacy Wyoming wake-service probe | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/scripts/install-model.ps1` | Legacy openWakeWord model installer | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/scripts/setup-local.ps1` | Legacy Windows WSL setup launcher | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/scripts/start-training.ps1` | Legacy Colab training launcher | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/scripts/train-local.ps1` | Legacy local training launcher | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/scripts/validate-model.ps1` | Legacy openWakeWord model validator | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wake-word-training/training-profile.json` | Legacy Hey Burden training phrase profile | 2026-08-22 |
| `esp32s3-home-assistant-legacy-2026-08-22/wokwi.toml` | Legacy Wokwi simulator configuration | 2026-08-22 |
| `LICENSE` | Project file | 2026-08-09 |
| `NOTICE.md` | Documentation | 2026-08-09 |
| `README.md` | Repository homepage with current CYD features, setup/recovery links and deployment overview | 2026-09-06 |
| `SECURITY.md` | Documentation | 2026-08-09 |


## Architecture Overview

The repository is organized as a workspace of independent ESP32 firmware projects alongside self-hosted support services:

1. `assistant/`: Clean-slate standalone voice satellite without OLED display, dedicated to INMP441 I2S mic, MAX98357A I2S DAC amp, Wyoming Whisper STT, and instant Govee UDP / HA light control for *"Hey Burden lights on / off"*.
2. `cyd-usage-monitor/`: ESP32-2432S028R Cheap Yellow Display usage monitor with dual-app launcher, OpenRouter telemetry, and local server.
3. `esp32s3-home-assistant/`: Primary clean-room ESPHome/ESP-IDF voice satellite with a locally trained on-device Hey Burden microWakeWord, constrained Speech-to-Phrase commands, Home Assistant intents, Piper feedback, MAX98357A audio, SSD1306 state display, and a focused diagnostics dashboard. The dated legacy sibling is rollback-only.

