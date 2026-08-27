# Hardware Inventory & Pin Mapping Matrix

This document tracks all connected hardware, modules, and pin mappings for our ESP32-S3 smart voice assistant ecosystem.

---

## 1. Microcontroller Board

| Specification | Details |
| :--- | :--- |
| **Model** | **ESP32-S3-DevKitC-1** |
| **Chip Package** | ESP32-S3 (QFN56) Rev v0.2 |
| **Core Architecture** | Xtensa® Dual-Core 32-bit LX7 @ 240 MHz with Vector Instructions (AI/DSP) |
| **Flash Memory** | **16 MB** Quad SPI Flash |
| **PSRAM** | **8 MB** Embedded PSRAM |
| **USB Interface** | WCH CH343 High-Speed USB-to-UART Bridge (`COM4`, VID `1A86`, PID `55D3`) |
| **Wireless** | 2.4 GHz Wi-Fi (802.11 b/g/n) + Bluetooth 5.0 (LE) |

---

## 2. Connected Peripherals & Modules

### A. I2C OLED Display
- **Type**: Purchased 0.96" monochrome OLED module
- **Driver IC**: SSD1306
- **Resolution**: 128 × 64 pixels
- **I2C Address**: `0x3C`
- **Operating Voltage**: 3.3V
- **Listing dimensions**: 27.5 × 27.8 mm nominal PCB; 2.54 mm header pitch
- **Pin order**: `GND`, `VCC`, `SCL`, `SDA`

### B. I2S MEMS Microphone Module
- **Type**: Omnidirectional I2S MEMS Microphone
- **Model**: **INMP441**
- **Architecture**: Low-noise, high-precision MEMS sensor with integrated I2S 24-bit ADC
- **Operating Voltage**: 3.3V (Do **not** connect to 5V)
- **Directivity**: Omnidirectional
- **SNR**: 61 dBA
- **Purchased breakout**: HZWDONE round 14 × 14 mm PCB with a 2×3 header
- **Labeled pad layout**: `SD VDD GND` above `L/R WS SCK` when viewed from the
  labeled face with the acoustic-port arrow pointing right

### C. I2S Audio Amplifier & DAC
- **Type**: I2S 3W Mono Class D Audio Amplifier & DAC Decoder
- **Model**: **MAX98357A**
- **DAC & Power**: Integrated 32-bit DAC, 3.2W output into 4Ω at 5V (or ~1.5W at 3.3V)
- **Efficiency**: Class D >92% efficiency
- **Supported Sample Rates**: 8 kHz – 96 kHz
- **Operating Voltage**: 2.5V – 5.5V (Connect to 5V for maximum loudness or 3.3V)
- **Purchased breakout size**: 18.7 × 17.7 mm
- **Header order**: `LRC`, `BCLK`, `DIN`, `GAIN`, `SD`, `VIN`, `GND`

### D. Box Speaker
- **Type**: Square Small Cavity Box Speaker (3525 / 2535 format)
- **Impedance & Power**: 4Ω 3W / 8Ω 2W
- **Connection**: Direct wiring to MAX98357A `+` and `-` audio outputs
- **Listing dimensions**: 25 × 35 mm body, approximately 165 mm lead, 1.25 mm plug
- **Order option still required**: Confirm whether the delivered speaker is the
  4Ω/3W or 8Ω/2W version and measure its thickness.

### E. Addressable LED Ring
- **Type**: WS2812/NeoPixel-compatible 5V GRB addressable LED ring
- **Verified Pixel Count**: 12 pixels in the operator-supplied photograph
- **Listing outside diameter**: 52 mm for the 12-pixel option
- **Data Input**: `DI`/`DIN` on GPIO4; never connect the ESP32 data wire to `DO`
- **Power**: 5V with common ground. Use a separate regulated 5V supply for
  sustained high-brightness use and join its ground to ESP32 ground.
- **Status Ownership**: Solid green means ready; a rotating three-pixel yellow
  gradient means listening; a full breathing-yellow ring means processing,
  acting, or speaking; pulsing red means offline/error; and dim amber means the
  wake word is disabled.
