# Project Context

## Current State

CYD Usage Monitor and the primary clean-room `esp32s3-home-assistant` ESPHome
voice satellite comprise independent, self-contained ESP32 firmware projects
and self-hosted container services. The former custom Arduino voice firmware is
preserved in a dated rollback-only directory. Projects requiring physical pin connections feature
interactive Wokwi `diagram.json` visual layouts, embedded Mermaid flowcharts, ASCII
schematics, and comprehensive pin mapping documentation.

Project Brain Protocol v1.1.0 is active and healthy at the repository root.

## Recent Changes
### 2026-08-27 — CYD Wi-Fi Prevention & Staged Recovery
- Reduced avoidable Wi-Fi interruptions on the continuously powered CYD by disabling ESP32 modem sleep, while retaining station-only mode, non-persistent credentials, and the framework's passive auto-reconnect.
- Added serial disconnect-reason names/numbers plus connected RSSI/channel evidence so future AP, RF, authentication, and driver failures can be distinguished instead of inferred from the screen.
- Added conservative fallback stages: explicit reconnect after 30 seconds, one station-radio reinitialization after two minutes, and a full ESP restart only after five minutes when that boot previously held a healthy connection. This avoids reboot loops during an AP outage or invalid configuration.
- Updated the launcher to show `Recovering`, documented the power/reliability tradeoff and recovery timing, and completed a clean PlatformIO firmware build at 37.5% RAM / 63.5% flash.
- Flashed the verified 1,255,056-byte image to the attached CH340 CYD on COM9. Controlled-reboot serial evidence captured one transient `ASSOC_FAIL` followed by a healthy connection at -53 dBm on channel 1, remote Usage Monitor routing, and synchronized 180-degree display state; the strong signal makes persistent weak RF unlikely at the current placement.
- Files affected: `docs/{context.md,map.md}` and `cyd-usage-monitor/{CHANGELOG.md,README.md,src/main.cpp}`.

### 2026-08-27 — Dashboard Favicon & High-Res App Icon Assets
- Generated a high-contrast cybernetic CYD monitor master icon (1024x1024) featuring the dark squircle chassis, glowing emerald-teal quota gauge arc meter, and gold/amber status accents.
- Created full multi-resolution raster and vector favicon suite: `cyd-monitor-icon-1024.png`, `icon-512.png`, `icon-192.png`, `apple-touch-icon.png` (180x180), `favicon-32x32.png`, `favicon-16x16.png`, multi-size `favicon.ico` (16/32/48/64px), and crisp scalable `favicon.svg`. Added complete cycle, cycle-badge, and sync action-icon families for Stream Deck and launcher shortcuts.
- Updated `dashboard.html` `<head>` with SVG, PNG, and Apple Touch Icon `<link>` tags, and added direct public `/favicon.ico` routing in `server.py`.
- Added automated server tests in `test_server.py` covering unauthenticated public favicon, SVG, and raster asset serving (all 47 tests passing).
- Deployed live to the operator-configured private host, rebuilt production containers, and verified healthy live responses (`200 OK`) across all favicon routes.
- Files affected: `docs/{context.md,map.md}`, `cyd-usage-monitor/CHANGELOG.md`, `cyd-usage-monitor/server/{dashboard.html,server.py,test_server.py,static/{apple-touch-icon.png,cyd-monitor-*-icon-*.png,cyd-monitor-icon-1024.png,favicon-16x16.png,favicon-32x32.png,favicon.ico,favicon.svg,icon-192.png,icon-512.png}}`.

### 2026-08-27 — Stream Deck Usage-Account Cycling
- Added a Windows Stream Deck helper that calls the existing private Bearer-protected next-account endpoint without storing its token in Stream Deck arguments or repository files.
- Added a windowless WScript launcher so Stream Deck can invoke the PowerShell helper without briefly flashing a console window.
- Configured the operator's Windows user environment from the already-flashed CYD's ignored private endpoint/token values. Each press rotates enabled Codex/Antigravity profiles and forces both the physical CYD and dashboard preview into Usage Monitor; OpenRouter is excluded.
- Files affected: `docs/{context.md,map.md}` and `cyd-usage-monitor/{CHANGELOG.md,README.md,scripts/stream-deck-next-account.{ps1,vbs}}`.

