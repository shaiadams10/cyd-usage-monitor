# ESP32-S3 Standalone Voice Assistant ("assistant")

Deployment-specific server, lamp, and Home Assistant entity values belong only
in the ignored `include/secrets.h`. The committed example uses documentation
addresses and generic entity names.

A focused, clean-slate voice satellite for the **ESP32-S3-DevKitC-1**. This project removes the OLED monitor to eliminate display latency and bus contention, connecting only the **INMP441 I2S MEMS Microphone**, **MAX98357A 3.2W I2S Class D DAC Amplifier**, and **Cavity Box Speaker**.

It features Voice Activity Detection (VAD), Wyoming Whisper STT audio streaming, direct sub-5ms Govee Local UDP & Home Assistant REST smart light control, audible chimes, an interactive serial CLI, and a real-time Web Dashboard.

---

## 📌 Master Hardware Pin Connections & Color Matrix

### 1. MAX98357A 3.2W I2S Class D DAC Amplifier (All 7 Pins + Speaker)

> [!IMPORTANT]
> **Why previous amplifier tests failed when ignoring pins:**
> - **`SD_MODE` (Shutdown / Channel Select):** If left unconnected or floating on clone breakout boards, the pin drops below $0.16\text{V}$, putting the amplifier into **Hardware Shutdown (mute)**. Connecting `SD_MODE` directly to **3.3V** keeps the amplifier permanently awake and active in stereo mix mode.
> - **`GAIN` (Hardware Gain Setting):** If left floating, the amplifier gain drifts and amplifies Wi-Fi high-frequency switching noise. Connecting `GAIN` directly to **GND** locks the gain to a stable, crisp **+12dB**.

| ESP32-S3 Pin | MAX98357A Pin | Wire Color | Function & Electrical Purpose |
| :--- | :--- | :--- | :--- |
| **`5V / VBUS`** (or 3.3V) | **`VIN`** | 🔴 Red | 5V Power Supply (5V provides max 3.2W loudness into 4Ω) |
| **`GND`** | **`GND`** | ⚫ Black | Power Ground Reference (0V) |
| **`3.3V`** | **`SD_MODE`** / `SD` | 🔴 Red | **Shutdown Control**: Pull to 3.3V to enable amp (prevents sleep/mute) |
| **`GND`** | **`GAIN`** | ⚫ Black | **Hardware Gain**: Tie to GND for fixed +12dB clean gain |
| **`GPIO 17`** | **`BCLK`** | 🟠 Orange | I2S Bit Clock (Serial Clock) |
| **`GPIO 18`** | **`LRC`** / `WS` | 🟢 Green | I2S Word Select (Left/Right Clock) |
| **`GPIO 8`** | **`DIN`** | 🟣 Purple | I2S Serial Audio Data from ESP32 to DAC |

#### Speaker Connections
| MAX98357A Output | Speaker Lead | Wire Color | Description |
| :--- | :--- | :--- | :--- |
| **`OUT+`** / `+` | Speaker Positive Terminal | 🔴 Red | Differential audio output (+) |
| **`OUT-`** / `-` | Speaker Negative Terminal | ⚫ Black | Differential audio output (-) |

---

### 2. INMP441 Omnidirectional I2S MEMS Microphone (All 6 Pins)

> [!CAUTION]
> **Strict 3.3V Voltage Limit:** The INMP441 MEMS sensor is rated strictly for **3.3V**. Connecting `VDD` to 5V will permanently burn out the microphone.

| ESP32-S3 Pin | INMP441 Pin | Wire Color | Function & Electrical Purpose |
| :--- | :--- | :--- | :--- |
| **`3.3V`** | **`VDD`** | 🔴 Red | **3.3V ONLY** Sensor Power Supply |
| **`GND`** | **`GND`** | ⚫ Black | Power Ground Reference (0V) |
| **`GND`** | **`L/R`** | ⚫ Black | **Channel Select**: Tie to GND for Left Channel (Standard I2S) |
| **`GPIO 15`** | **`SCK`** | 🟠 Orange | I2S Serial Bit Clock for Microphone |
| **`GPIO 16`** | **`WS`** | 🟢 Green | I2S Word Select (Sample Clock @ 16kHz) |
| **`GPIO 7`** | **`SD`** | 🟣 Purple | I2S Serial Data Out from Microphone to ESP32 |

