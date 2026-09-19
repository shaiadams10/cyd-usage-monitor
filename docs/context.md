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

### 2026-09-18 — Antigravity Disabled Quota Support
- Diagnosed persistent Antigravity CLI collection failures (258 consecutive failures
  on the active profile) when Claude models reached their weekly limit (0.00% remaining).
  The CLI renders `Disabled: You have hit your weekly limit, the 5-hour limit does not
  currently apply...` without a numerical percentage, causing `parse_antigravity_usage`
  to raise a ValueError and time out.
- Added parsing support for disabled limit layouts in `parse_antigravity_usage`:
  reports 0% remaining quota and "Weekly limit reached" (or "Limit reached") reset status.
- Hardened server `usage_sub` to format non-duration reset strings cleanly without
  awkward "Refresh in: " prefixes.
- Added comprehensive unit tests in `test_collector.py` and `test_server.py`; verified
  all 55 server tests and 21 helper tests pass.
- Files: cyd-usage-monitor/server/{collector.py,server.py,test_collector.py,test_server.py},
  cyd-usage-monitor/CHANGELOG.md, docs/{context.md,map.md}.

### 2026-09-13 — CYD Fixed-Address Recovery
- Diagnosed a healthy monitor application published on a stale LAN address
  after the Wi-Fi host received a different DHCP lease. The physical CYD kept
  its Wi-Fi association but could not reach its private device API.
- Reserved the original server address for the host in the gateway, restarted
  only the affected Wi-Fi radio, restored the private Compose bind, and
  recreated only the monitor app. Collector and Tunnel containers remained
  running; no application source, image, or firmware behavior changed.
- Verified the host returned on its reservation, the app was healthy, the
  unauthenticated API returned 401, the authenticated API returned 200, and a
  fresh physical-device route report plus sustained polling traffic confirmed
  end-to-end CYD recovery without USB serial access.
- Files: docs/{context.md,map.md,map.local.md}; ignored private deployment and
  firmware configuration plus remote rollback backups.

### 2026-09-09 — Codex Desktop Hook Update Recovery
- Diagnosed live Codex hook callbacks failing at identity startup while the
  server, CYD route, mappings, trust and Antigravity watcher remained healthy.
  Codex Desktop had replaced its versioned bundled CLI directory, leaving the
  private helper configuration pointed at a removed executable.
- Added a fail-closed fallback that rediscovers the newest bundled `codex.exe`
  only under the standard Codex Desktop installation directory when the saved
  path no longer exists. Installed matching helpers into shared-home and the
  already-trusted compatibility path without changing hook registration.
- Passed all 18 switching tests and a live Codex identity, mapping and server
  selection check returned `selected`; no prompt, credential or identity data
  was retained or exposed.
- Files: cyd-usage-monitor/{scripts/chat-account-switch.py,
  scripts/test_chat_account_switch.py,README.md,CHANGELOG.md},
  docs/{context.md,map.md}; ignored private runtime helpers and backups.

### 2026-09-09 — CYD Server Network Recovery
- Diagnosed unreachable device API: app was internally healthy but Docker had
  no active network attachments or published ports after an earlier host reboot.
  The configured private LAN address still matched the host. Restart alone did
  not repair it; recreated only the app through existing remote Compose config.
- Verified restored LAN port, authenticated device API HTTP 200, unauthenticated
  HTTP 401, and dashboard listener authentication. Collector remained running.
  Physical screen recovery was not independently confirmed; no USB serial device
  was available. The cause of the lost Docker attachment remains unproven.
- No firmware, application source, image build, or configuration change.
- Files: docs/{context.md,map.md}.


### 2026-09-06 — Desktop Restart Recovery and Switch History
- Proved Codex MSIX redirected the old helper directory into private package
  storage; Windows Task Scheduler could not see it at its configured path.
  Migrated mappings/state to shared user-home storage, preserved the trusted
  live Codex command via its compatibility copy, and installed a per-user task.