### 2026-08-27 — Dashboard-Controlled 180° CYD Rotation
- Added a persisted dashboard control that switches the physical E32R40T between normal and 180-degree-flipped landscape orientations through the existing private display-command poll. The 480x320 layout is unchanged, and resistive-touch coordinates invert with the panel so controls stay aligned upside down.
- Kept the browser LVGL preview upright and added a physical `0°`/`180°` indicator. The physical CYD now stores its last orientation in Preferences/NVS, so it restores immediately on reboot before networking is available.
- Added bidirectional launcher/Usage Monitor/OpenRouter synchronization: browser preview navigation commands the physical CYD, while physical touch navigation reports its state through a Bearer-only device endpoint and the browser follows it. Home and account selection participate in the same persisted route.
- Passed 46 server tests and completed fresh WebAssembly and PlatformIO builds at 37.5% RAM and 63.2% flash.
- Flashed the 1,249,728-byte firmware image to the attached CH340 CYD on COM9 with verified segment hashes. Serial boot confirmed that the new firmware restored the saved 180-degree orientation from NVS before networking, received remote Launcher/Usage routes, and reported synchronized app state back to the server.
- Visually tested the upright launcher and OpenRouter preview, the 180-degree indicator, an unchanged CSS canvas transform, and device-to-browser route following. Backed up the live source/private state, deployed the rebuilt application, and preserved all configured profiles while leaving the collector and Tunnel running. All three services are healthy; production device-route isolation returned `401` unauthenticated, `200` with Bearer authentication, and `404` for a dashboard-only route on the device listener.
- Kept root microphone diagnostic WAV captures out of version control as private runtime artifacts.
- Files affected: `.gitignore`, `docs/{context.md,map.md}`, and `cyd-usage-monitor/{CHANGELOG.md,README.md,server/{dashboard.html,server.py,static/lvgl/{cyd_lvgl.js,cyd_lvgl.wasm},test_server.py},simulator/{build-wasm.ps1,lvgl_cyd_sim.c},src/main.cpp}`.

### 2026-08-27 — Dashboard-Managed Email Integration & Draft Preservation
- Added a protected Alerts email setup flow with Gmail/Google Workspace and custom TLS SMTP modes. Gmail presets the official SMTP endpoint and accepts whitespace-formatted app passwords; custom mode supports STARTTLS or implicit TLS, host, port, sender, recipient, username, and provider credential.
- Stored dashboard-submitted SMTP credentials atomically in private mode-`0600` runtime data. Status responses expose only safe setup metadata; passwords and usernames never return to the browser. Existing host environment SMTP settings take precedence and make the dashboard form read-only.
- Chose app-password/provider SMTP setup over Gmail OAuth because alert-only OAuth would add a Google Cloud project, consent/redirect configuration, Gmail scopes, verification considerations, and a refresh-token lifecycle. Added save, test, health, and remove controls plus server-side address, hostname, port, and TLS validation.
- Passed 44 server tests, Compose and JavaScript validation, visually tested Gmail/custom dashboard states, and deployed the rebuilt application and collector to the configured private host. Production correctly reports email unconfigured until the operator supplies a credential through the new form.
- Fixed the live email form losing earlier values as focus moved between fields: the 1.2-second telemetry renderer now hydrates the form only when server-side email configuration actually changes, and focus/input/change events keep the complete browser draft authoritative until Save succeeds. Revalidated 44 tests and redeployed the dashboard application.
- Files affected: `docs/{context.md,map.md}` and `cyd-usage-monitor/{CHANGELOG.md,README.md,instructions/{DEPLOYMENT_RUNBOOK.md,TOKEN_GUIDE.md},server/{collector.py,dashboard.html,server.py,test_collector.py,test_server.py}}`.

