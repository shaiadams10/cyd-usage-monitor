# Hardware Inventory & Connection Guide

This is the canonical wiring guide for the ESP32-S3 Home Assistant voice
satellite. Wire one device at a time using the tables in section 2, then use
the ESP32-centric table in section 3 as a final cross-check.

> [!IMPORTANT]
> Disconnect USB and external power before changing wires. All modules must
> share ESP32 ground. The board's `5Vin` header and its `3V3` rail must never be
> joined together.

---

## 1. Microcontroller Board

| Specification | Details |
| :--- | :--- |
| **Model** | **ESP32-S3 `2025-V1.4` DevKitC-style clone (dual USB-C, 44-pin N16R8)** |
| **Chip Package** | ESP32-S3 (QFN56) Rev v0.2 |
| **Core Architecture** | Xtensa® Dual-Core 32-bit LX7 @ 240 MHz with Vector Instructions (AI/DSP) |
| **Flash Memory** | **16 MB** Quad SPI Flash |
| **PSRAM** | **8 MB** Embedded PSRAM |
| **USB Interface** | WCH CH343 high-speed USB-to-UART bridge plus native ESP32-S3 USB |
| **Wireless** | 2.4 GHz Wi-Fi (802.11 b/g/n) + Bluetooth 5.0 (LE) |

