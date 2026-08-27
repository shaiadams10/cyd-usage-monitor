# ESP32-S3 Home Assistant Voice Satellite Carrier

This directory contains a code-defined tscircuit carrier PCB for the working
ESPHome voice satellite. It sockets the existing modules instead of replacing
them with bare ICs.

## Current status

The electrical source now passes local TypeScript, netlist, schematic
placement, PCB placement, autorouting, and Gerber-derived copper-short checks.
The generated Gerber archive includes copper, masks, silkscreens, drills, a BOM,
and pick-and-place CSV.

**Do not order the PCB yet.** The supplied AliExpress listings now identify the
microphone, amplifier, OLED, speaker, and LED-ring product families. The round
microphone footprint has been corrected from the former generic 1x6 placeholder
to the purchased 14 mm, 2x3-pin layout. The exact ordered SKU options, component
heights, and the exact ESP32-S3 board are still not encoded by those URLs. The
present 3D export models the carrier and standard footprints, not the complete
socketed assembly, so it is not yet a valid enclosure model.

## Local-only tool installation

No global tscircuit install is required or supported. The CLI, evaluator, and
TypeScript compiler are exact-version development dependencies in this
directory and are locked by `package-lock.json`.

```powershell
Set-Location esp32s3-home-assistant\circuit
npm ci
npm run validate
npm run dev
```

Use `npm run ...` so the executable always comes from `node_modules/.bin` in
this project. `npm audit --omit=dev` currently reports zero runtime
vulnerabilities. The toolchain's development dependency tree reports 10
transitive advisories (7 moderate and 3 high); do not run a forced audit fix
because that can silently change PCB generation behavior.

## Electrical connections

| Module | Carrier connection |
| --- | --- |
| ESP32-S3-DevKitC-1 | Official v1.0/v1.1 2x22 mapping, 22.86 mm header-row spacing |
| INMP441 | 3.3 V, GND, SD GPIO7, SCK GPIO15, WS GPIO16, L/R to GND |
| MAX98357A | 5 V, GND, DIN GPIO8, BCLK GPIO17, LRC GPIO18, GAIN to GND |
| SSD1306 I2C OLED | 3.3 V, GND, SCL GPIO5, SDA GPIO6 |
| WS2812 ring | Peripheral 5 V, GND, GPIO4 through 330 ohm series resistor |

The MAX98357A speaker connects to the breakout's own `SPK+` and `SPK-`
terminal. Its output is bridge-tied: neither speaker lead may be connected to
ground.

The 5 V peripheral routes are 1.0 mm and the ground routes are 0.8 mm. A
470 uF radial electrolytic footprint is placed on the ring/amplifier rail. The
capacitor is polarized; verify its marked negative lead before soldering.

## Power selector

`J_PWR_SEL` accepts one standard 2-pin shunt:

- Pins 1-2: the DevKit USB/5 V rail powers the amplifier and LED ring.
- Pins 2-3: `J_PWR` powers the amplifier and ring from an external regulated
  5 V supply. The DevKit remains separately USB-powered.

Install exactly one shunt position. The external rail intentionally does not
feed the DevKit, which prevents it from back-feeding a connected USB host.
All supplies share carrier ground. Use external mode for high LED brightness or
high speaker volume; size the regulated supply for the measured load.

## Mechanical assumptions that must be verified

### Confirmed from the supplied listings

| Part | Confirmed listing data | Carrier consequence |
| --- | --- | --- |
| HZWDONE INMP441 | 14 x 14 mm round PCB; two 3-pin rows labeled `SD VDD GND` / `L/R WS SCK` | Exact 2x3 socket, outline, and courtyard are now modeled; the module intentionally overhangs the left carrier edge for clearance and acoustic access. |
| MAX98357/MAX98357A | 18.7 x 17.7 mm breakout; 7-pin `LRC BCLK DIN GAIN SD VIN GND`; onboard bridge-tied speaker terminal | Electrical header order matches. Full body, terminal height, and mounting-hole geometry still need to be added to the assembly model. |
| SSD1306 OLED | 0.96-inch, 128 x 64; 27.5 x 27.8 mm nominal PCB drawing; `GND VCC SCL SDA` at 2.54 mm pitch | Electrical header order matches. Display height, exact mounting-hole centers, and viewing-window offset still need physical verification. |
| Box speaker | 25 x 35 mm; listing offers 4 ohm/3 W and 8 ohm/2 W; 1.25 mm plug and approximately 165 mm lead | Off-board enclosure part; connect only across the amplifier's `SPK+`/`SPK-` bridge output. Confirm the ordered impedance and thickness. |
| WS2812B/SK6812 ring | Seller chart gives the 12-pixel ring a 52 mm outside diameter; the fitted module photo confirms 12 pixels | Remains off-board through the protected 3-wire connector. Confirm connector/no-connector SKU and ring thickness before case CAD. |

AliExpress item links identify a product listing but do not contain the ordered
SKU identifier. Consequently, options such as speaker impedance, OLED color,
and LED-ring connector choice cannot be proven from the URL alone.

The source currently assumes:

- official Espressif DevKitC-1 dimensions of 25.40 x 62.74 mm;
- 22.86 mm between the two DevKit header-row centers;
- 2.54 mm pitch on the socketed breakout headers;
- a 50 x 70 mm carrier with four 3.2 mm mounting holes at
  `(±21.5 mm, ±31.5 mm)`;
- the exact pin order printed in each component source file.

Before ordering, identify the exact ESP32-S3 board and read the option names from
the AliExpress order details. Measure only the dimensions the listings omit:
component height, header-to-edge offsets, connector direction, OLED viewing
window, USB plug clearance, speaker thickness/wire exit, and LED-ring thickness
and mounting geometry. Then add the remaining courtyards/keepouts and STEP
models.

## Validation and exports

```powershell
npm run validate
npm run export:all
```

`validate` runs type checking, netlist validation, schematic-placement checks,
PCB-placement checks, a full autorouted build, and the copper-short detector.
Unused DevKit breakout pins and the MAX98357A module's default-managed SD/MODE
pin are intentionally unconnected.

Generated artifacts are ignored under `dist/`:

| Artifact | Purpose |
| --- | --- |
| `dist/gerbers.zip` | Gerber/drill files plus BOM and pick-and-place CSV |
| `dist/kicad.zip` | Independent KiCad review and final manufacturer DRC |
| `dist/pcb.svg` | Routed two-layer carrier review |
| `dist/schematic.svg` | Human-readable schematic |
| `dist/carrier_board.glb` | Preliminary carrier-only 3D reference |

The radial capacitor STEP model is not currently available from tscircuit's
model CDN, so the KiCad/GLB exports may omit that body even though its pads and
drill holes are present.

## Recommended route to a finished enclosure

1. Verify every physical module and connector against the assumptions above.
2. Update tscircuit courtyards, keepouts, labels, and exact part numbers.
3. Open the exported KiCad project and run KiCad DRC plus a 1:1 paper fit test.
4. Order a small unassembled prototype batch and perform continuity checks
   before inserting any modules.
5. Populate and bench-test USB power first, then external peripheral power.
6. Import verified STEP models into FreeCAD or Fusion 360 and design the case
   around the complete assembly, microphone acoustic opening, speaker chamber,
   OLED window, ring diffuser, USB access, ventilation, and mounting bosses.

Tscircuit remains the source of truth for the carrier. KiCad is the independent
manufacturing review layer, and a mechanical CAD tool should own the final case.