### 2026-08-26 — Dual Codex Quotas, Durable Identity & Independent Alert Fallback
- Updated the common Codex collection path to parse the current rolling 5-hour and weekly quota windows while retaining the one-shot update-prompt Skip responder for every existing or future Codex profile. Successful CLI-visible identities are now persisted on the profile, so later collection errors, incidents, alerts, dashboard cards, and CYD payloads continue to identify the affected account.
- Added physical and WebAssembly LVGL Codex dual-limit layouts plus protected dashboard-to-device app commands. The OpenRouter overview now has **Show on CYD**, and CLI profile selection switches both the live preview and physical display back to Usage Monitor.
- Added host-only STARTTLS/TLS SMTP as an independent, deduplicated fallback when WAHA delivery fails, with dashboard health and a test action. The production deployment has no SMTP credentials yet, so the transport is installed but intentionally reports unconfigured until the operator provides a dedicated SMTP account or app password.
- Browser-tested healthy, error-identity, Codex dual-limit, and OpenRouter/Usage preview states; deployed the rebuilt app/collector, verified all configured profiles healthy with both Codex accounts carrying 5-hour/weekly telemetry and durable identity, flashed COM7, and serial-confirmed both remote routes. Passed 42 server tests, Compose validation, JavaScript syntax, PlatformIO, and Emscripten builds.
- Files affected: `docs/{context.md,map.md}` and `cyd-usage-monitor/{.env.example,CHANGELOG.md,README.md,docker-compose.yml,instructions/{DEPLOYMENT_RUNBOOK.md,TOKEN_GUIDE.md},server/{collector.py,dashboard.html,server.py,static/lvgl/{cyd_lvgl.js,cyd_lvgl.wasm},test_collector.py,test_server.py},simulator/{build-wasm.ps1,lvgl_cyd_sim.c},src/main.cpp}`.

### 2026-08-26 — CYD Navigation, Codex Collection & Alert Delivery Repair
- Fixed the Hosyond E32R40T launcher by applying TFT_eSPI's complete five-value resistive calibration, making decorative launcher children click-through, clearing competing route flags, enlarging Home targets, and adding navigation serial diagnostics. Usage Monitor, OpenRouter, and Home now have independent reliable routes in firmware and the browser simulator.
- Traced both live Codex failures to version 0.147.0's startup self-update prompt intercepting scheduled `/status`. The collector now detects the ANSI-rendered prompt and selects Skip once without mutating the read-only container; both configured Codex accounts and Antigravity returned to fresh `ok` telemetry after deployment.
- Made failed WAHA sends durable and retryable, suppressed recovery messages for outages whose failure alert was never delivered, and exposed delivery errors as a red dashboard Overview status. The failed private WAHA session was restarted and is waiting for the operator to scan its QR code before a test alert can be delivered.
- Rebuilt the firmware and WebAssembly preview, deployed the collector repair to the configured private host, and passed 35 server tests plus the PlatformIO and simulator builds.
- Files affected: `docs/{context.md,map.md}` and `cyd-usage-monitor/{CHANGELOG.md,README.md,server/{collector.py,dashboard.html,static/lvgl/cyd_lvgl.wasm,test_collector.py},simulator/lvgl_cyd_sim.c,src/main.cpp}`.

### 2026-08-26 — Hosyond E32R40T Hardware Correction & Verified Flash
- Identified the connected Hosyond 4.0-inch ESP32-32E module behind reseller listing ASIN B0G1M857NL as the E32R40T hardware family. Although the listing title incorrectly says ILI9341 240×320, its detailed specification and the manufacturer documentation identify an ST7796S 320×480 display with XPT2046 resistive touch.
- Corrected the mixed-board configuration: backlight GPIO27, red LED GPIO22, and XPT2046 sharing LCD SPI on GPIO14/13/12 with CS GPIO33 and IRQ GPIO36. Removed incompatible GT911 probing and separate-touch-bus setup, and reduced CH340C upload speed to 460800 baud.
- Built and flashed the 1,214,224-byte image to COM7 with verified hashes. Serial boot confirmed the display path, E32R40T touch initialization, live touch coordinates, and repeated launcher account-switch actions. The pre-existing 4 MiB factory backup remains intact with SHA-256 `445F6FCB210442777F04028F3AD2022BD1C7231B5D9907309D8514F863978315`.
- Files affected: `docs/{context.md,map.md}` and `cyd-usage-monitor/{CHANGELOG.md,README.md,instructions/FLASHING_GUIDE.md,platformio.ini,src/main.cpp}`.

### 2026-08-26 — CYD ST7796 480x320 Responsive Layout & Dual-Touch Integration
- Upgraded the CYD Usage Monitor LVGL UI layout to full native 480×320 screen geometry for the 3.5-inch ST7796 display, expanding Launcher tiles, ChatGPT metrics, Antigravity 2x2 grid, and OpenRouter spend/charts edge-to-edge.
- Integrated dual-touch hardware autodetection supporting both capacitive (GT911 on I2C `SDA=33, SCL=32`) and resistive (XPT2046 on shared SPI `CS=33, IRQ=36`) touch controllers with real-time ADC pressure tracking.
- Removed `-D TFT_INVERSION_ON=1` to restore the correct dark-mode UI palette.
- Files affected: `docs/{context.md,map.md}`, `cyd-usage-monitor/{platformio.ini,src/main.cpp}`.

