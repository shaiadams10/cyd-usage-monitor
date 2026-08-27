# ESP32-S3 Home Assistant Voice Satellite

Clean-room v2 firmware for the ESP32-S3-WROOM-1 N16R8 voice satellite. It uses
ESPHome's ESP-IDF voice stack, on-device microWakeWord detection, a fresh Home
Assistant Assist command pipeline after every wake, and a deliberately small
diagnostics dashboard.

The previous custom Arduino/Wyoming implementation is preserved next to this
directory as `esp32s3-home-assistant-legacy-2026-08-22/` for rollback and
hardware-reference purposes. Do not copy its networking or state-machine code
into this project.

## Hardware

| Device | Signal | ESP32-S3 pin |
|---|---|---:|
| SSD1306 OLED | SDA | GPIO6 |
| SSD1306 OLED | SCL | GPIO5 |
| WS2812/NeoPixel LED ring | DI/DIN | GPIO4 |
| MAX98357A | BCLK | GPIO17 |
| MAX98357A | LRC/WS | GPIO18 |
| MAX98357A | DIN | GPIO8 |
| MAX98357A | GAIN | GND (+12 dB) |
| INMP441 | SCK | GPIO15 |
| INMP441 | WS | GPIO16 |
| INMP441 | SD | GPIO7 |
| BOOT button | input | GPIO0 |

The optional code-defined carrier PCB is in `circuit/`. Its tscircuit CLI and
TypeScript compiler are installed only in that directory and pinned by its npm
lockfile. The corrected source matches the official DevKitC-1 header map,
isolates optional external 5 V to the amplifier/ring rail, and passes netlist,
schematic-placement, PCB-placement, build, and copper-short checks. It remains
blocked from fabrication until the exact breakout-board bodies, pin orders,
overhangs, and heights are measured; see `circuit/README.md` before ordering or
starting an enclosure.

Speaker software volume defaults to **50%**, is restored after reboot, and is
applied consistently to the listening acknowledgement, speaker test, and every
streamed response.

## Supported dashboard capabilities

Open `http://<device-ip>/`. The ESPHome v3 dashboard is stored on the device and
has no cloud asset dependency. It intentionally exposes only:

- a 300-row, vertically scrollable ESPHome log with automatic live following;
  scrolling upward pauses following and **Back to live** resumes it;
- a focused **Voice Assistant** card with state, wake word, exact transcript,
  exact reply, matched command, action result, timing, error, and wake
  enablement;
- compact **Connection**, **Device Health**, and **Recovery** cards;
- essential connectivity, reset, uptime, heap, PSRAM, and loop-time evidence;
- wake-word enable/disable;
- an enabled-by-default **Wake Sound** toggle controlling the immediate 35 ms
  low-energy listening acknowledgement;
- a persistent **One-Breath Pre-roll** control from 180–340 ms, defaulting to
  260 ms, for real-room trim calibration without reflashing;
- a persistent 10–60% **Speaker Volume** slider, defaulting to 50%;
- explicit **Interaction Availability** and **Ready for Voice** entities;
- separate wake-to-pipeline, replay, speech detection, speech capture, STT,
  wake-to-action, and total-busy-time diagnostics;
- a separate **Research Sessions** tab that packages up to 200 wake-to-ready
  interactions into a master-detail review queue, keeps exactly one evidence
  record selected, synchronizes human review labels and notes to the private
  diagnostics service, and supports JSON/CSV export;
- a distinct 250 ms speaker test that is easy to hear and exercises the same
  physical output path as wake feedback and TTS;
- normal restart and safe-mode restart.

It does not implement lamp controls, simulated voice commands, arbitrary OLED
messages, firmware upload, or a second custom WebSocket log
protocol. Home controls belong in Home Assistant.

The LED ring is status-owned and intentionally absent from both Home Assistant
and the local dashboard, so a manual color cannot hide whether speech will be
accepted.

## First build

1. Copy `secrets.yaml.example` to the ignored `secrets.yaml` file.
2. Fill the real Wi-Fi values, an API encryption key, and an OTA password.
3. Install ESPHome in an isolated environment and compile:

```powershell
uv venv .venv --python 3.13
uv pip install --python .venv/Scripts/python.exe "esphome==2026.7.0"
.venv/Scripts/esphome.exe config device.yaml
.venv/Scripts/esphome.exe compile device.yaml
```

