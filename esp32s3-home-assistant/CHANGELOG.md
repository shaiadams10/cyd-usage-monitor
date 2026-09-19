# Changelog

## Unreleased

### Changed

- Replaced the brief low-level speaker probe with dashboard sound tests:
  sweep, chime, random melody, soft noise, rising levels, and two embedded
  peak-normalized speech samples, including an identical mono/stereo comparison.
  A bounded nonblocking PSRAM player handles partial writes and output draining;
  tests pause wake detection and the ring, reject active Assist sessions, and
  expose a stop button. Normal direct Assist transport remains unchanged.
- Corrected diagnostic guidance: accepted PCM bytes and GPIO transitions do
  not establish acoustic quality or rule out firmware/format problems. The
  operator still reports quiet, distorted sound at 100% volume.

- Expanded speaker control to a true 0–100% PCM-amplitude range, removed the
  obsolete hidden 0.50 speaker scale and 0.65 Assist-response multiplier, and
  reserve shared USB-rail headroom by switching the LED ring fully off during
  TTS playback. The floating 9 dB MAX98357A gain setting remains the clean
  hardware baseline; 100% now means unattenuated digital full scale.
- Completely reworked Voice Lab as a responsive evidence inbox with clearer
  hierarchy, touch-friendly record cards, at-a-glance totals, and a focused
  selected-record workspace. Successful and failed requests now carry explicit
  green **Successful** and red **Error** flags; review state is independent and
  shown only as a blue dot that disappears once a human label is selected.
  Added an always-visible plain-language guide so color is never the sole cue.
- Restored ESPHome's direct 16 kHz PCM Assist speaker transport after the
  experimental lossless-WAV announcement media player broke spoken
  confirmations and left Voice Assistant in `SPEAKING`. Restored explicit TTS
  stream-start/end handling and matching wake-tone metadata. A 10-second
  emergency guard now records `TTS
  STREAM TIMEOUT RECOVERED`, stops the speaker/session, and re-arms the wake
  word only when the direct stream genuinely fails to close. Recovery status
  distinguishes Home Assistant offline, an intentionally disabled wake word,
  and a genuine recovery failure.
- Replaced the 16 kHz mono speaker probe with a bounded 22.05 kHz dual-mono
  300 Hz–5 kHz logarithmic sweep. The reference test temporarily switches off
  the shared-5-V LED ring, retains GPIO transition evidence, and restores the
  ready indication afterward. Updated the hardware baseline to recommend the
  MAX98357A's unconnected 9 dB gain setting, local 10 µF + 0.1 µF amplifier
  bypass, separate short power branches, under-playback voltage checks, and an
  adequately rated USB source/cable.

- Made the Research Sessions review queue exhaustive across its two evidence
  sources. Every stored Speech-to-Phrase diagnostic is now imported even when
  no matching ESPHome log row reached the browser, so empty-transcript,
  no-audio-after-VAD, fuzzy-match, high-cost, and other decoder failures remain
  visible with their saved WAV, signal metrics, candidates, timing, and review
  controls. Device-only failures that stop before recognition remain visible
  with their device outcome and timing evidence, and a late device record
  replaces its temporary diagnostic-only row without creating a duplicate.

- Replaced the visible ESPHome entity-table dashboard with a purpose-built,
  responsive voice console. Added a plain-language animated assistant state,
  touch-friendly speaker volume with step and test controls, custom wake-word
  and acknowledgement switches, a one-breath buffer control, latest
  conversation cards, compact health metrics, and confirmed recovery actions.
  The lightweight controls use ESPHome's local REST routes, while the hidden
  stock entity/log surface remains active for telemetry, session capture, and
  the existing 12-second recovery fail-open.

