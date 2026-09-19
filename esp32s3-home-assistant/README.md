# ESP32-S3 Home Assistant Voice Satellite

Clean-room v2 firmware for the ESP32-S3-WROOM-1 N16R8 voice satellite. It uses
ESPHome's ESP-IDF voice stack, on-device microWakeWord detection, a fresh Home
Assistant Assist command pipeline after every wake, and a purpose-built local
voice control dashboard.

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
| MAX98357A | VIN | 3V3 no-solder option, or verified regulated 5V |
| MAX98357A | SD/SD_MODE | 3V3 (enable) |
| MAX98357A | BCLK | GPIO17 |
| MAX98357A | LRC/WS | GPIO18 |
| MAX98357A | DIN | GPIO8 |
| MAX98357A | GAIN | Unconnected (recommended 9 dB) |
| MAX98357A | GND | GND |
| INMP441 | SCK | GPIO15 |
| INMP441 | WS | GPIO16 |
| INMP441 | SD | GPIO7 |
| BOOT button | input | GPIO0 |

See [`HARDWARE.md`](HARDWARE.md) for the canonical connection guide. It has a
separate, complete wiring table for the OLED, microphone, amplifier, speaker,
and 12-pixel LED ring, followed by whole-system cross-check diagrams.
Front/back photographs identify the fitted board as an ESP32-S3 `2025-V1.4`
dual-USB-C N16R8 DevKitC-style clone. Its front-side `IN-OUT` solder jumper
controls whether USB VBUS reaches the `5Vin` header. The operator has now closed
that jumper and measured 4.8 V at `5Vin`, which is valid for the MAX98357A and
LED ring. Its back-side `USB-OTG` jumper is not needed for this COM-powered
arrangement. Never combine external `5Vin` power and USB while `IN-OUT` is
closed.

No solder modification is required to test or use the amplifier at reduced
power: leave `5Vin` unused and connect MAX98357A `VIN` and `SD` to the healthy
`3V3` rail. The amplifier's specified supply range includes 3.3 V. Begin at low
speaker volume; if audio causes a reset, the shared regulator lacks sufficient
headroom and the amplifier needs a dedicated or verified 5 V source.

The optional code-defined carrier PCB is in `circuit/`. Its tscircuit CLI and
TypeScript compiler are installed only in that directory and pinned by its npm
lockfile. The corrected source matches the official DevKitC-1 header map,
isolates optional external 5 V to the amplifier/ring rail, and passes netlist,
schematic-placement, PCB-placement, build, and copper-short checks. It remains
blocked from fabrication until the exact breakout-board bodies, pin orders,
overhangs, and heights are measured; see `circuit/README.md` before ordering or
starting an enclosure.

Speaker software volume defaults to **50%**, spans a true **0–100% PCM
amplitude** range, is restored after reboot, and is applied consistently to the
listening acknowledgement, the bounded diagnostic tone, and every streamed
response. There is no hidden response multiplier or half-volume ceiling.

## Supported dashboard capabilities

Open `http://<device-ip>/`. The dashboard is stored on the device and has no
cloud asset dependency. Its visible control surface is purpose-built rather
than a restyled ESPHome entity table. It provides:

- a large, plain-language live state surface for ready, listening, processing,
  speaking, unavailable, and error states;
- a touch-friendly 0–100% speaker slider with dedicated step buttons and a
  prominent speaker-test action;
- custom wake-word and wake-sound switches rather than the stock ESPHome
  controls;
- a touch-friendly **One-Breath Pre-roll** control from 180–340 ms, defaulting
  to 260 ms, for real-room trim calibration without reflashing;
- latest-heard and assistant-reply conversation cards;
- compact pipeline, total-time, Wi-Fi, and free-memory health indicators;
- deliberately separated restart and safe-mode actions with confirmation;
- essential connectivity, reset, uptime, heap, PSRAM, and loop-time evidence;
- explicit **Interaction Availability** and **Ready for Voice** entities;
- a bounded two-line OLED status layout that keeps every state inside the
  128×64 panel, uses the former RSSI footer space for status/last-heard text,
  and leaves Wi-Fi strength available in the browser diagnostics only;
