# ESP32-S3 Home Assistant Voice Satellite & Media Player

A dual-core ESP32-S3 smart voice satellite and media player featuring low-latency Piper neural TTS streaming (<200ms TTFS), I2S digital audio output via MAX98357A DAC, SSD1306 OLED status display, a real-time web dashboard, and Web OTA firmware updating.

The physical target is an **ESP32-S3-WROOM-1 N16R8**. The PlatformIO profile
must retain its 16 MB QIO flash and 8 MB Octal OPI PSRAM settings. The 144 KB
Whisper recording buffer is allocated explicitly in PSRAM so the Wi-Fi,
AsyncTCP, dashboard, and continuous wake stream keep sufficient internal heap.

---

## 📌 Hardware Pin Connections

### 1. MAX98357A I2S 3.2W DAC Amplifier
| ESP32-S3 Pin | MAX98357A Pin | Wire Color | Signal / Function | Logic / Voltage |
| :--- | :--- | :--- | :--- | :--- |
| **5V / VBUS** | `VIN` | 🔴 Red | 5V Power for 3.2W Audio Output | 5V DC (or 3.3V) |
| **GND** | `GND` | ⚫ Black | Common Ground | 0V |
| **GPIO 17** | `BCLK` | 🟠 Orange | I2S Bit Clock | 3.3V Logic |
| **GPIO 18** | `LRC` / `WS` | 🟢 Green | I2S Word Select (Left/Right) | 3.3V Logic |
| **GPIO 8** | `DIN` | 🟣 Purple | I2S Digital Serial Audio Data | 3.3V Logic |
| **3V3** *(optional)* | `SD_MODE` | 🔴 Red | Mode Select (Pull up to 3.3V for right/mix) | 3.3V Logic |
| **GND** *(optional)* | `GAIN` | ⚫ Black | Hardware Gain Setting (GND = +12dB) | 0V |

### 2. Cavity Box Speaker (4Ω 3W / 8Ω 2W)
| MAX98357A Pin | Speaker Terminal | Wire Color | Function |
| :--- | :--- | :--- | :--- |
| `+` / `OUT+` | Speaker Positive Terminal | 🔴 Red | Audio Output Positive |
| `-` / `OUT-` | Speaker Negative Terminal | ⚫ Black | Audio Output Negative |

### 3. SSD1306 I2C OLED Display
| ESP32-S3 Pin | SSD1306 OLED Pin | Wire Color | Signal / Function | Logic / Voltage |
| :--- | :--- | :--- | :--- | :--- |
| **3V3** | `VCC` / `VDD` | 🔴 Red | 3.3V Power Supply | 3.3V DC |
| **GND** | `GND` | ⚫ Black | Common Ground | 0V |
| **GPIO 6** | `SDA` | 🔵 Blue | I2C Serial Data | 3.3V Logic |
| **GPIO 5** | `SCL` / `SCK` | 🟡 Yellow | I2C Serial Clock | 3.3V Logic |

### 4. INMP441 I2S MEMS Microphone
| ESP32-S3 Pin | INMP441 Pin | Wire Color | Signal / Function | Logic / Voltage |
| :--- | :--- | :--- | :--- | :--- |
| **3V3** | `VDD` | 🔴 Red | 3.3V Power (**3.3V ONLY**) | 3.3V DC |
| **GND** | `GND` | ⚫ Black | Ground Reference | 0V |
| **GND** | `L/R` | ⚫ Black | Channel Select (GND = Left) | 0V |
| **GPIO 15** | `SCK` | 🟠 Orange | I2S Serial Bit Clock (RX) | 3.3V Logic |
| **GPIO 16** | `WS` | 🟢 Green | I2S Word Select (LRCLK) | 3.3V Logic |
| **GPIO 7** | `SD` | 🟣 Purple | I2S Serial Data Out from Mic | 3.3V Logic |

---

## 📊 Connection Flowchart