- Task supports logon, one-minute recovery, batteries and unlimited runtime.
  Verified scheduled launch and automatic recovery after terminating only the
  verified watcher; operator confirmed a real Antigravity selection. No reboot
  was performed. On-demand diagnostics now verify process and heartbeat age.
- Added bounded local outcome/phase/timing history and 200 server selection/route
  events with allowlisted source tags and hashed task/account references.
  Stream Deck helpers tag requests; no message text or credentials are logged.
- Antigravity 2.12.2 contains hooks and a JSON-hooks flag; global schema matches
  official docs, but the old hook path was inaccessible outside Codex. Installed
  a metadata-only corrected-path probe; no native callback on the operator test.
  Effective feature-flag value and app-reload requirement remain unestablished.
- Passed 16 switching, 3 Windows transport and 53 server tests. Deployed only the
  server layer with source/state/image rollback backups; matching source hashes,
  dashboard/API success and private-history 401/public-route 404 checks passed.
- Files: cyd-usage-monitor/{scripts/chat-account-switch.py,
  scripts/watch-antigravity-messages.py,scripts/install-chat-account-switch.py,
  scripts/install-antigravity-startup.ps1,scripts/test_chat_account_switch.py,
  scripts/stream-deck-next-account.ps1,scripts/stream-deck-next-account.vbs,
  server/server.py,server/test_server.py,AGENTS.md,README.md,CHANGELOG.md,
  instructions/CHAT_ACCOUNT_SWITCH_SETUP.md,instructions/TOKEN_GUIDE.md},
  docs/{context.md,map.md}; ignored operator runtime and map.local.md.


### 2026-09-06 — GitHub Homepage Refresh
- Updated the public root README to cover recent CYD features and link directly
  to desktop recovery, Stream Deck controls, detailed setup, and the changelog.
- Corrected obsolete HTTPS firmware setup and ILI9341 hardware statements using
  the current private-LAN implementation and E32R40T configuration.
- Checked local link targets and source consistency; no runtime changes.
- Files: README.md, cyd-usage-monitor/CHANGELOG.md, docs/{context.md,map.md}.


### 2026-09-06 — CYD Public Release Security Audit
- CI follow-up: isolated all collector test paths and inherited notification
  credentials after clean Linux exposed two accidental production-path reads.
  Files: cyd-usage-monitor/{server/test_collector.py,README.md,CHANGELOG.md}.
- Published commit `7a308608f9c5605a9d8302f6e6339b70c60ed5de` directly to
  GitHub main; followed by test-isolation fix `147ff8b`. Verified remote SHA.
  Final GitHub CI run `34043993243` passed both server and firmware/WASM jobs;
  clean Linux tests and all 66 local Python tests passed.
- Prepared a CYD-only release from upstream main in an isolated worktree because
  two unpublished local commits contain unrelated projects. Preserve local work.
- Hardened both Stream Deck transports against redirects/proxies/automatic Windows
  authentication and noncanonical endpoints; synthetic-token Windows tests pass.
- Gitleaks scanned 15 historical commits and the release tree without leaks;
  private-value and binary-asset checks also found no matches. All 51 server and
  15 helper tests, firmware, LVGL motion, WASM and dashboard syntax checks passed.
- CI now runs Windows helper and real LVGL motion checks; affected workflow:
  .github/workflows/ci.yml.
- Files: cyd-usage-monitor/{scripts/stream-deck-next-account.ps1,
  scripts/stream-deck-next-account.vbs,scripts/test_stream_deck_security.py,
  .gitignore,README.md,CHANGELOG.md}, docs/{context.md,map.md}.

### 2026-09-06 — Desktop Switching Recovery Runbook
- Audited the selector, installer and Windows watcher against setup docs. Added
  a fresh-computer sequence covering prerequisites, private settings/mappings,
  custom labels, installer constraints, trust, startup and acceptance checks.