ESPHome 2026.7.0 has a speaker-task startup race on this configuration. Use the
checked-in flash wrapper, which applies the narrowly scoped workaround and
regenerates the pinned, offline-capable dashboard bundle before building:

```powershell
./scripts/flash.ps1 -Device COM4
./scripts/flash.ps1 -Device esp32s3-home-assistant.local
```

On the original operator workstation, the existing ignored Arduino Wi-Fi
configuration can instead be migrated without printing any secret values:

```powershell
./scripts/migrate-legacy-secrets.ps1
```

Flash over USB only after configuration validation:

```powershell
.venv/Scripts/esphome.exe run device.yaml --device COM4
```

## Debugging

The quickest debugging path is the dashboard's **Debug Log**. It follows new
rows until you scroll upward; press **Back to live** to jump to the newest row
and resume automatic scrolling. Equivalent
commands are:

```powershell
.venv/Scripts/esphome.exe logs device.yaml --device COM4
.venv/Scripts/esphome.exe logs device.yaml --device esp32s3-home-assistant.local
```

When reporting a failure, capture the voice state, last error, reset reason,
free heap, free PSRAM, and the log lines surrounding the event.
Safe mode deliberately disables most components and is only for recovering a
device that repeatedly crashes during boot.

## What happens after “Hey Burden”

The device is a complete Home Assistant Assist satellite, not only a wake-word
tester. ESPHome microWakeWord detects **Hey Burden** locally, then immediately
starts a fresh encrypted Home Assistant STT/intent/TTS request. This avoids the
stale TTS-token failure observed after a server-side wake pipeline had remained
open for several minutes and removes the server wake round trip.

Both interaction styles are supported. A local buffered-microphone component
keeps one second of physical INMP441 history in PSRAM. At the exact Hey Burden
detection callback it marks the stream, then gives Voice Assistant the final
260 ms before that marker plus every complete sample captured during the
handoff. This preserves the first command syllable in **“Hey Burden, lights
off”** without moving wake detection to the server. The raw microphone remains
the wake detector's source; only Voice Assistant receives replayed samples, so
pre-roll cannot retrigger microWakeWord.

The OLED and ring react immediately, and the acoustic Wake Sound now defaults
on. It plays a quiet 35 ms acknowledgement as soon as Voice Assistant enters
listening. The microphone history continues during playback, and the short,
low-energy tone is designed for the configured noise suppression to reject. The
toggle can still disable it for controlled capture comparisons.

For this installation, individual entity exposure is disabled and automatic
exposure of new entities is off. Bedroom-only custom sentences make **“lights
on”** and **“lights off”** directly target both lamps without allowing an
uncertain transcript such as `Right Lamp` to operate only one lamp. Successful
intent scripts report the matched command and concrete action back to the ESP
dashboard.

The target pipeline is **Focused Local**: microWakeWord detects Hey Burden on the
ESP, Speech-to-Phrase recognizes only the supported command grammar, Home
Assistant executes the explicit intent, and Piper optionally speaks the reply.
Whisper and server-side openWakeWord are not fallbacks in this design. See
`server/README.md` for the command-addition and retraining procedure.

Live recorder evidence showed two distinct behaviors: a successful one-breath
request completed in about 2.8 seconds, while missed speech detection held the
pipeline open for roughly 15 seconds. In those slow cases the restored pre-roll
had been manually reduced to 80 ms. The supported floor is now 180 ms and the
device is returned to 260 ms; the timing entities identify whether any future
delay is command capture, Speech-to-Phrase, intent execution, or TTS.

The acknowledgement waits for the asynchronous I2S speaker task before queuing
PCM. Turn **Wake Sound** off to compare a completely silent wake transition.
Local wake detection re-arms after Piper finishes; a guarded recovery script
also restores it after a manual-button request or stopped pipeline path.

The deployed Speech-to-Phrase recognizer is trained from a finite Bedroom
grammar. It accepts `lights on/off`, both verb orders (`turn lights off` and
`turn off lights`, likewise for on/switch), plus the more
acoustically distinct fallbacks `lights up/out`. Removing singular and repeated
variants reduces the number of similar hypotheses competing over the short
final word. It cannot invent a lamp or room name outside that grammar. The active Home Assistant pipeline uses
`stt.speech_to_phrase`; the retired Whisper container is stopped and is not a
fallback.