- Kept the MAX98357A on native Philips I2S with explicit 16 kHz, 16-bit mono
  source metadata and restored the speaker diagnostic to a slider-controlled
  250 ms tone that fits within the 300 ms ring buffer. This removed an
  accidental full-volume override and long blocking feed; the flashed device
  accepted all 8,000 bytes, showed active BCLK/LRC/DIN transitions, logged no
  I2S/queue/buffer failure, and reduced the observed test loop stall from 729 ms
  to 148 ms. Identified the fitted dual-USB-C N16R8 board as the
  photographed `2025-V1.4` DevKitC-style variant and confirmed that its
  front-side `IN-OUT` pads are open, isolating USB VBUS from `5Vin`; the
  back-side `USB-OTG` pads are also open but are not required for COM-powered
  5 V output. Documented the measured 1.3–1.98 V floating `5Vin`, healthy 3.3 V
  rails, exact jumper choice, safe USB/external supply constraints, and the
  MAX98357A-supported no-solder alternative of powering `VIN` from 3.3 V at
  reduced output. The amplifier cannot operate from the measured floating
  voltage.

- Moved the dashboard loading mask into ESPHome's small `css_include` resource
  so it blocks the stock UI before the large JavaScript bundle downloads, then
  removes the stylesheet only after the custom shell is ready. Retained a
  12-second fail-open to expose ESPHome's stock recovery UI if custom
  enhancement fails after download.

- Deployed and smoke-tested Home Assistant's native host-network topology after
  adding narrow UFW allowances for LAN TCP 8123, LAN mDNS, and bridged
  Speech-to-Phrase access to host TCP 8123. Preserved the existing Wyoming
  config-entry hostnames through loopback mappings to their published ports;
  the active Speech-to-Phrase/Piper pipeline remained available. After a later
  physical restart reproduced a 21-second connection, reconfigured the ESPHome
  config entry from its retained numeric address to
  `esp32s3-home-assistant.local`. A controlled restart then connected in 7.1
  seconds, including Home Assistant's intentional five-second expected-reboot
  cooldown, instead of the original bridge-network trace's 33.6 seconds.

- Reworked the 128×64 OLED into a bounded, state-specific two-line layout,
  removed the on-device Wi-Fi RSSI footer, and shortened the last-heard footer
  so long status/transcript text no longer renders beyond the panel edges.

- Added an early branded dashboard bootstrap screen and reveal-on-ready handoff
  so the stock ESPHome entity layout no longer flashes underneath the custom
  operations console while its shadow-DOM enhancements attach.

- Documented a measured startup trace that isolates the long readiness wait to
  Home Assistant's ESPHome API reconnect backoff when its bridged container
  cannot receive LAN mDNS announcements, plus a voltage/resistance checklist
  for a silent MAX98357A after the ESP32 I2S probe succeeds.

- Added color emojis to the Suggested Wire columns across all peripheral
  connection tables (SSD1306 OLED, INMP441 microphone, MAX98357A amplifier,
  box speaker, and 12-pixel LED ring) in `HARDWARE.md` to visually match the
  pinout cross-check table and Mermaid flowcharts.

- Reorganized `HARDWARE.md` into one complete connection table per device and
  corrected the whole-system tables and diagrams to show the confirmed
  MAX98357A wiring: 5 V to `VIN`, 3.3 V to `SD/SD_MODE`, and ground to both
  `GND` and `GAIN`. Added explicit power-rail, bridge-tied speaker, microphone,
  and LED-ring safety notes so every physical connection can be checked without
  inferring omitted module pins.

- Moved the complete wiring, wire-color, pinout, and LED-ring connection guide
  from the workspace-level `docs/` directory to this project as `HARDWARE.md`,
  and updated the project and workspace links so the hardware documentation is
  self-contained with the firmware it describes.

- Matched the carrier to the supplied AliExpress component listings. Replaced
  the incorrect generic 1x6 INMP441 socket with the purchased HZWDONE 14 mm
  round 2x3 footprint, exact labeled pad arrangement, body outline, and
  courtyard; moved it to a collision-free edge position with intentional
  acoustic overhang. Recorded the confirmed MAX98357A, SSD1306, 25 x 35 mm
  speaker, and 52 mm 12-pixel ring dimensions while keeping fabrication gated
  on ordered SKU choices, missing heights, and the exact ESP32-S3 board.