- **Signal Conditioning**: Use a 330–470 Ω series data resistor and 470–1000 µF
  local bulk capacitor; add a 74AHCT125/74HCT14 if 3.3 V data is marginal at 5 V.

---

## 3. Master GPIO Pinout Map

| ESP32-S3 GPIO | Connected Peripheral | Module Pin | Function / Description | Wire Color |
| :--- | :--- | :--- | :--- | :--- |
| **5V / VBUS** | MAX98357A Amplifier | `VIN` | 5V Power for 3W Audio Amplifier (or 3.3V) | 🔴 Red |
| **3.3V** | Power Rail | `VCC` / `VDD` | 3.3V Logic, OLED & Microphone Power | 🔴 Red |
| **GND** | Ground Rail | `GND` / `L/R` | Common Ground | ⚫ Black |
| **GPIO 4** | Addressable LED Ring | `DI` / `DIN` | WS2812 RMT data input | 🟡 Yellow / White |
| **GPIO 5** | OLED Display | `SCK` / `SCL` | I2C Clock | 🟡 Yellow |
| **GPIO 6** | OLED Display | `SDA` | I2C Data | 🔵 Blue |
| **GPIO 17** | MAX98357A Amplifier | `BCLK` | I2S Bit Clock for Speaker | 🟠 Orange |
| **GPIO 18** | MAX98357A Amplifier | `LRC` / `WS` | I2S Word Select (Left/Right Clock) | 🟢 Green |
| **GPIO 8** | MAX98357A Amplifier | `DIN` | I2S Digital Audio Data to Amplifier | 🟣 Purple |
| **GPIO 15** | INMP441 Microphone | `SCK` | I2S Serial Bit Clock for Microphone | 🟠 Orange |
| **GPIO 16** | INMP441 Microphone | `WS` | I2S Word Select for Microphone | 🟢 Green |
| **GPIO 7** | INMP441 Microphone | `SD` | I2S Serial Data Out from Microphone | 🟣 Purple |

> [!CAUTION]
> **Reserved Internal Pins:** On this 8MB PSRAM ESP32-S3 board, avoid using `GPIO 26` through `GPIO 38`, as they are dedicated to the high-speed Octal/Quad Flash and PSRAM bus.

---

## 4. Master Ecosystem Wiring Flowchart