ESPHome's software volume spans roughly -49 to 0 dB rather than scaling its
control value linearly. The firmware converts the displayed percentage to true
amplitude/dB, caps the dashboard at 60%, and applies a 0.50 amplitude scale.
The default 50% position is therefore about -12 dB before the Assist pipeline's
additional 0.65 response multiplier. This headroom is intentional because the
fitted MAX98357A GAIN pin is grounded for +12 dB analog gain. Local tones and
streamed Assist responses use the same
16 kHz, signed 16-bit mono PCM format. Because ESPHome's Assist audio messages
carry raw bytes without stream metadata, the firmware restores that format
before every tone and every deferred Piper speaker start. This prevents a
local tone from leaving stale sample-rate/channel metadata that tears, slows,
or silences the following spoken response.

The MAX98357A runs in its native Philips-I2S mode with the required one-bit
data delay. The retired MSB setting was left-justified; it became audible after
a USB power cycle but produced the reported torn/distorted output. The earlier
standard-I2S silence result was invalid because the diagnostic buffer itself
had been mislabeled.

The test path logs accepted versus requested PCM bytes, making a successful
test meaningful beyond a start/stop lifecycle log.
The same test samples the physical GPIO17, GPIO18, and GPIO8 pads during
playback and logs BCLK, LRC, and DIN transition counts. Nonzero counts on all
three isolate continued silence to wiring, amplifier power/shutdown, the
MAX98357A module, or the speaker beyond the ESP32 pins.
The configured stereo slot mask lets the ESP-IDF mono transmitter reach either
amplifier channel selection while Home Assistant retains its native mono Assist
stream. The incompatible forced-stereo negotiation patch was removed. The
acknowledgement also uses continuous phase plus attack/release fades.

## Wake-word status

The firmware uses the locally trained **Hey Burden** streaming microWakeWord
model in `wake-word-training/artifacts/`. It runs continuously on the ESP32, so
wake response does not depend on a server round trip. The independent quantized
streaming test selected a conservative 0.87 probability cutoff: zero false
accepts were observed at that point, with an 11.7% false-rejection rate; 0.86
improved recall slightly but measured two false accepts per hour in that test.

## LED ring wiring

The photographed ring has **12 addressable 5050 pixels**. Firmware configures it
as a 5 V WS2812/NeoPixel-compatible **GRB** ring. Connect the input pad, not the
output pad:

| Ring pad | ESP32-S3 | Connection |
|---|---|---|
| `5V`, `VCC`, or `+5V` | `5V/VBUS` | Red power wire |
| `GND`, `G`, or `-` | `GND` | Black common-ground wire |
| `DI`, `DIN`, `IN`, or `DATA` | `GPIO4` | Yellow/white data wire; do not use `DO` |

Never power the ring from 3.3 V. The status patterns are deliberately capped at
low brightness, but a 12-pixel ring can still approach 0.72 A at unrestricted
full white. If it will be used at higher brightness, use a regulated external
5 V supply and join its ground to ESP32 ground. Put a 330–470 Ω resistor in
series with GPIO4 near the ring and a 470–1000 µF bulk capacitor across ring
5 V/GND. If 3.3 V GPIO data is unreliable while the ring is powered at 5 V,
add a 74AHCT125/74HCT14 5 V logic-level shifter.

The ring is the primary “may I speak?” signal:

| Ring state | Meaning |
|---|---|
| Solid green | Ready; say **Hey Burden** and the command |
| Three-pixel yellow gradient rotating | Listening/capturing the current command |
| Full yellow ring breathing | Speech ended; transcribing, routing, acting, or speaking |
| Pulsing red | Home Assistant offline or the last request failed |
| Dim amber | Wake word was deliberately disabled |

## Session history and improvement data

Every wake receives a unique session ID. At completion the device emits one
structured record containing exact STT, reply, matched command, action result,
error, custom-versus-generic routing outcome, replay duration/bytes, pre-roll,
Wi-Fi signal, and all stage timings. **Overview** and **Research Sessions** use
distinct `#overview` and `#sessions` URLs, so refreshing preserves the selected
page. The reference-inspired operations console uses a persistent desktop rail,
an oversized live-readiness state, sharp high-contrast panels, and a responsive
top navigation on narrow screens. Research Sessions stores the newest 200
device records locally in that browser as a compact queue with exactly one
selected detail workspace at a time. The selected workspace separates
conversation outcome, recognition decision, acoustic evidence, request timeline,
and human-review fields. It shows the normalized transcript, the
exact `on`/`off` token that selected the action, custom-versus-generic routing,
capture evidence, timings, and labels for correct, wrong recognition, wrong
action, or missed audio. A reviewer can also record what was actually spoken
and the expected result, creating useful expected-versus-recognized pairs.
Export JSON or CSV to use those human-reviewed records for later grammar,
threshold, and latency analysis.