- Audited and repaired the tscircuit carrier after reproducing the previous
  errors. Corrected the ESP32-S3-DevKitC-1 J1/J3 pin map (the old source put 5 V
  on a physical ground pin), corrected the official 22.86 mm header-row
  spacing, removed the electrically floating duplicate speaker terminal,
  replaced the impossible 470 uF 0805 footprint with a radial electrolytic,
  and isolated optional external 5 V to the peripheral rail through a manual
  source selector. Added deliberate schematic sections/sheet placement,
  collision-free PCB placement, wider power/ground routing, a DevKit body
  outline, exact-version project-local npm tooling, a lockfile, a repeatable
  validation command, and failure-aware local-only export tooling. Regenerated
  Gerber/BOM/PnP, KiCad, SVG, and GLB artifacts; fabrication and enclosure work
  now explicitly require physical module measurements first.

### Added

- Added a code-defined PCB carrier board and breakout shield workspace in `circuit/`
  using TSCircuit (TypeScript & React JSX). Integrates the ESP32-S3 DevKitC-1 N16R8,
  INMP441 I2S microphone, MAX98357A I2S DAC amplifier, SSD1306 OLED, 12-pixel WS2812
  LED ring with 330 Ω protection, 470 µF bulk power decoupling, and an external 5V
  terminal. Provides interactive 3D/2D browser development (`npm run dev`) and automated
  exports for Gerber ZIPs, KiCad project archives, vector SVGs, and 3D GLB models.

- Added a report-before-prune voice research workflow. Dashboard correctness
  tags, expected speech, notes, and device-session telemetry now synchronize to
  the private diagnostics service. When the raw record-count or storage limit
  is exceeded, it atomically preserves the complete batch as a content-addressed
  deterministic report before removing covered audio. The dashboard tracks raw
  capacity, report totals, pending/analyzed state, review coverage, quick
  findings, and saved Codex analysis summaries.

- Added unique voice-session IDs, explicit custom/generic routing outcomes, and
  structured end-of-session records with transcript, reply, command/result,
  error, replay settings, radio evidence, and per-stage timing.
- Added a dedicated Session History dashboard page with compact expandable
  rows, local retention of the newest 200 sessions, human correctness/failure
  labels, expected-speech and review-note fields, and JSON/CSV research export.
  Expanded rows explain normalized transcript polarity, routing, capture, and
  the exact returned `on`/`off` token that selected the action. Added a
  credential-free Home Assistant Recorder SQLite exporter for longer-term
  session datasets.
- Added a reproducible diagnostic Speech-to-Phrase image that retains the exact
  post-VAD WAV, Kaldi N-best candidates, acoustic/grammar costs, score margin,
  raw and fuzzy text/cost, word timing/lattice confidence where available, and
  signal/boundary quality metrics. Added a private diagnostics API,
  bounded 200-record/256-MiB raw retention, optional WAV playback, automatic
  timestamp/transcript session correlation, and dashboard/CSV presentation.
- Added a local `buffered_microphone` ESPHome platform that keeps one second of
  raw INMP441 history in PSRAM and replays a 260 ms pre-wake slice plus the
  exact handoff interval into each locally triggered Assist command pipeline.
- Added a status-owned 12-pixel GRB WS2812-compatible LED ring on GPIO4: solid
  green when voice is ready, rotating yellow while a request owns the pipeline,
  pulsing red for offline/error, and dim amber when wake detection is disabled.
  Manual dashboard and Home Assistant light control is deliberately disabled.
- Added explicit interaction-availability/readiness entities plus separate
  wake-to-pipeline, replay, speech-detection, capture, STT, wake-to-action, and
  total-busy-time diagnostics in Home Assistant and the device dashboard.
- Reproducible local microWakeWord training/export tooling for the custom
  **Hey Burden** phrase, with generated corpora/features/models kept outside
  version control and only the ignored deployment artifact staged locally.
- Clean-room ESPHome/ESP-IDF firmware for the N16R8 ESP32-S3.
- Existing OLED, INMP441, MAX98357A, and BOOT-button pin mapping.
- Continuous encrypted Assist audio with local server-side openWakeWord
  detection and the standard Home Assistant Assist API.
- Immediate local listening earcon and OLED state feedback.
- Persistent dashboard speaker-volume control (10–100%, default 50%) applied
  consistently to wake acknowledgement, test playback, and streamed TTS.
- Minimal local ESPHome v3 diagnostics dashboard with live logs and recovery
  controls.
- Scrollable 300-row dashboard log with paused-history status and a Back to
  live control.