```mermaid
flowchart TD
    subgraph ESP32S3["ESP32-S3 DevKitC-1 (Dual-Core LX7)"]
        P5V["5V / VBUS (5V Rail)"]
        P3V3["3V3 (3.3V Rail)"]
        PGND["GND (Common Ground)"]
        G17["GPIO 17 (I2S TX BCLK)"]
        G18["GPIO 18 (I2S TX LRC)"]
        G8["GPIO 8 (I2S TX DIN)"]
        G15["GPIO 15 (I2S RX SCK)"]
        G16["GPIO 16 (I2S RX WS)"]
        G7["GPIO 7 (I2S RX SD)"]
        G6["GPIO 6 (I2C SDA)"]
        G5["GPIO 5 (I2C SCL)"]
    end

    subgraph MAX98357A["MAX98357A I2S DAC / Amp"]
        AVIN["VIN"]
        AGND["GND"]
        ABCLK["BCLK"]
        ALRC["LRC / WS"]
        ADIN["DIN"]
        ASPKP["OUT+"]
        ASPKN["OUT-"]
    end

    subgraph SPK["4Ω 3W Box Speaker"]
        SPOS["+ (Positive)"]
        SNEG["- (Negative)"]
    end

    subgraph INMP441["INMP441 MEMS Microphone"]
        MVDD["VDD (3.3V)"]
        MGND["GND"]
        MLR["L/R"]
        MSCK["SCK"]
        MWS["WS"]
        MSD["SD"]
    end

    subgraph OLED["SSD1306 128x64 OLED (0x3C)"]
        OVCC["VCC / VDD"]
        OGND["GND"]
        OSDA["SDA"]
        OSCL["SCL"]
    end

    %% Power Rails
    P5V -->|🔴 Red (5V Power)| AVIN
    P3V3 -->|🔴 Red (3.3V Power)| OVCC
    P3V3 -->|🔴 Red (3.3V Power)| MVDD
    PGND -->|⚫ Black (GND)| AGND
    PGND -->|⚫ Black (GND)| OGND
    PGND -->|⚫ Black (GND)| MGND
    PGND -->|⚫ Black (GND)| MLR

    %% I2S Digital Audio TX (Speaker)
    G17 -->|🟠 Orange (BCLK Clock)| ABCLK
    G18 -->|🟢 Green (LRC Word Select)| ALRC
    G8 -->|🟣 Purple (DIN Audio In)| ADIN

    %% I2S Digital Audio RX (Microphone)
    G15 -->|🟠 Orange (SCK Clock)| MSCK
    G16 -->|🟢 Green (WS Word Select)| MWS
    MSD -->|🟣 Purple (SD Audio Out)| G7

    %% Analog Speaker Drive
    ASPKP -->|🔴 Red| SPOS
    ASPKN -->|⚫ Black| SNEG

    %% I2C OLED Bus
    G6 -->|🔵 Blue (SDA Data)| OSDA
    G5 -->|🟡 Yellow (SCL Clock)| OSCL

    classDef pwr fill:#ef4444,stroke:#991b1b,color:#ffffff,stroke-width:2px;
    classDef gnd fill:#1f2937,stroke:#111827,color:#ffffff,stroke-width:2px;
    classDef i2s fill:#8b5cf6,stroke:#5b21b6,color:#ffffff,stroke-width:2px;
    classDef i2c fill:#3b82f6,stroke:#1d4ed8,color:#ffffff,stroke-width:2px;
    classDef spk fill:#10b981,stroke:#047857,color:#ffffff,stroke-width:2px;

    class P5V,P3V3,AVIN,OVCC,MVDD pwr;
    class PGND,AGND,OGND,MGND,MLR gnd;
    class G17,G18,G8,ABCLK,ALRC,ADIN,G15,G16,G7,MSCK,MWS,MSD i2s;
    class G6,G5,OSDA,OSCL i2c;
    class ASPKP,ASPKN,SPOS,SNEG,SPK spk;
```

---

## 🔌 Visual Wiring Schematic