- separate wake-to-pipeline, replay, speech detection, speech capture, STT,
  wake-to-action, and total-busy-time diagnostics;
- a separate **Voice Lab** evidence inbox that packages up to 200 wake-to-ready
  interactions into a master-detail review queue, shows explicit green
  **Successful** and red **Error** outcome flags, and uses a blue dot only for
  records that still need human review; the dot disappears as soon as a review
  label is selected;
- Voice Lab summary counts, a plain-language status guide, acoustic evidence,
  synchronized review labels/notes, report retention, and JSON/CSV export;
- a collection of bounded sound and stored-speech tests that honors the persistent
  volume slider, temporarily removes the shared-power LED-ring load, and
  independently exercises 16 kHz mono and matched dual-mono I2S output;
- a 300-row ESPHome log that remains active behind the custom interface for
  session capture and stock recovery.

The bundled browser UI loads a tiny blocking stylesheet before its larger
JavaScript bundle and shows a lightweight local connecting screen until the
custom voice console is attached. The stock ESPHome controls continue running
underneath as the local transport and recovery layer, but they are not the
visible product UI. A 12-second JavaScript fail-open reveals that stock recovery
surface if the custom console cannot start.

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

### Startup readiness

In a measured power-on trace, firmware setup completed in about 1 second and
Wi-Fi connected in about 6.1 seconds, but Home Assistant did not reconnect its
ESPHome API client until 33.5 seconds; local wake-word inference became ready at
33.6 seconds. The dominant delay was therefore the Home Assistant client
reconnect, not ESP32 initialization or RF quality.

The deployed Home Assistant container now uses Docker host networking, the
native topology documented for Home Assistant Container. Its former bridge
could reach the device by IP but could not receive LAN multicast, so
`aioesphomeapi` missed the ESP32's mDNS boot announcement and waited through an
existing exponential reconnect interval. Narrow UFW allowances cover trusted
LAN TCP 8123, LAN mDNS UDP 5353, and Speech-to-Phrase's bridge-to-host TCP 8123
connection. Existing Wyoming integration hostnames resolve to their published
loopback ports from the host-networked Home Assistant container, keeping Piper,
openWakeWord, and Speech-to-Phrase available without another proxy or service.

A later physical restart still reproduced about 21 seconds because Home
Assistant's ESPHome config entry retained the device's numeric address, which
bypassed the zeroconf wake path even after host networking was enabled. The
entry was reconfigured through Home Assistant's native flow to
`esp32s3-home-assistant.local`. On the controlled verification restart, Home
Assistant applied its intentional five-second expected-reboot cooldown and
then connected 7.1 seconds after disconnect/reboot began. This is the native
fix and requires no proxy, broker, or additional service.

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
Local wake detection re-arms when the direct Piper stream and Assist session
finish. If that stream remains active for 10 seconds after the pipeline ends, a
firmware watchdog hard-stops the speaker and lingering voice session, then
re-arms the local wake word. The recovered timeout is emitted as a replacement
record for the same session, so Research Sessions retains its WAV and
recognition evidence while showing the TTS transport failure instead of a false
success. Offline, disabled-wake-word, and unrecoverable states are reported
separately rather than collapsing every recovery failure into "wake disabled."

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
amplitude/dB across the complete range: 0% is muted, 50% is half PCM amplitude
(-6.02 dB), and 100% bypasses software attenuation. Direct Assist responses use
the same one-stage control with no additional multiplier. During TTS playback,
the shared-power LED ring turns fully off so the amplifier gets the greatest
instantaneous rail headroom firmware can provide; the ready indication returns
after the voice pipeline and buffered playback have closed.