### 2026-08-26 — Physical CYD Backup, Driver Setup & Usage Monitor Flash
- Provisioned the physical ESP32-2432S028R Cheap Yellow Display over COM7 after installing the WCH CH340 USB-to-serial driver.
- Performed a full 4MB raw flash dump saved to `cyd-usage-monitor/data/factory_backup.bin` before modifying flash, preserving the factory vendor hardware selftest and LVGL 8 `lv_demo_widgets()` benchmark suite (analytics, shop, profile, and performance meters).
- Configured local Wi-Fi credentials in `cyd-usage-monitor/include/secrets.h`, compiled the release firmware with PlatformIO, and flashed the two-app CYD Usage Monitor and OpenRouter UI image. Verified boot and touch navigation startup on physical hardware.
- Files affected: `docs/{context.md,map.md}`, `.gitignore`, and `cyd-usage-monitor/{include/secrets.h,data/factory_backup.bin}`.

## History Summary
<!-- Compressed summaries of older changes go here -->

- Identified the purchased voice-satellite modules and corrected the carrier's INMP441 footprint to the real 14 mm round 2x3 geometry on 2026-08-24; amplifier/OLED bodies and exact ESP32-S3 board dimensions still gate fabrication and case CAD.

- Audited and corrected the code-defined TSCircuit PCB carrier board on 2026-08-24 with official DevKit pinout, peripheral-only power selection, radial capacitor, export scripts, and `npm run validate` gate.

- Reworked the ESPHome operations console into a responsive readiness overview and master-detail Research Sessions workspace on 2026-08-24, then rebuilt and OTA-validated it on the physical device.

- Added report-before-prune voice research retention, private review/report APIs, archive telemetry, and the master-detail Research Sessions redesign on 2026-08-24; validated retention ordering, responsive UI, the live private service, ESPHome compile, and physical OTA deployment.

- Added bounded post-VAD WAV/JSON acoustic diagnostics, Kaldi candidate/cost evidence, a hardened private diagnostics API, and transcript/time dashboard correlation on 2026-08-23; later report-before-prune research retention superseded its age-based lifecycle.

- Added durable UTF-8 dashboard bundling, refresh-stable Overview/Research routes, compact expandable recognition records, and transparent constrained-decoder evidence on 2026-08-23; later dashboard and research-console redesigns expanded that foundation.

- Added natural verb-order light intents, an always-audible wake acknowledgement, phase-specific LED-ring behavior, structured voice-session logs, and a reviewed Session History dashboard on 2026-08-23; later acoustic research and dashboard redesigns expanded that foundation.

- Replaced the ESP32-S3 voice satellite's temporary manual LED entity with a GPIO4 12-pixel GRB status ring, added voice-stage readiness/timing diagnostics, restored safe pre-roll bounds, documented protected 5V wiring, and validated the physical OTA deployment on 2026-08-23.

- Added local buffered-microphone pre-roll bridging for one-breath voice captures and initial manual 24-pixel LED ring controls on 2026-08-23 before status-owned 12-pixel ring refactoring.