- Heap, PSRAM, fragmentation, loop-time, reset, Wi-Fi, and voice lifecycle
  diagnostics.
- UART0 logging through the board's CH343 USB bridge, matching COM4 and the
  dashboard log stream.

### Changed

- Reworked the device dashboard using the supplied operations-console sample
  as visual direction: a persistent desktop status rail, oversized readiness
  hero, square high-contrast surfaces, and a compact responsive top navigation.
  Replaced Research Sessions accordions with a master-detail queue that keeps
  one interaction selected while preserving all decoder evidence, reviews,
  reports, exports, and refresh-stable routes.
- Redesigned Overview around a live readiness hero and structured device
  sections, and rebuilt Research Sessions as a clearer evidence workspace with
  one selected record at a time and grouped conversation, recognition, acoustic,
  timing, and review panels. Removed all time-based acoustic expiry; retained
  research reports now live independently from the rolling raw-audio folder.

- Made Overview and Session History distinct `#overview`/`#sessions` routes so
  navigation survives refresh. Made dashboard bundling read the maintained
  enhancement explicitly as UTF-8 and replaced fragile non-ASCII separators,
  eliminating the mojibake visible in generated firmware.

- Made the wake acknowledgement enabled by default and replaced the former
  delayed/cancelled tone with a quiet 35 ms confirmation at listening start.
- Split the status ring into a three-pixel rotating yellow listening gradient
  and a full-ring yellow breathing effect after speech ends while STT, intent,
  action, and response playback are busy.
- Added both natural verb orders (`turn lights off` / `turn off lights` and
  on/switch equivalents) to the constrained Bedroom grammar, deployed it,
  reloaded Home Assistant's conversation/intent engines, retrained
  Speech-to-Phrase, and verified `turn off lights` and `turn on lights` return
  the explicit `Lights off.` / `Lights on.` custom responses.
- Guarded speech-capture timing when VAD ends without a corresponding start,
  preventing an unsigned-uptime value such as 333,700 ms from appearing as a
  real utterance duration.
- Separated wake-detection and pipeline-start timestamps, added replay-byte and
  replay-duration diagnostics, exposed a 180–340 ms persistent dashboard trim,
  made the wake tone opt-in after reboot, and delayed it to 500 ms so restored
  one-breath audio can reach VAD first.
- Identified the intermittent 15-second one-breath delay as a no-speech VAD
  timeout after the pre-roll was reduced to 80 ms. Restored 260 ms and raised
  the supported floor to 180 ms; successful recorded requests complete in
  about 2.8 seconds.
- Replaced Okay Nabu with the newly trained **Hey Burden** quantized streaming
  model on the ESP32. Independent testing selected a conservative 0.87 cutoff
  (zero measured false accepts and 11.7% false rejection); wake detection stays
  instant and on-device rather than adding a server wake round trip.
- Added analog-clipping headroom for the MAX98357A module's physically grounded
  GAIN pin (+12 dB): capped the dashboard at 60%, scaled requested amplitude by
  0.50, and reduced the Assist response multiplier to 0.65. Switched the active
  Home Assistant Piper voice from `en_US-amy-low` to
  `en_US-lessac-medium` while leaving the server wake setting untouched.
- Compiled and OTA-flashed configuration hash `0x127cee52`. The live device
  loaded Hey Burden at cutoff 0.87, allocated both microWakeWord tensor arenas,
  accepted the full 8,000-byte 16 kHz mono speaker probe, and observed active
  BCLK/LRC/DIN pad transitions without an I2S error.
- Made the dashboard **Test Speaker** action single-run so repeated clicks
  cannot restart the I2S task mid-tone and create torn audio or an ISR
  event-queue overflow.
- Restored the complete spoken-response format to ESPHome Assist's native
  16 kHz, signed 16-bit mono PCM and explicitly reapplied it before every Piper
  response. Raw Assist audio has no embedded stream metadata, so the previous
  44.1 kHz stereo tone metadata corrupted the following speech.
- Replaced torn left-justified/MSB output with the MAX98357A's native Philips
  I2S timing and removed the incompatible forced-stereo negotiation patch.
  Local tones now share the exact Assist response format while retaining a
  both-slot hardware mask for amplifier channel-selection tolerance.