---

## 🗺️ Master Wiring Schematic (Mermaid Flowchart)

```mermaid
flowchart TD
    subgraph ESP32S3["ESP32-S3 DevKitC-1 (N16R8)"]
        P5V["5V / VBUS (5V Rail)"]
        P3V3["3V3 (3.3V Rail)"]
        PGND["GND (Common Ground)"]

        subgraph I2S_Speaker["I2S TX (Speaker DAC)"]
            G17["GPIO 17 (BCLK)"]
            G18["GPIO 18 (LRC / WS)"]
            G8["GPIO 8 (DIN)"]
        end

        subgraph I2S_Mic["I2S RX (Microphone)"]
            G15["GPIO 15 (SCK)"]
            G16["GPIO 16 (WS)"]
            G7["GPIO 7 (SD)"]
        end
    end

    subgraph MAX98357A["MAX98357A 3.2W DAC / Amp"]
        AVIN["VIN (5V)"]
        AGND["GND"]
        ASD["SD_MODE (Tie to 3.3V)"]
        AGAIN["GAIN (Tie to GND)"]
        ADIN["DIN"]
        ABCLK["BCLK"]
        ALRC["LRC / WS"]
        ASPKP["OUT+"]
        ASPKN["OUT-"]
    end

    subgraph SPK["3W Cavity Box Speaker"]
        SPOS["+ (Positive)"]
        SNEG["- (Negative)"]
    end

    subgraph INMP441["INMP441 MEMS Microphone"]
        MVDD["VDD (3.3V ONLY!)"]
        MGND["GND"]
        MLR["L/R (Tie to GND)"]
        MSCK["SCK"]
        MWS["WS"]
        MSD["SD (Data Out)"]
    end

    %% Power Wiring
    P5V -->|🔴 Red (5V)| AVIN
    P3V3 -->|🔴 Red (3.3V)| ASD
    P3V3 -->|🔴 Red (3.3V)| MVDD
    PGND -->|⚫ Black (GND)| AGND
    PGND -->|⚫ Black (GND)| AGAIN
    PGND -->|⚫ Black (GND)| MGND
    PGND -->|⚫ Black (GND)| MLR

    %% I2S Audio Out
    G17 -->|🟠 Orange| ABCLK
    G18 -->|🟢 Green| ALRC
    G8 -->|🟣 Purple| ADIN
    ASPKP -->|🔴 Red| SPOS
    ASPKN -->|⚫ Black| SNEG

    %% I2S Audio In
    G15 -->|🟠 Orange| MSCK
    G16 -->|🟢 Green| MWS
    MSD -->|🟣 Purple| G7

    classDef pwr fill:#ef4444,stroke:#991b1b,color:#ffffff,stroke-width:2px;
    classDef gnd fill:#1f2937,stroke:#111827,color:#ffffff,stroke-width:2px;
    classDef i2s fill:#8b5cf6,stroke:#5b21b6,color:#ffffff,stroke-width:2px;
    classDef spk fill:#10b981,stroke:#047857,color:#ffffff,stroke-width:2px;

    class P5V,P3V3,AVIN,ASD,MVDD pwr;
    class PGND,AGND,AGAIN,MGND,MLR gnd;
    class G17,G18,G8,ADIN,ABCLK,ALRC,G15,G16,G7,MSCK,MWS,MSD i2s;
    class ASPKP,ASPKN,SPOS,SNEG,SPK spk;
```

---

## 🔌 Master Visual Wiring ASCII Schematic