- Trained and deployed the custom 62,304-byte quantized streaming Hey Burden microWakeWord model (0.87 cutoff), tuned MAX98357A gain margins, and verified clean native-I2S streaming on 2026-08-23.
- Made the speaker diagnostic single-run to prevent rapid-click I2S task restarts and queue overflow, then validated an end-to-end light command and clean 16 kHz response drain on 2026-08-23.
- Restored native Philips I2S timing, unified 16 kHz mono format metadata, and validated live MAX98357A speaker diagnostics on 2026-08-23.
- Moved wake detection on-device with Okay Nabu, added focused far-field capture diagnostics, corrected dashboard volume mapping, and established fresh Assist pipelines on 2026-08-23; the later custom Hey Burden model, buffered pre-roll bridge, and native-I2S repair superseded the interim wake and audio details.
- Cut over from Faster Whisper to the digest-pinned focused-local Speech-to-Phrase/explicit Bedroom intent/Piper architecture on 2026-08-23, added exact action and timing observability, temporarily matched the legacy MSB/stereo output, and sanitized deployment-specific values; later native-I2S, on-device Hey Burden, and acoustic research changes refined this foundation.
- Used a lights-only Faster Whisper bias and restored MSB amplifier output on 2026-08-22 while investigating empty/incorrect short commands and silent standard-I2S tests; the later native-I2S repair and constrained Speech-to-Phrase architecture superseded both paths.
- Tried standard-I2S output and continuous server-side Okay Nabu/Faster Whisper capture on 2026-08-22, including adaptive acknowledgement and continuous-listening recovery; the later fitted-amplifier audio repair, on-device Hey Burden model, and buffered focused-local Speech-to-Phrase architecture superseded that path.
- Improved room-intent reliability and calibrated crisp audio on 2026-08-22 by removing Whisper's silence-biasing device prompt, constraining entity exposure, adding observed clipped-wake variants, shortening/fading the acknowledgement, and adding volume/Wake Sound controls; the later Speech-to-Phrase and buffered one-breath path superseded that recognizer and feedback timing.
- Established Bedroom-only one-breath commands on 2026-08-22 by restricting Assist exposure, adding duplicate-phrase intent handling for the then-active Whisper recognizer, streaming command audio immediately after wake, adding persistent volume/acknowledgement controls, and physically validating the flashed device; the later focused-local Speech-to-Phrase architecture superseded that recognition path.
- Raised voice output to 30%, tuned the then-active Whisper/VAD path, added missing OLED glyphs and the scrollable local dashboard log, and corrected one-shot Assist/speaker startup recovery on 2026-08-22 before the later focused-local Speech-to-Phrase cutover.
- Rebuilt the canonical clean-room ESPHome/ESP-IDF N16R8 voice satellite on 2026-08-22, preserving the former Arduino/Wyoming implementation as a dated rollback directory; established encrypted Home Assistant Assist, focused diagnostics, local wake inference, dual-I2S hardware, recovery controls, and the initial Whisper/Piper integration before later focused-local audio and wake refinements.
- Restored the physical N16R8 memory profile and PSRAM allocation on 2026-08-22, verified stable dashboard/voice operation on the device, and added the ignored local operator topology map for deployment details.
- Built a resumable local RTX 5070/WSL2 Hey Burden training pipeline with isolated generation/conversion environments, CUDA validation, streaming false-positive batches, and real-room tuning guidance on 2026-08-21; it is preserved in the dated legacy project.
- Stabilized the legacy dashboard and continuous wake stream on 2026-08-22 with a deterministic gzip asset, rolling WebSocket diagnostics, batched microphone frames, bounded socket writes, and a verified 90-second physical-device soak; that implementation is preserved in the dated rollback project.
- Added a repeatable Hey Burden training/deployment workspace with synthetic training, artifact validation, credential-free service probing, and real-room tuning guidance on 2026-08-21; it is now preserved in the dated legacy project.
- The retired custom firmware gained a Core 1 Wyoming openWakeWord client, adaptive VAD/pre-roll, zero-wait Govee control, and wake telemetry on 2026-08-21; the clean-room ESPHome build later replaced that hand-built streaming/state-machine path.
- Established the original N16R8 standalone assistant profile, dual-I2S audio tasks, speaker/microphone exclusion, Whisper prompt tuning, and COM4 deployment on 2026-08-17.
- Promoted the former `esp32s3-ha-media-player` directory to the canonical `esp32s3-home-assistant` project and removed standalone microphone/OLED/speaker diagnostic projects on 2026-08-21.
- The retired custom firmware gained Hey Burden matching, 200 ms microphone pre-roll, tuned VAD, speaker/microphone exclusion, Wyoming response parsing, direct light intents, and simulated dashboard commands on 2026-08-21 before the clean-room ESPHome rebuild replaced that path.
- Removed the legacy browser speech/audio path on 2026-08-21 while retaining the physical INMP441-to-Whisper pipeline; that implementation is now preserved in the dated rollback project.
- Added the legacy OLED voice transcript/action footer and hardened dual-address I2C discovery on 2026-08-21; that UI is now preserved only in the rollback implementation.
- Corrected MAX98357A MSB audio alignment and Wyoming Whisper `data_length` response parsing, then compiled and flashed the physical ESP32-S3 on 2026-08-17.
- Added low-latency direct Govee UDP control with queued Home Assistant state synchronization, lamp-specific voice intents, BOOT-button toggling, and dashboard controls on 2026-08-17.
- Generated interactive Wokwi visual schematics (`diagram.json` and `wokwi.toml`) and comprehensive hardware documentation across all projects on 2026-08-16.
- Recorded the active ESP32-S3 device address in local operator documentation on 2026-08-17; deployment-specific addresses remain outside the public training workflow.
- Built low-latency zero-wait direct real-time TTS audio streaming pipeline and Web OTA in `esp32s3-home-assistant` on 2026-08-16.