This is not electrically identical to the official Espressif DevKitC-1 power
path. Its header is labeled `5Vin`, and a two-pad `IN-OUT` solder jumper selects
whether USB VBUS reaches that header. Physical front/back photographs confirm
that this board was supplied with its `IN-OUT` pads open; its separate back-side
`USB-OTG` pads are open too. With `IN-OUT` open, `5Vin` is an input—not a usable
USB-powered 5 V output—and measured 1.3–1.98 V unloaded while both `3V3` pins
correctly measured 3.3 V. The operator has now shorted the clearly labeled
`IN-OUT` pads, connecting COM-port USB VBUS to `5Vin`, and measured 4.8 V at the
header. The `USB-OTG` jumper is not required for this arrangement. Never bridge
unlabeled pads, and never combine USB and an external `5Vin` supply while
`IN-OUT` is closed. See the [matching board power-path notes](https://github.com/profharris/YD-ESP32-S3_ESP32-S3-WROOM-1_Dev#notes%C2%B9-rgb-in-out-usb-otg-solder-jumper-pads).

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

#### Connect the SSD1306 OLED

| OLED pin | Connect to ESP32-S3 | Purpose | Suggested wire |
| :--- | :--- | :--- | :--- |
| `GND` | `GND` | Ground | ⚫ Black |
| `VCC` / `VDD` | `3V3` | 3.3 V power | 🔴 Red |
| `SCL` / `SCK` | `GPIO5` | I2C clock | 🟡 Yellow |
| `SDA` | `GPIO6` | I2C data | 🔵 Blue |

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

#### Connect the INMP441 microphone

| INMP441 pin | Connect to ESP32-S3 | Purpose | Suggested wire |
| :--- | :--- | :--- | :--- |
| `VDD` | `3V3` | 3.3 V power only | 🔴 Red |
| `GND` | `GND` | Ground | ⚫ Black |
| `L/R` | `GND` | Select the left I2S channel used by the firmware | ⚫ Black |
| `SCK` | `GPIO15` | I2S bit clock | 🟠 Orange |
| `WS` | `GPIO16` | I2S word select | 🟢 Green |
| `SD` | `GPIO7` | Microphone audio data to ESP32 | 🟣 Purple |

> [!CAUTION]
> The INMP441 is a 3.3 V device. Do not connect its `VDD` pin to 5 V.

### C. I2S Audio Amplifier & DAC

- **Type**: I2S 3W Mono Class D Audio Amplifier & DAC Decoder
- **Model**: **MAX98357A**
- **DAC & Power**: Integrated 32-bit DAC, 3.2W output into 4Ω at 5V (or ~1.5W at 3.3V)
- **Efficiency**: Class D >92% efficiency
- **Supported Sample Rates**: 8 kHz – 96 kHz
- **Operating Voltage**: 2.5V – 5.5V (Connect to 5V for maximum loudness or 3.3V)
- **Purchased breakout size**: 18.7 × 17.7 mm
- **Header order**: `LRC`, `BCLK`, `DIN`, `GAIN`, `SD`, `VIN`, `GND`

#### Connect the MAX98357A amplifier

| MAX98357A pin | Connect to ESP32-S3 | Purpose | Suggested wire |
| :--- | :--- | :--- | :--- |
| `VIN` | `3V3` (no-solder option) or verified regulated `5V` | The amplifier accepts 2.5–5.5 V; 3.3 V is quieter but avoids modifying this board | 🔴 Red |
| `GND` | `GND` | Power and signal ground | ⚫ Black |
| `SD` / `SD_MODE` | `3V3` | Pull high so the fitted breakout remains enabled | 🔴 Red |
| `GAIN` | **Leave unconnected** | Recommended 9 dB hardware gain; more clipping margin than `GAIN` to GND (+12 dB) | — |
| `BCLK` | `GPIO17` | I2S bit clock | 🟠 Orange |
| `LRC` / `WS` | `GPIO18` | I2S word select | 🟢 Green |
| `DIN` | `GPIO8` | ESP32 audio data to amplifier | 🟣 Purple |

For the fitted board without solder modification, connect both amplifier `VIN`
and `SD` to `3V3`; the MAX98357A supports this voltage, with less maximum output
power than at 5 V. Start at low volume because the amplifier then shares the
board's 3.3 V regulator with the ESP32 and peripherals. The higher-power option
uses verified regulated 5 V for `VIN` while retaining `3V3` only for `SD`. On
this board, `5Vin` does not carry USB 5 V while `IN-OUT` is open. Never join the
3.3 V and 5 V rails.

> [!WARNING]
> The header has both a pin marked `5` (`GPIO5`) and a different pin marked
> `5Vin`; they are not interchangeable. More importantly, this clone's `5Vin`
> is isolated from USB by the open `IN-OUT` jumper. Do not power the amplifier
> from `5Vin` until a meter confirms about 5 V there. Using `3V3` for amplifier
> `VIN` is the supported no-solder alternative.

#### If the amplifier is silent

The documented connections are electrically valid for the MAX98357A: `VIN`
may be 5 V while its I2S inputs use 3.3 V logic, `SD_MODE` above 1.4 V keeps the
part enabled and selects the left I2S slot, and an unconnected `GAIN` pin selects
9 dB gain. A direct `GAIN`-to-`GND` connection selects 12 dB but is no longer
recommended because the extra gain reduces the usable unclipped volume range.
The firmware sends the same program to both I2S slots, so the selected slot does
not change the audible content.

The previously flashed device's 16 kHz diagnostic accepted all 8,000 requested
PCM bytes and sampled active transitions on GPIO17 (`BCLK`), GPIO18 (`LRC`), and
GPIO8 (`DIN`) without an I2S driver, queue, or buffer error. The replacement
reference test sends a faded 22.05 kHz dual-mono sweep from 300 Hz to 5 kHz and
temporarily turns the shared-power LED ring off. If that test remains distorted,
the fault is downstream of decoding and is not caused by active LED data.

With power on and the black meter lead on amplifier `GND`, verify approximately
4.8–5 V at `VIN` and 3.3 V at `SD_MODE`. Repeat the `VIN` measurement while the
reference sweep plays; an idle reading alone cannot reveal cable/header sag on
audio peaks. Place a 10 µF capacitor and a 0.1 µF ceramic capacitor directly
across amplifier `VIN`/`GND`, with short leads. Run separate short 5 V/GND pairs
from the ESP32 header to the amplifier and LED ring rather than daisy-chaining
power through a module or breadboard row. Retain 470–1000 µF at the ring. A 4 Ω
speaker, ring, ESP32, and peripherals can collectively exceed a weak computer
USB port or thin cable; use a short, capable USB source/cable. If voltage sags,
audio crackles, or the ESP32 resets, stop and correct the power distribution.

If `IN-OUT` is open, a reading near 1.3–2.0 V at `5Vin` while `3V3` remains
correct is a floating node, not firmware voltage control. In that state, a
reversible low-power test may connect amplifier `VIN` and `SD` to `3V3` and
leave `5Vin` unused. If amplifier `SD_MODE` is held at 3.3 V while amplifier
`VIN` is below 3.0 V, the MAX98357A datasheet requires current limiting at
`SD_MODE`; do not leave this partial-power state as normal wiring.
Then disconnect power and measure the speaker by itself:
a nominal 4 ohm speaker normally reads roughly 3–4 ohms and an 8 ohm speaker
roughly 6–8 ohms; an open circuit indicates a broken lead, plug, or voice coil.
Follow the labels printed beside the actual breakout pads—the apparent
left-to-right header order reverses when the module is flipped over—and inspect
or reflow every header and speaker-terminal solder joint. Leave `GAIN`
unconnected for the recommended 9 dB setting. Never measure or connect either
bridge-tied speaker output to ESP32 ground.

### D. Box Speaker

- **Type**: Square Small Cavity Box Speaker (3525 / 2535 format)
- **Impedance & Power**: 4Ω 3W / 8Ω 2W
- **Connection**: Direct wiring to MAX98357A `+` and `-` audio outputs
- **Listing dimensions**: 25 × 35 mm body, approximately 165 mm lead, 1.25 mm plug
- **Order option still required**: Confirm whether the delivered speaker is the
  4Ω/3W or 8Ω/2W version and measure its thickness.

#### Connect the box speaker

| Speaker lead | Connect to MAX98357A | Purpose | Suggested wire |
| :--- | :--- | :--- | :--- |
| Positive (`+`) | `OUT+` / `SPK+` | Bridge-tied positive speaker output | 🔴 Red |
| Negative (`-`) | `OUT-` / `SPK-` | Bridge-tied negative speaker output | ⚫ Black |

> [!CAUTION]
> Neither speaker lead connects to ESP32 ground. Both leads must remain on the
> MAX98357A bridge-tied speaker output.

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

#### Connect the 12-pixel LED ring

| LED-ring pin | Connect to | Purpose | Suggested wire |
| :--- | :--- | :--- | :--- |
| `5V` / `VCC` | Regulated `5V` supply | LED power; do not use 3V3 | 🔴 Red |
| `GND` | ESP32 `GND` and supply ground | Common ground | ⚫ Black |
| `DI` / `DIN` | `GPIO4` through 330–470 Ω | Addressable LED data input | 🟡 Yellow / ⚪ White |

Connect the 470–1000 µF bulk capacitor across the ring's local `5V` and `GND`
terminals, observing capacitor polarity. Leave `DO` unconnected unless another
ring is chained after this one.

---

## 3. ESP32-S3 Connection Cross-check

| ESP32-S3 GPIO | Connected Peripheral | Module Pin | Function / Description | Wire Color |
| :--- | :--- | :--- | :--- | :--- |
| **3V3 or verified 5V** | MAX98357A Amplifier | `VIN` | 3.3 V no-solder/low-power option, or verified 5 V for greater output | 🔴 Red |
| **5V supply** | Addressable LED Ring | `5V` / `VCC` | Regulated 5 V LED power | 🔴 Red |
| **3V3** | MAX98357A Amplifier | `SD` / `SD_MODE` | Logic-high amplifier enable | 🔴 Red |
| **3V3** | SSD1306 OLED | `VCC` / `VDD` | 3.3 V display power | 🔴 Red |
| **3V3** | INMP441 Microphone | `VDD` | 3.3 V microphone power | 🔴 Red |
| **GND** | MAX98357A Amplifier | `GND` | Common power/signal return; leave `GAIN` unconnected | ⚫ Black |
| **GND** | SSD1306 OLED | `GND` | Common ground | ⚫ Black |
| **GND** | INMP441 Microphone | `GND`, `L/R` | Common ground and left-channel selection | ⚫ Black |
| **GND** | Addressable LED Ring | `GND` | Common ESP32/supply ground | ⚫ Black |
| **GPIO 4** | Addressable LED Ring | `DI` / `DIN` | WS2812 RMT data input | 🟡 Yellow / ⚪ White |
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
        P5V["Verified regulated 5V (closed IN-OUT or external)"]
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
        ASD["SD / SD_MODE (3.3V enable)"]
        AGAIN["GAIN (+12 dB)"]
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
    P3V3 -->|🔴 Red (3.3V enable)| ASD
    P3V3 -->|🔴 Red (3.3V)| OVCC
    P3V3 -->|🔴 Red (3.3V)| MVDD
    PGND -->|⚫ Black| AGND
    %% AGAIN intentionally has no connection: floating selects 9 dB gain.
    PGND -->|⚫ Black| OGND
    PGND -->|⚫ Black| MGND
    PGND -->|⚫ Black| MLR
    PGND -->|⚫ Black| LGND
    G4 -->|🟡 Yellow / ⚪ White| LDI

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

    class P5V,P3V3,AVIN,ASD,OVCC,MVDD pwr;
    class PGND,AGND,AGAIN,OGND,MGND,MLR gnd;
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
    │  [Verified 5V] ──(Red Wire)────> [VIN] MAX98357A 3.2W DAC    │
    │  [3V3]  ──(Red Wire)───────────> [SD/SD_MODE] MAX98357A      │
    │  [OPEN] ──(No Wire)────────────> [GAIN] MAX98357A (9 dB)     │
    │  [GND]  ──(Black Wire)─────────> [GND] MAX98357A             │
    │  [3V3]  ──(Red Wire)───────────> [VCC/VDD] SSD1306 OLED     │
    │  [3V3]  ──(Red Wire)───────────> [VDD] INMP441 Microphone    │
    │  [GND]  ──(Black Wire)─────────> Common Ground Rail (GND)    │
    │  [Verified 5V] ──(Red Wire)────> [5V] WS2812 LED Ring        │
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