Voice responses use ESPHome's direct Assist speaker stream at its native
protocol format: signed 16-bit, 16 kHz mono PCM. This restores the coupled
`on_tts_stream_start` / `on_tts_stream_end` lifecycle, so the spoken
confirmation is delivered before the session ends and local wake detection is
re-armed immediately afterward. The brief wake acknowledgement uses the same
format, and every TTS response explicitly restores that metadata before audio
starts. A 10-second watchdog remains only as an emergency transport fail-safe.

The MAX98357A runs in its native Philips-I2S mode with the required one-bit
data delay. The retired MSB setting was left-justified; it became audible after
a USB power cycle but produced the reported torn/distorted output. The earlier
standard-I2S silence result was invalid because the diagnostic buffer itself
had been mislabeled.

The dashboard's **Speaker sound tests** section plays a frequency sweep,
doorbell chime, randomized melody, soft noise, rising level steps, and two
stored speech samples through the physical speaker. All use 16 kHz signed
16-bit PCM and the current volume slider. Counting speech also has an identical
dual-mono stereo version to compare channel handling directly. Speech samples
are peak-normalized to approximately -1 dBFS; level steps use 10%, 25%, 50%, and
80% source amplitude. Start at a modest slider setting and stop if distorted.

Tests pause wake detection and switch the ring off. A nonblocking PSRAM-backed
player retains partial writes, waits for the output to drain, and then restores
wake readiness. **Stop test** cancels playback. Tests are rejected during an
active Assist session. Byte counts confirm delivery, not acoustic fidelity;
even active GPIO transitions do not prove correct I2S timing or clean output.
Quiet/distorted output at 100% remains unresolved pending listening comparisons.
The samples can be regenerated on Windows with
`powershell -NoProfile -File scripts/build-speaker-samples.ps1`; no cloud service
or private recording is required. The normal wake acknowledgement uses
continuous phase plus attack/release fades in the same 16 kHz mono format as
Assist speech.

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
top navigation on narrow screens. Research Sessions combines the newest 200
device records with every returned raw record from the connected diagnostics
service as a compact queue with exactly one selected detail workspace at a
time. This union is deliberate: stored recognition attempts are imported even
when their ESPHome log row never reached the browser, so decoder failures and
empty transcripts are not hidden by correlation. If the matching device record
arrives later, the dashboard merges it into the diagnostic-only row instead of
showing a duplicate. Device failures that stop before recognition still appear
from their structured log record; because Speech-to-Phrase never received those
captures, they correctly show device evidence without claiming that a server
WAV exists. The selected workspace separates
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
setting survives refresh. The queue imports all returned decoder statuses, not
only `OK`, and preserves the server record as the durable source for its audio
and decoder evidence.

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

Firmware prioritizes the reliable conversational contract: Home Assistant
streams the spoken confirmation directly as 16 kHz PCM, ESPHome exposes exact
stream-start/end events, and wake detection resumes from true pipeline
completion. Separate stored-speech and synthesized sound tests bypass Home
Assistant/Piper to help distinguish source/stream problems from output-path
problems. Successful byte delivery alone cannot establish the cause of distortion.

The remaining physical quality baseline is equally important. Leave `GAIN`
unconnected for the MAX98357A's 9 dB setting instead of grounding it for 12 dB;
the extra analog gain only reduces clipping margin. Place 10 µF and 0.1 µF
ceramic bypass capacitors directly between amplifier `VIN` and `GND`. Feed the
amp and ring from separate short 5 V/GND branches at the board header rather
than daisy-chaining through either module, and retain 470–1000 µF at the ring.
Use a short, capable USB supply/cable, because a 4 Ω speaker plus a 12-pixel ring
can exceed a weak computer port or cable during peaks even when a no-load meter
shows 4.8 V. Measure the amp's VIN while the reference sweep plays; substantial
sag or a reset is a power-distribution fault. Finally, confirm a 4–8 Ω speaker
with adequate power rating and never connect either bridge-tied speaker lead to
ground. Firmware cannot undo clipping after the PCM reaches the amplifier or
speaker.

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