```mermaid
flowchart TD
    subgraph ESP32S3["ESP32-S3 DevKitC-1 (N16R8)"]
        P5V["5V / VBUS (5V Rail)"]
        P3V3["3V3 (3.3V Rail)"]
        PGND["GND (Common Ground)"]

        subgraph BusI2C["I2C Bus"]
            G6["GPIO 6 (SDA)"]
            G5["GPIO 5 (SCL)"]
        end

        G4["GPIO 4 (LED Ring Data)"]

        subgraph BusI2S_TX["I2S TX (Speaker Audio)"]
            G17["GPIO 17 (BCLK)"]
            G18["GPIO 18 (LRC / WS)"]
            G8["GPIO 8 (DIN)"]
        end

        subgraph BusI2S_RX["I2S RX (Microphone Audio)"]
            G15["GPIO 15 (SCK)"]
            G16["GPIO 16 (WS)"]
            G7["GPIO 7 (SD)"]
        end
    end

    subgraph OLED["SSD1306 128x64 OLED (0x3C)"]
        OVCC["VCC / VDD"]
        OGND["GND"]
        OSDA["SDA"]
        OSCL["SCL"]
    end

    subgraph MAX98357A["MAX98357A 3.2W DAC / Amp"]
        AVIN["VIN (5V)"]
        AGND["GND"]
        ABCLK["BCLK"]
        ALRC["LRC / WS"]
        ADIN["DIN"]
        ASPKP["OUT+"]
        ASPKN["OUT-"]
    end

    subgraph SPK["3W Box Speaker"]
        SPOS["+ (Positive)"]
        SNEG["- (Negative)"]
    end

    subgraph INMP441["INMP441 MEMS Microphone"]
        MVDD["VDD (3.3V Only!)"]
        MGND["GND"]
        MLR["L/R (Left Channel)"]
        MSCK["SCK"]
        MWS["WS"]
        MSD["SD (Data Out)"]
    end

    subgraph LEDRING["12-pixel WS2812/NeoPixel Ring"]
        LVCC["5V / VCC"]
        LGND["GND"]
        LDI["DI / DIN"]
    end

    %% Power Distribution
    P5V -->|🔴 Red (5V)| AVIN
    P5V -->|🔴 Red (5V)| LVCC
    P3V3 -->|🔴 Red (3.3V)| OVCC
    P3V3 -->|🔴 Red (3.3V)| MVDD
    PGND -->|⚫ Black| AGND
    PGND -->|⚫ Black| OGND
    PGND -->|⚫ Black| MGND
    PGND -->|⚫ Black| MLR
    PGND -->|⚫ Black| LGND
    G4 -->|🟡 Yellow / White| LDI

    %% I2C OLED
    G6 -->|🔵 Blue| OSDA
    G5 -->|🟡 Yellow| OSCL

    %% I2S DAC / Speaker
    G17 -->|🟠 Orange| ABCLK
    G18 -->|🟢 Green| ALRC
    G8 -->|🟣 Purple| ADIN
    ASPKP -->|🔴 Red| SPOS
    ASPKN -->|⚫ Black| SNEG

    %% I2S Microphone
    G15 -->|🟠 Orange| MSCK
    G16 -->|🟢 Green| MWS
    MSD -->|🟣 Purple| G7

    classDef pwr fill:#ef4444,stroke:#991b1b,color:#ffffff,stroke-width:2px;
    classDef gnd fill:#1f2937,stroke:#111827,color:#ffffff,stroke-width:2px;
    classDef i2c fill:#3b82f6,stroke:#1d4ed8,color:#ffffff,stroke-width:2px;
    classDef i2s fill:#8b5cf6,stroke:#5b21b6,color:#ffffff,stroke-width:2px;
    classDef spk fill:#10b981,stroke:#047857,color:#ffffff,stroke-width:2px;

    class P5V,P3V3,AVIN,OVCC,MVDD pwr;
    class PGND,AGND,OGND,MGND,MLR gnd;
    class G6,G5,OSDA,OSCL i2c;
    class G4,LDI i2c;
    class G17,G18,G8,ABCLK,ALRC,ADIN,G15,G16,G7,MSCK,MWS,MSD i2s;
    class ASPKP,ASPKN,SPOS,SNEG,SPK spk;
```

---

## 5. Master Visual Wiring Schematic

```text
    ┌─────────────────────────────────────────────────────────────┐
    │                 ESP32-S3-DevKitC-1 (N16R8)                  │
    │                                                             │
    │  ─── Power Rails ───                                        │
    │  [5V]   ──(Red Wire)───────────> [VIN] MAX98357A 3.2W DAC    │
    │  [3V3]  ──(Red Wire)───────────> [VCC/VDD] SSD1306 OLED     │
    │  [3V3]  ──(Red Wire)───────────> [VDD] INMP441 Microphone    │
    │  [GND]  ──(Black Wire)─────────> Common Ground Rail (GND)    │
    │  [5V]   ──(Red Wire)───────────> [5V] WS2812 LED Ring        │
    │  [IO4]  ──(Yellow/White)───────> [DI] WS2812 LED Ring        │
    │  [GND]  ──(Black Wire)─────────> [GND] WS2812 LED Ring       │
    │                                                             │
    │  ─── I2C Display Bus (0x3C) ───                             │
    │  [IO6]  ──(Blue Wire)──────────> [SDA] SSD1306 OLED         │
    │  [IO5]  ──(Yellow Wire)────────> [SCL] SSD1306 OLED         │
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
    │  [GND]  ──(Black Wire)─────────> [L/R] (Left Channel)       │
    └─────────────────────────────────────────────────────────────┘
```