```text
    ┌─────────────────────────────────────────────────────────────┐
    │                 ESP32-S3-DevKitC-1 (N16R8)                  │
    │                                                             │
    │  ─── Power Rails ───                                        │
    │  [5V]   ──(Red Wire)───────────> [VIN] MAX98357A Amp        │
    │  [3V3]  ──(Red Wire)───────────> [SD_MODE] MAX98357A Amp    │
    │  [3V3]  ──(Red Wire)───────────> [VDD] INMP441 Mic (3.3V)   │
    │  [GND]  ──(Black Wire)─────────> Common Ground Rail (GND)    │
    │                                  ├──> [GND] MAX98357A       │
    │                                  ├──> [GAIN] MAX98357A      │
    │                                  ├──> [GND] INMP441         │
    │                                  └──> [L/R] INMP441         │
    │                                                             │
    │  ─── I2S Speaker Output (MAX98357A DAC) ───                 │
    │  [IO17] ──(Orange Wire)────────> [BCLK]                     │
    │  [IO18] ──(Green Wire)─────────> [LRC / WS]                 │
    │  [IO8]  ──(Purple Wire)────────> [DIN]                      │
    │         MAX98357A [OUT+] ──────> (+) 3W 4-8Ω Box Speaker    │
    │         MAX98357A [OUT-] ──────> (-) 3W 4-8Ω Box Speaker    │
    │                                                             │
    │  ─── I2S Microphone Input (INMP441 MEMS) ───                │
    │  [IO15] ──(Orange Wire)────────> [SCK]                      │
    │  [IO16] ──(Green Wire)─────────> [WS]                       │
    │  [IO7]  <─(Purple Wire)────────  [SD]                       │
    └─────────────────────────────────────────────────────────────┘
```

---

## 🗣️ Voice Commands & Trigger Logic

When speaking to the microphone, the onboard VAD (Voice Activity Detection) detects speech, plays a subtle wake chime, captures up to 3.5s of audio, and streams it to **Wyoming Whisper STT** (`<voice-server-ip>:10300`).

### Supported Trigger Phrases:
- **"Hey Burden, lights on"** $\rightarrow$ Turns ON Govee lamps & HA `all_lamps` + plays Mario Coin sound.
- **"Hey Burden, lights off"** $\rightarrow$ Turns OFF Govee lamps & HA `all_lamps` + plays Powerdown chime.
- **"Hey Burden, toggle lights"** $\rightarrow$ Toggles lamp state.
- **"Hey Burden, lamp 1 on"** $\rightarrow$ Turns ON the configured Lamp 1 entity.
- **"Hey Burden, lamp 2 off"** $\rightarrow$ Turns OFF the configured Lamp 2 entity.
- **"Hey Burden, play chime"** $\rightarrow$ Plays speaker test chime.

---

## 🎮 Interactive Serial Monitor CLI

Open the serial monitor at **115200 baud**:

| Key | Action | Description |
| :---: | :--- | :--- |
| `1` or `on` | **Lights ON** | Direct Govee UDP + HA REST + Mario coin audio feedback |
| `0` or `off` | **Lights OFF** | Direct Govee UDP + HA REST + Powerdown chime |
| `t` or `toggle` | **Toggle** | Toggles lamp power state |
| `r` or `record` | **Record (3.5s)** | Manually starts microphone capture and Whisper transcription |
| `s` or `sound` | **Test Audio** | Tests speaker startup tone and coin effect |
| `m` or `mic` | **Mic VU** | Prints real-time microphone RMS and peak levels |
| `?` | **Help** | Displays CLI command menu |

---

## 🌐 Real-Time Web Dashboard

Once connected to your Wi-Fi network, navigate to `http://<device-ip>` in your browser:
- **💡 Smart Lights Controls:** Instant ON, OFF, and Toggle buttons.
- **🎙️ Speech & Microphone:** "Record & Transcribe (3.5s)" button with real-time live VU level meter.
- **📝 Live Transcript & Status:** Shows the raw transcript returned from Whisper STT and current execution status.

---

## 🚀 Build, Flash & Run

```sh
cd assistant
pio run -t upload
pio device monitor -b 115200
```