- Documented OLED `VCC`/`VDD` labeling across the ESP32-S3 hardware guides on 2026-08-17; the standalone diagnostic projects were later removed.
- Earlier live-microphone work established 16kHz INMP441 DSP, WebSocket audio, and Wyoming Whisper buffering before the browser streaming path was later removed in favor of the physical voice pipeline.
- Hardened that earlier live-microphone path with buffered WebSocket streaming, a decoupled Whisper worker, trigger matching, and HA light control on 2026-08-17 before the browser path was retired.
- Documented hardware inventory (ESP32-S3 N16R8, SSD1306, INMP441, MAX98357A, box speaker) and deployed Wyoming Whisper/Piper/openWakeWord/HA voice satellite stack on 2026-08-15.
- Debounced transient CLI failure alerts and added structured WhatsApp incident retry on 2026-08-11.
- Added Collector Incident Diagnostics, bounded structured history, and formatted WhatsApp Alerts with automatic retry on 2026-08-11.
- Added Collector Incident Diagnostics, bounded structured history, and formatted WhatsApp Alerts with automatic retry on 2026-08-09.
- Upgraded production container image to Python 3.14 on 2026-08-09 and verified server tests.

- Verified stable WebAssembly semantic module exports and ABI checks in CI on 2026-08-09.

- Restored Usage Monitor pointer interaction in the WebAssembly preview and connected controls to active-profile selection on 2026-08-09.
- Added OpenRouter credits launcher app, Management API collection, balance arc, and 7-day chart on 2026-08-09.
- Added Wokwi serial shortcuts (`U`, `H`, `N`, `?`), Utilities tab, and scaled preview on 2026-08-09.
- Added pastel CYD App Launcher on 2026-08-09 with non-blocking Wi-Fi, touch latch,
  Usage Monitor and OpenRouter apps, matching WebAssembly simulator, and test coverage.
- Restored LAN-only CYD telemetry on 2026-08-09 by replacing device-side
  Cloudflare HTTPS with private RFC1918 HTTP, splitting the Python service
  into Tunnel-only and Bearer-protected LAN listeners, removing obsolete
  Cloudflare device ingress, and refreshing the Graphify graph.
- Verified persistent Wokwi HTTPS against GTS WE1 issuing CA, keep-alive connections,
  and deliberate top-right arrow touch navigation alongside serial shortcuts.
- Project Brain Protocol was upgraded to v1.1.0 while preserving all
  project-specific instructions outside the managed block.
- Earlier Wokwi TLS work isolated an emulator-compatible verified certificate
  path and documented handshake diagnostics before device telemetry later
  returned to the private-LAN-only architecture.
- Wokwi networking diagnostics use bounded emulator-friendly TLS/NTP timeouts
  and credential-safe mbedTLS errors, with corrected operator guidance.
- Earlier CYD networking work corrected the Cloudflare trust chain, separated
  touch/TFT SPI buses, added the protected flashing guide, and verified the
  deployed dashboard/device boundary before telemetry later moved to LAN-only.
- Graphify was activated on 2026-08-09 as a deterministic, source-only graph
  over 12 tracked C/C++, Python, and PowerShell files, with repository-relative
  references and no dependency, generated-asset, secret, or LLM input.
- Project Brain Protocol v1.1.0 was initialized on 2026-08-09 with the
  discovered ESP32/Python/Docker architecture, build commands, repository
  map, context ledger, and preserved workspace policies.
- Initial deployment hardening introduced the Cloudflare Tunnel, separated
  human and device authentication, protected runtime secrets, and documented
  the public-release security boundary before later returning CYD telemetry to
  a private-LAN-only path.
- The hardened application and Tunnel were deployed to the operator-confirmed
  host with private runtime state, rollback protection, verified layered
  authentication, live telemetry, and no tracked deployment identifiers.
- A public-safe operator runbook documented the remote-only Tunnel boundary,
  layered dashboard login, credential operations, deployment verification,
  rollback, and Git release checks.

## Next Steps
<!-- What should be worked on next? -->

- Evaluate optional OpenRouter low-balance/spend alerts only if thresholds and
  delivery behavior are explicitly defined; collection is currently read-only.

## Known Issues
<!-- Active bugs, tech debt, or blockers -->

*None currently identified in the clean-room voice path; physical confirmation
of perceived earcon/TTS loudness remains an operator acceptance check.*