- Fixed a false-positive speaker diagnostic: the generated 44.1 kHz stereo
  tone was previously handed to raw `speaker.play` without stream metadata, so
  ESPHome interpreted it as 16 kHz mono. Both local tones now declare their
  exact stream format before I2S startup and log accepted/requested PCM bytes.
- Added live GPIO-pad transition counting for speaker BCLK, LRC, and DIN during
  the diagnostic tone, separating an ESP/I2S signal failure from faults beyond
  the ESP32 header pins.
- Replaced the long-lived server-side openWakeWord stage with ESPHome's
  maintained on-device `okay_nabu` microWakeWord model. Every match now opens a
  fresh Home Assistant command pipeline, avoiding the current expired TTS-token
  failure after an idle server-wake session and removing a network wake round
  trip from one-breath commands.
- Raised the INMP441 command and wake sources to 4x gain, enabled level-2 noise
  suppression and 31 dBFS automatic gain control, and retained local VAD for
  better room-scale pickup without widening the supported command space.
- Converted dashboard volume percentages to true amplitude/dB values, matched
  the physically proven 44.1 kHz MSB/stereo output, and replaced the 45 ms
  speaker check with a distinct 250 ms diagnostic tone.
- Tightened Speech-to-Phrase to plural light commands and the distinct
  `lights up/out` alternatives, removing acoustically overlapping singular and
  duplicated hypotheses that competed over `on` versus `off`.
- Forced the I2S speaker path to stereo and duplicated mono into both slots,
  matching the last physically audible driver instead of relying on the
  amplifier module's undocumented L/R-select strap.
- Added concise `voice_trace` lifecycle logs and dashboard fields for exact
  recognition text, exact assistant reply, matched command, action result, and
  end-to-end/recognition timing.
- Completed the focused-local cutover from Whisper to digest-pinned
  Speech-to-Phrase with a versioned lights-only grammar and a repeatable
  add-command/retrain/test procedure. Selected it in the preferred Home
  Assistant pipeline, verified exact `lights on`/`lights off` intent responses,
  and stopped the retired Whisper service.
- Changed the live Bedroom intents from an area target to the two explicit
  light entities and made successful actions report back to the ESP dashboard.
- Restored the fitted amplifier's physically verified MSB bus format after
  standard I2S produced clean driver logs but no audible output on this unit.
  Replaced the near-full-scale volume curve with a square-root curve, lowered
  acknowledgement PCM peak to 17,000, and added Piper stream headroom to
  reduce high-volume tearing.
- Biased Faster Whisper only toward `light(s) on/off`, enabled beam search, and
  shortened the silence endpoint from 500 ms to 300 ms. Expanded the deployed
  Bedroom grammar with singular and plural forms so `light on` cannot fall
  through to Home Assistant's generic area matcher.
- Connected the existing Wyoming openWakeWord service to Home Assistant,
  selected `okay_nabu` in the active pipeline, and moved wake detection to the
  same continuous audio stream used for command capture. This removes the
  on-device wake-to-STT subscription boundary that clipped one-breath commands.
- Added adaptive wake feedback: post-wake VAD cancels the delayed earcon for
  one-breath speech, while a pause after the wake word still receives audible
  confirmation before the command.
- Added guarded continuous-listening recovery after manual-button and stopped
  pipeline paths, and exposed `WAITING FOR WAKE WORD` as the steady dashboard
  state.
- Removed Whisper's device-name prompt after Assist debug history showed
  15-second silent captures hallucinating `Left Lamp`, `Right Lamp`, and
  `Right Turn`; the pipeline now relies on audio plus explicit room intents.
- Removed individual lamp exposure while retaining Bedroom-only `lights on/off`
  intents, preventing a hallucinated lamp name from operating one lamp.
- Added clipped wake-tail variants observed in real runs, including
  `okay now ... lights on/off`, to the Bedroom intent grammar.
- Shortened wake feedback from 90 ms to 45 ms, made its oscillator
  phase-continuous, and added attack/release fades to eliminate tearing at high
  volume while reducing contamination of immediate command audio.
- Recalibrated dashboard volume around ESPHome's -49..0 dB software curve with
  a fourth-root mapping and 2 dB headroom; added a persistent Wake Sound toggle
  so users can disable acoustic feedback for maximum one-breath accuracy.