```text
    ┌─────────────────────────────────────────────────────────────┐
    │                 ESP32-S3-DevKitC-1 (N16R8)                  │
    │                                                             │
    │  ─── Power Rails ───                                        │
    │  [5V]   ──(Red Wire)───────────> [VIN] MAX98357A 3.2W DAC    │
    │  [3V3]  ──(Red Wire)───────────> [VCC/VDD] SSD1306 OLED     │
    │  [3V3]  ──(Red Wire)───────────> [VDD] INMP441 Microphone    │
    │  [GND]  ──(Black Wire)─────────> Common Ground Rail (GND)    │
    │                                                             │
    │  ─── I2C Display Bus (0x3C) ───                             │
    │  [IO6]  ──(Blue Wire)──────────> [SDA] SSD1306 OLED         │
    │  [IO5]  ──(Yellow Wire)────────> [SCL] SSD1306 OLED         │
    │                                                             │
    │  ─── I2S Speaker Output (I2S_NUM_0 TX) ───                  │
    │  [IO17] ──(Orange Wire)────────> [BCLK] MAX98357A DAC       │
    │  [IO18] ──(Green Wire)─────────> [LRC]  MAX98357A DAC       │
    │  [IO8]  ──(Purple Wire)────────> [DIN]  MAX98357A DAC       │
    │         MAX98357A [OUT+] ──────> (+) 3W 4-8Ω Box Speaker    │
    │         MAX98357A [OUT-] ──────> (-) 3W 4-8Ω Box Speaker    │
    │                                                             │
    │  ─── I2S Microphone Input (I2S_NUM_1 RX) ───                │
    │  [IO15] ──(Orange Wire)────────> [SCK] INMP441 Mic          │
    │  [IO16] ──(Green Wire)─────────> [WS]  INMP441 Mic          │
    │  [IO7]  <─(Purple Wire)────────  [SD]  INMP441 Mic          │
    │  [GND]  ──(Black Wire)─────────> [L/R] (Left Channel)       │
    └─────────────────────────────────────────────────────────────┘
```

---

## 💻 Wokwi Visual Simulator

An interactive Wokwi visual diagram is provided in [`diagram.json`](diagram.json).

---

## 🌐 Web Dashboard & Modes

- **⚡ Media & Voice Mode:** Stream synthetic voice sentences via Piper neural TTS (<200ms TTFS), play chimes and sound effects (wake chime, Mario coin, fanfare, frequency sweep), test volume levels, and push custom text to the SSD1306 OLED screen.
- **🏠 Smart Home & Automation:** Dedicated streaming openWakeWord detection for *"Hey Burden"*, adaptive room-noise VAD, Wyoming Whisper command transcription, local intent matching, direct Govee UDP actions, and asynchronous Home Assistant REST state synchronization.
- **⚙️ Utilities & Web OTA:** Reset display to defaults, view network telemetry, or flash updated firmware binaries over Wi-Fi at `http://<device-ip>/update`.

The speaker starts at **17% master volume** after every boot. This single master
gain is applied to the startup chime, wake earcon, sound effects, sweep, and
streamed Piper TTS. The dashboard can adjust it for the current session.

The Utilities tab includes live voice-pipeline state, the remaining command
window, wake-stream/recording/transcription flags, a safe pipeline-reset button,
the exact USB monitor/upload commands, and a browser-visible rolling copy of the
device's serial output. Live diagnostics and new log snapshots travel over the
dashboard's existing WebSocket, avoiding repeated HTTP connections while audio
is streaming. The same information remains available manually at `/api/status`
and `/api/logs`.

The editable dashboard is `web/index.html`. After changing it, regenerate the
flash-resident gzip asset with `scripts/build-dashboard.ps1`; the compressed
page is about 7.6 KB instead of roughly 31 KB uncompressed.

## Modern Voice Pipeline