The derived Speech-to-Phrase image now preserves the decoder evidence that the
Wyoming transcript response cannot carry. For every new recognition it stores
the exact post-VAD 16 kHz WAV, three Kaldi lattice candidates, separate acoustic
and grammar costs, best-versus-second score margin, raw best path, fuzzy result
and fuzzy cost, final transcript, word timing and lattice confidence when
available, plus peak/RMS, clipping, DC offset, estimated noise/SNR, leading and
trailing silence, and possible active-tail truncation. The private diagnostics
service exposes these records and their WAV player, accepts bounded review
metadata from the dashboard, and tracks deterministic research reports. Enter
its private URL in **Acoustic diagnostics service** once per browser; the
setting survives refresh.

Raw room-audio retention has no time expiry. It rolls over only after exceeding
200 records or 256 MiB. Before any covered WAV/JSON pair is removed, the service
atomically writes one immutable `research-*.json` report containing the complete
decoder records, synchronized correctness tags and notes, device-session
telemetry, review coverage, confusion pairs, acoustic issue counts, and
rule-based recommendations. Reports persist separately under
`server/data/speech-to-phrase/reports/`; the dashboard shows archive pressure,
total/pending/analyzed report counts, quick findings, and a saved analysis
summary. Each complete report can be downloaded as JSON for a later Codex
analysis. The committed API binds to loopback and must only be exposed on a
trusted private LAN. Delete both ignored diagnostics and reports directories
only when deliberately erasing the research archive. Kaldi costs and lattice
confidence are comparative decoder evidence, not calibrated human certainty.

Home Assistant Recorder independently retains the underlying entities. To
package its longer-lived SQLite history without credentials or network access:

```powershell
python scripts/export-voice-sessions.py `
  --db C:\path\to\home-assistant_v2.db `
  --output voice-sessions.json
```

The source corpus and generated features remain outside the repository. To
reproduce the environment, features, training, or export, use the documented
PowerShell launchers in `wake-word-training/`. A server-oriented openWakeWord
TFLite file is not compatible with this ESPHome microWakeWord path.

## Crisp-audio boundary

Firmware now guarantees native Philips I2S, 16 kHz signed 16-bit mono stream
metadata, complete PCM delivery, and conservative digital headroom. The live
speaker probe accepted all 8,000 diagnostic bytes and observed transitions on
BCLK, LRC, and DIN. If speech still tears above the new software ceiling, the
remaining correction is physical: reduce the MAX98357A gain strap from the
current +12 dB, place the datasheet-recommended 10 µF and 0.1 µF bypass
capacitors directly across amplifier VIN/GND, and add local bulk capacitance
when the USB/power leads are long. Also confirm a 4–8 Ω speaker with adequate
power rating. Those changes prevent amplifier, supply, or speaker clipping that
software cannot repair after the PCM leaves the ESP32.

## TSCircuit PCB Carrier Board

A code-defined hardware carrier board and breakout shield is maintained in `circuit/` using [TSCircuit](https://github.com/tscircuit/tscircuit) (TypeScript & React JSX).

### Capabilities:
- **Interactive 3D / 2D Dev Server**: Run `npm run dev` in `circuit/` to view the 3D board, 2D PCB traces, and schematic in your browser with hot reload.
- **Manufacturing Exports**: Run `npm run export:all` to produce Gerber ZIPs for JLCPCB/PCBWay, KiCad project archives, vector SVGs, and 3D GLB models in `circuit/dist/`.

```powershell
cd esp32s3-home-assistant/circuit
npm run dev           # Interactive 3D & schematic preview
npm run export:all    # Export Gerbers, KiCad, SVG, and 3D models
```

## Architecture rule

The ESP32 owns wake detection, far-field microphone gain, and adaptive local
feedback. Home Assistant owns constrained STT, intent execution, and TTS. The
microphone source uses 4x gain with level-2 noise suppression and 31 dBFS
automatic gain control for room reach while retaining the wake model's VAD.
All processing remains on the local network; the dashboard observes this
pipeline but is never a dependency of it.