- Grouped and ordered the v3 dashboard into Voice Assistant, Connection,
  Device Health, and Recovery cards while hiding noisy low-level diagnostics.
- Renamed the transcript rows to `You Said`, `Assistant Said`, and `Last Error`,
  and updated the OLED heading to match the active `Okay Nabu` model.
- Moved wake detector start/stop handling from generic API client hooks to the
  voice-assistant connection hooks so a terminal log client cannot change the
  listening state.
- Raised the listening earcon's PCM source level while preserving the enforced
  30% speaker master gain, and added a matching dashboard speaker-test button.
- Serialized the listening earcon correctly around ESPHome's asynchronous I2S
  speaker startup: stop wake inference, start the speaker, wait until it is
  running, enqueue the PCM tone, drain it, and only then start command capture.
  Added a reproducible ESPHome 2026.7.0 dependency workaround for its duplicate
  I2S initialization race; this eliminates the dashboard test's `Parent bus is
  busy`/empty-tone failure.
- Re-arm wake detection from pipeline end only after both the Assist state
  machine and streamed Piper audio finish.
- Added the apostrophe to both OLED fonts so contractions in STT/TTS text do
  not flood the logger during the 250 ms display refresh.
- Tuned Faster Whisper with VAD filtering, a 500 ms silence endpoint, and a
  concise Bedroom device-name prompt that avoids encouraging phrase repeats.
- Start the Assist microphone immediately after the on-device wake match and
  pass the detected wake phrase into the pipeline, enabling natural one-breath
  commands such as `Okay Nabu, lights off`.
- Cycle three short tonal wake acknowledgements without blocking command
  capture or feeding spoken acknowledgement words back into STT.
- Limit the deployed Home Assistant Assist exposure to the two Bedroom lamps,
  disable automatic exposure, and add Bedroom-only light intents that also
  handle duplicated Whisper transcripts such as `lights off lights off`.
- Added comma and ampersand OLED glyphs and removed redundant wake-detector
  starts so display refresh and speaker testing no longer create log spam.

### Removed from the new design

- Long-lived server-side wake detection from the active runtime; the ESP now
  uses supported on-device microWakeWord and creates a fresh Assist request for
  each command.
- Custom raw Wyoming sockets in firmware; streaming uses ESPHome's encrypted
  Assist API and Home Assistant's supported Wyoming integration.
- Custom AsyncWebServer/WebSocket dashboard protocol and browser command mocks.
- Direct dashboard home-control commands and on-device OTA uploads.
- Custom Whisper buffers, fallback wake matching, and hand-built VAD state.

### Validation

- OTA-flashed configuration hash `0xf47cbeba`, verified local Okay Nabu and VAD
  inference, encrypted Home Assistant connection, 216+ KB free heap, and a
  clean 44.1 kHz Test Speaker start/buffer/stop cycle without an I2S error.
- Deployed the narrowed sentence grammar, verified its exact checksum on the
  Home Assistant host, and observed Speech-to-Phrase retrain successfully.
- Built and flashed the clean-room image to the physical ESP32-S3 over COM4.
- Verified normal boot, 16 MB flash, 8 MB PSRAM, the OLED at `0x3C`, I2S
  microphone/speaker initialization, Wi-Fi, encrypted API access, continuous
  Assist streaming, and an HTTP 200 diagnostics dashboard response.
- Added the existing Docker-network Faster Whisper and Piper services to Home
  Assistant through Wyoming Protocol and selected them as the English STT/TTS
  providers for the Home Assistant Assist pipeline.
- Observed a physical wake-word activation reach STT, intent processing, and
  Piper TTS, and verified the dashboard speaker test starts and stops without
  an I2S error before wake detection resumes.
- OTA-flashed the 50%-volume one-breath build, verified a clean speaker test and
  dashboard slider, and tested the duplicated light command through Assist.
- Flashed configuration hash `0xac464a53`, verified the active Assist pipeline
  advertises `wake_word.openwakeword` with `okay_nabu`, observed continuous
  microphone streaming, and ran speaker tests at 40% and 75% with standard-I2S
  start/buffer/stop logs and no speaker error.