```text
INMP441 16 kHz audio
        │
        ├─ idle ──> Wyoming openWakeWord :10400 ──> 100 ms wake earcon
        │                                                │
        └─ command <── adaptive VAD + 250 ms pre-roll <──┘
                         │
                         └─> Wyoming Whisper :10300
                                  │
                                  └─> local intent
                                       ├─> immediate Govee UDP
                                       └─> queued HA REST synchronization
```

The microphone is sampled in 16 ms frames and the wake worker combines five of
them into each native 80 ms openWakeWord network chunk. Each payload is written
in bounded 512-byte pieces with TCP coalescing enabled. This keeps I2S capture
responsive while reducing packet/header pressure by 5× and preventing the wake
stream from starving the dashboard's HTTP and WebSocket connections.

The firmware first checks whether `WAKE_WORD_MODEL` exists on the openWakeWord service. When available, idle room audio goes only to the dedicated wake engine and Whisper receives only an actual command. If the custom model is absent, the firmware safely retains its stricter Whisper wake-phrase fallback and rechecks openWakeWord every 30 seconds.

### Wake-to-wake timing and recovery

- Wyoming openWakeWord currently applies a **2 second refractory period** after
  a detection.
- The wake earcon is about 100 ms, followed by a 110 ms acoustic settling guard.
- The command must begin within the following 5 second command window.
- A spoken command can record for up to 4.5 seconds, and Whisper can wait up to
  8 seconds for its transcription response.
- Once the command finishes—or the command window expires—the satellite returns
  to `waiting_for_wake`. Feedback audio temporarily pauses wake streaming so it
  cannot trigger on its own speaker.

For quick diagnosis, open the Utilities tab and inspect `phase`. Normal idle is
`waiting_for_wake` with `wake stream: connected`. Use **Reset Voice Pipeline**
if it remains in `waiting_for_command`, `recording_command`, or `transcribing`.
The reset cancels an in-flight Whisper wait safely without rebooting the ESP32.

The endpoint detector continuously estimates the room noise floor, uses separate speech-start and speech-stop thresholds, rejects short impulses, preserves 250 ms of speech onset, and permits commands up to 4.5 seconds. Speaker audio is excluded from microphone capture, and the pre-roll buffer is cleared after the wake earcon.

### Install the custom “Hey Burden” model

The repeatable training, validation, installation, and acceptance-test workflow is
kept in [`wake-word-training/`](wake-word-training/README.md).

1. Train `hey_burden.tflite` with Home Assistant's [official wake-word training environment](https://www.home-assistant.io/voice_control/create_wake_word/). Home Assistant recommends a distinctive three- or four-syllable phrase and notes that training normally takes 30–60 minutes.
2. Copy the model to `/share/openwakeword/hey_burden.tflite` on the Home Assistant host.
3. Reload the openWakeWord Wyoming integration or restart the openWakeWord app.
4. Confirm Serial Monitor reports `Model 'hey_burden' available`; the device changes engines automatically without another firmware flash.

For operator deployments over SSH, copy
`wake-word-training/deployment.example.json` to the ignored
`wake-word-training/deployment.local.json` and fill in the private host and
remote paths. This keeps the important deployment route durable on the local
machine without committing a private hostname or filesystem layout.

The implementation follows the maintained [ESPHome voice-assistant lifecycle](https://esphome.io/components/voice_assistant/), Home Assistant's [openWakeWord app configuration](https://github.com/home-assistant/addons/blob/master/openwakeword/DOCS.md), and the current [Wyoming openWakeWord event protocol](https://github.com/rhasspy/wyoming-openwakeword).


---

## 🚀 Build and Flash

```sh
cd esp32s3-home-assistant
pio run -t upload --upload-port COM4
pio device monitor --port COM4 --baud 115200 --rts 0 --dtr 0
```

On boot, the serial log should confirm `Whisper buffer in PSRAM` and report
roughly 8 MB of free PSRAM. If it reports an internal-RAM fallback, stop and
check the N16R8 memory settings before testing the dashboard or voice pipeline.
