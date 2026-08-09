# CYD Usage Monitor

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![PlatformIO](https://img.shields.io/badge/firmware-PlatformIO-orange.svg)](cyd-usage-monitor/platformio.ini)
[![ESP32](https://img.shields.io/badge/hardware-ESP32--2432S028R-red.svg)](cyd-usage-monitor/README.md#hardware)

A self-hosted usage dashboard for the ESP32 Cheap Yellow Display. It collects
quota snapshots from locally authenticated OpenAI Codex and Google Antigravity
CLIs, renders them in a browser dashboard, and keeps the selected account
visible on a physical 320×240 CYD screen.

![CYD Usage Monitor dashboard](docs/images/cyd-usage-monitor-dashboard.png)

## Highlights

- Multiple isolated Codex and Antigravity CLI profiles
- Live quota cards for Codex, Gemini, and Claude usage windows
- A browser-based LVGL/WebAssembly preview matching the physical display
- Fast profile switching from the dashboard, touchscreen, or serial input
- Optional WhatsApp outage and recovery alerts through WAHA
- Hardened Docker Compose deployment with configurable, private host mounts
- Process-safe local state and isolated, least-privilege CLI subprocesses
- No provider tokens, browser cookies, or private provider APIs in the app

## Architecture

```text
Codex /status + Antigravity /usage
                 │
       isolated CLI collector
                 │
       normalized local snapshot
          ┌──────┴──────┐
          │             │
  protected dashboard   authenticated CYD API
          │             │
  LVGL browser preview  ESP32-2432S028R
```

Provider authentication remains inside each official CLI profile. The
collector parses only the quota panels those CLIs display and writes a small
normalized snapshot for the dashboard and device.

## Quick start

### Server

Requirements: a private Linux host, Docker Compose, and host-installed Codex
and Antigravity CLIs.

```sh
cd cyd-usage-monitor
cp .env.example .env
# Fill in the private values and host CLI paths in .env.
docker compose up -d --build
```

Use a unique `MONITOR_ADMIN_PASSWORD` of at least 16 characters and a random
`CYD_API_TOKEN` of at least 24 characters. Keep port 8000 on a private network
or place it behind a TLS reverse proxy; HTTP Basic authentication must not be
exposed over plaintext internet traffic. Administrative writes additionally
require the dashboard's custom CSRF header, and temporary CLI sign-in material
is stored in a private one-time inbox and scrubbed after use.

### Firmware

Copy `cyd-usage-monitor/include/secrets.h.example` to the ignored
`cyd-usage-monitor/include/secrets.h`, then configure Wi-Fi, the private
monitor URL, the server's trusted CA certificate, and the same `CYD_API_TOKEN`
used by the server. Plain HTTP is rejected unless the explicit development-only
opt-in is enabled; use HTTPS for real deployments.

```sh
cd cyd-usage-monitor
pio run
pio run --target upload
```

See the [complete setup, security, hardware, and deployment guide](cyd-usage-monitor/README.md).

## Hardware

| Component | Model |
| --- | --- |
| Board | ESP32-2432S028R Cheap Yellow Display |
| Display | 2.8-inch ILI9341, 320×240 |
| Touch | XPT2046 resistive controller |
| Firmware | Arduino framework, LVGL 8, TFT_eSPI |

Detailed pin assignments are documented in the
[project guide](cyd-usage-monitor/README.md#hardware).

## Project layout

```text
cyd-usage-monitor/
├── src/          ESP32 firmware
├── include/      LVGL configuration and safe secrets template
├── server/       dashboard, API, collector, tests, and WASM assets
├── simulator/    shared LVGL WebAssembly simulator source
├── .env.example  value-free server configuration template
└── README.md     complete operator and hardware guide
```

Real `.env` files, firmware secrets, CLI profiles, runtime snapshots, build
output, logs, and private keys are excluded from version control and Docker
build contexts.

## Development

```sh
python -m unittest discover -s cyd-usage-monitor/server
cd cyd-usage-monitor
pio run
docker compose --env-file .env.example config --quiet
```

Dependencies are version-pinned, and the repository CI repeats the parser/API
tests, Compose validation, container build, firmware build, and deterministic
WebAssembly rebuild. See [CONTRIBUTING.md](CONTRIBUTING.md) and
[SECURITY.md](SECURITY.md) before publishing changes.

## License

Released under the widely used [MIT License](LICENSE). Provider names and the
project's unofficial display artwork are addressed separately in
[NOTICE.md](NOTICE.md); the project is independent and is not endorsed by the
named providers.