- Validation: all 12 switching tests and 51 server tests passed; Brain healthy.
- Initially found integration scripts untracked; the subsequent CYD public
  release includes them and their recovery guide. No clean-machine test claimed.
- Files: cyd-usage-monitor/{instructions/CHAT_ACCOUNT_SWITCH_SETUP.md,README.md,
  CHANGELOG.md}, docs/{context.md,map.md}.

### 2026-09-06 — Transition Redraws and Server Reachability
- Follow-up: Stream Deck still used the former LAN address in the Windows user
  setting CYD_USAGE_MONITOR_NEXT_ACCOUNT_URL. Backed up and corrected that
  private setting; account discovery and the actual VBS direct-selection helper
  succeeded while retaining the current account. Helpers read User settings on
  every invocation, so restarting Stream Deck is not required.
- Found post-arrival zero resets/card movement and costly full-screen redraws
  (initial observed maxima 236–289 ms). Replaced slides with directional masked
  strip reveals, coalesced navigation, stable values and no pressed zoom.
- Device associated at strong RSSI with zero disconnects while HTTP failed.
  Server listener worked inside Docker but its published IP was no longer on
  the host. Operator subsequently confirmed the host was off, then restarted it.
  Docker failed startup with cannot-assign-address until private LAN binding
  and firmware endpoint were corrected. Cause of host power-off is unproven.
- Added reset/network/memory/render diagnostics and periodic-fetch backoff.
  Passed 51 server tests, real LVGL motion tests and browser frame checks.
  Firmware hash verification and matching hosted assets/API checks passed.
  Sequential live route acknowledgments passed for all three routes plus both
  provider-selection API checks. Observed 116 requests with zero HTTP failures,
  Wi-Fi disconnects or crash signatures; heap/worker-stack headroom stayed ample.
  Redraw averages remained about 47–57 ms with occasional long frames; no fixed
  frame-rate or universal flicker-elimination claim. Optimized opaque reveal strips.
- Files: cyd-usage-monitor/src/{main.cpp,ui_motion.h}, simulator/{lvgl_cyd_sim.c,
  test_motion.c}, server/static/lvgl/{cyd_lvgl.js,cyd_lvgl.wasm}, README.md,
  CHANGELOG.md, docs/{context.md,map.md}; private config and map.local.md.

### 2026-09-05 — Animated CYD Screens
- Added shared bounded LVGL motion for all four layouts: launcher icon activity,
  eased/staggered quota bars with refresh sweeps, card entrances, and OpenRouter
  arc, exact-cent counters, and seven-column chart transitions.
- Serialized HTTP work on a worker while the UI task pumps LVGL; preserved
  request ordering/timeouts and replaced the blocking 20 ms update LED delay.
  Navigation still waits for the current bounded operation to finish.
- Passed 51 server tests, firmware and production WASM builds, real LVGL motion
  checks, and browser rendering of all four layouts. Saved device flash rollback,
  installed firmware with hash verification (37.7% static RAM / 63.7% flash),
  and deployed matching hosted assets with old assets/image retained. Hosted
  asset hashes, authenticated dashboard/APIs, and unauthenticated denial passed.
  Device-origin acknowledgments passed for OpenRouter, Home, and Usage; Codex
  and Antigravity selection API checks passed and the account/route were restored.


## History Summary

- 2026-09-05 — Desktop Message Account Selection: added and verified credential-safe
  Windows desktop message hooks and background file watcher to switch active CYD
  accounts based on Codex and Antigravity chat activity.

- 2026-09-05 — Replaced PowerShell startup in Stream Deck controls with direct
  windowless HTTP, accelerated CYD command polling, and verified server,
  firmware, physical switching, and security behavior.

- 2026-09-05 — Propagated the configured local timezone through isolated CLI
  profiles and containers, correcting Codex quota reset times; validated all
  accounts on the live deployment.

- 2026-09-04 — Repeatable speaker sound/speech tests; acoustic comparison remains pending. Details retained in the voice project changelog.

- 2026-09-04 — Stream Deck Direct Account Selection (details retained in project changelogs).

- 2026-09-04 — Full-Scale Speaker Volume Control (details retained in prior history and project changelogs).

- 2026-09-04 — Voice Lab Evidence Inbox Rework (details retained in the voice satellite changelog).
<!-- Compressed summaries of older changes go here -->
- 2026-09-04 — Restored and physically verified direct Assist PCM TTS and normal
  wake re-arm after URL-player lockups; retained bounded timeout recovery.
  Details in the voice satellite changelog.
- 2026-09-04 — Native-Rate Lossless Voice Playback Rebuild (details in project changelogs).

- 2026-09-04 — Exhaustive Voice Research Review Queue (details retained in project changelogs).

- Built the purpose-designed ESP32-S3 voice console on 2026-09-04 with live
  status, controls, session diagnostics, and verified embedded deployment; later
  entries describe subsequent refinements.
- Aligned physical and simulator Codex quota bars and disabled accidental card scrolling on 2026-09-03; firmware and 47 server tests passed.
- Diagnosed voice satellite boot time and speaker hardware on 2026-09-03: host
  networking restored native Home Assistant Assist zeroconf reconnection in 7.1s,
  shortened OLED state text, corrected the speaker diagnostic, and identified the
  `2025-V1.4` open `IN-OUT` jumper.

- Added consistent wire-color emojis across the satellite hardware guide on
  2026-09-02, including peripheral tables, cross-checks, and Mermaid flows.

- Reorganized and cross-checked the voice satellite per-device wiring tables
  and whole-system diagrams on 2026-08-30.

- Colocated the canonical Home Assistant wiring guide in the voice-satellite
  project and updated all workspace links on 2026-08-29.

- Disabled CYD Wi-Fi modem sleep and added reason-aware staged reconnect,
  station reinitialization, and guarded restart recovery on 2026-08-27; a
  physical controlled-reboot test confirmed healthy strong-signal recovery.

- Added and deployed a complete high-resolution CYD dashboard favicon/app-icon
  suite with public asset routes and automated coverage on 2026-08-27.

- Added a credential-safe, windowless Windows Stream Deck helper for cycling
  enabled Codex/Antigravity accounts on the physical CYD and dashboard on
  2026-08-27.

- Added dashboard-controlled 180-degree CYD rotation with synchronized
  device/browser routing, persisted orientation, and verified physical/live
  deployment on 2026-08-27.

- Added dashboard-managed Gmail/custom SMTP alerts, private credential storage,
  test/removal controls, and browser-draft preservation on 2026-08-27;
  validated and deployed the protected workflow.

- Supported dual Codex rolling 5-hour and weekly quotas, durable account identity,
  dashboard-to-device app commands, and host-only TLS SMTP alert fallback on
  2026-08-26; validated server tests, simulator, and physical CYD firmware.

- Repaired CYD resistive-touch navigation, handled Codex CLI update prompts in
  scheduled collection, and made WAHA delivery failures durable and visible on
  2026-08-26; validated the firmware, simulator, server tests, and live
  deployment.

- Identified the connected Hosyond 4.0-inch ESP32-32E module as the E32R40T family (ST7796S 320×480 with XPT2046 resistive touch), corrected shared LCD/touch SPI pins, and verified flashing to COM7 on 2026-08-26.

- Upgraded the CYD to its native ST7796 480×320 layout, added capacitive and
  resistive touch autodetection, and corrected dark-mode inversion on
  2026-08-26; later E32R40T identification selected the resistive path and
  corrected the final board-specific pins.

- Backed up the original 4 MB CYD factory firmware, provisioned local Wi-Fi, and completed the first verified Usage Monitor/OpenRouter flash and touch-navigation boot on 2026-08-26.

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

- Speaker output remains quiet and distorted according to the operator even
  at 100% volume. Matched stored-speech and level tests are intended to isolate
  source/stream, channel-format, and output-stage causes; no cause is proven yet.
