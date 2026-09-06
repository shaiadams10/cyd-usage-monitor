# CYD Usage Monitor

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![PlatformIO](https://img.shields.io/badge/firmware-PlatformIO-orange.svg)](cyd-usage-monitor/platformio.ini)
[![ESP32](https://img.shields.io/badge/hardware-ESP32--2432S028R-red.svg)](cyd-usage-monitor/README.md#hardware--pin-mapping)

A self-hosted usage dashboard for the ESP32 Cheap Yellow Display. It collects
quota snapshots from locally authenticated OpenAI Codex and Google Antigravity
CLIs, adds OpenRouter credits and spend through its documented management API,
and displays the results in a protected browser dashboard and on a physical CYD.

![CYD Usage Monitor dashboard](docs/images/cyd-usage-monitor-dashboard.png)

## Highlights

- **Automatic account selection when you send a message:** local Codex Desktop
  submissions select the CYD profile mapped to the signed-in ChatGPT account,
  including steering messages during an active turn.
- **Antigravity message selection:** an event-driven Windows helper selects a
  configured primary profile on explicit user messages; assistant continuations
  do not reclaim the display.
- **Stream Deck controls:** cycle profiles or select a specific account with
  windowless buttons using the authenticated private device API.
- **Usage and credits:** separate Codex 5-hour and weekly quotas, Antigravity
  Gemini/Claude quota windows, and OpenRouter balance, spend, and daily history.
- **Animated display and browser preview:** shared LVGL transitions, quota bars,
  counters, launcher navigation, and persistent display orientation/state.
- **Outage notifications:** optional WhatsApp through WAHA with TLS SMTP email
  fallback, deduplication, and recovery alerts.
- **Private deployment:** isolated CLI profiles, protected dashboard, separate
  Bearer-authenticated LAN API, and hardened Docker Compose services.

## Set up message-based switching

The optional Windows integration follows the login used by **local Codex Desktop**.
It queries the official local `account/read` interface for each submission and
maps the normalized email hash to an existing CYD profile. Unknown or ambiguous
identities leave the display unchanged. Browser/mobile ChatGPT, remote tasks,
and externally managed app tokens are not supported.

Antigravity currently selects one configured primary profile; it does not discover
changes of Google login. Neither integration changes quota collection or makes
additional model requests. Windows helpers reject proxies and redirects and keep
credentials and mappings outside Git.

Use the **[fresh Windows setup and recovery guide](cyd-usage-monitor/instructions/CHAT_ACCOUNT_SWITCH_SETUP.md)**
for prerequisites, private settings, custom account labels, hook trust, startup,
troubleshooting, and account-switch/reboot acceptance checks. A new computer needs
those private settings restored separately; cloning this repository does not
restore credentials or personal account mappings.

## Architecture

```text
Codex /status + Antigravity /usage       OpenRouter documented API
                |                                  |
        isolated CLI collector ------------ normalized snapshots
                                                   |
                         +-------------------------+------------------+
                         |                                            |
                 protected dashboard                    authenticated private CYD API
                         |                                            |
                 LVGL browser preview                          physical CYD
                                                                      ^
                                         desktop messages / Stream Deck selection
```

Codex and Antigravity credentials remain inside their official server CLI profiles.
Only normalized usage is persisted for display. The optional OpenRouter Management
API key is stored separately in private runtime data and is used only for
read-only collection. See the [authentication and token guide](cyd-usage-monitor/instructions/TOKEN_GUIDE.md).

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
`CYD_API_TOKEN` of at least 24 characters. Configure the host CLI mounts and
Cloudflare Tunnel values before starting Compose. The dashboard listener is
Tunnel-only and protected by Cloudflare Access plus application authentication.
The separate device listener is bound to the operator's private LAN address;
never expose it through a public Tunnel or router port forward.

Create and authenticate each CLI account through the protected dashboard. Configure
OpenRouter separately if wanted. Set `CYD_MONITOR_TIMEZONE` for local reset times.
Follow the [deployment runbook](cyd-usage-monitor/instructions/DEPLOYMENT_RUNBOOK.md)
for the complete prerequisites, private configuration, and verification sequence.

### Firmware

Copy `cyd-usage-monitor/include/secrets.h.example` to the ignored
`cyd-usage-monitor/include/secrets.h`, then configure Wi-Fi, the private IPv4 HTTP
device endpoint, and the same `CYD_API_TOKEN` used by the server. Firmware accepts
only the private LAN device endpoint; the public HTTPS dashboard is a separate
surface. Check the [flashing guide](cyd-usage-monitor/instructions/FLASHING_GUIDE.md)
for board identification, pin configuration, backups, and upload precautions.

```sh
cd cyd-usage-monitor
pio run
pio run --target upload
```

See the [complete setup, security, hardware, and deployment guide](cyd-usage-monitor/README.md).

## Hardware

| Component | Model |
| --- | --- |
| Current target | E32R40T with ESP32-32E module |
| Display | 4.0-inch ST7796S, 320×480 (480×320 landscape) |
| Touch | XPT2046 resistive controller |
| Firmware | Arduino framework, LVGL 8, TFT_eSPI |

The historical `esp32-2432S028R` PlatformIO environment name is retained; verify
your actual board before flashing. Detailed pin assignments are documented in the
[project guide](cyd-usage-monitor/README.md#hardware--pin-mapping).

## Project layout

```text
cyd-usage-monitor/
├── src/          ESP32 firmware
├── include/      LVGL configuration and safe secrets template
├── server/       dashboard, API, collector, tests, and WASM assets
├── simulator/    shared LVGL WebAssembly simulator source and motion tests
├── scripts/      Windows message hooks, Stream Deck helpers, and tests
├── instructions/ setup, recovery, authentication, deployment, and flashing guides
├── .env.example  value-free server configuration template
└── README.md     complete operator and hardware guide
```

Real `.env` files, firmware secrets, CLI profiles, runtime snapshots, build
output, logs, and private keys are excluded from version control and Docker
build contexts.

## Development

```sh
python -m unittest discover -s cyd-usage-monitor/server
# On Windows:
python -m unittest discover -s cyd-usage-monitor/scripts -p "test_*.py"
cd cyd-usage-monitor
pio run
docker compose --env-file .env.example config --quiet
```

Dependencies are version-pinned, and the repository CI repeats the parser/API
tests, Windows helper security checks, Compose validation, container build,
firmware build, real LVGL motion tests, and WebAssembly rebuild/smoke checks. See [CONTRIBUTING.md](CONTRIBUTING.md) and
[SECURITY.md](SECURITY.md) before publishing changes.

## Documentation

- [Complete operator and hardware guide](cyd-usage-monitor/README.md)
- [New-computer message switching setup](cyd-usage-monitor/instructions/CHAT_ACCOUNT_SWITCH_SETUP.md)
- [Stream Deck account controls](cyd-usage-monitor/README.md#stream-deck-account-cycling)
- [Changelog](cyd-usage-monitor/CHANGELOG.md)

## License

Released under the widely used [MIT License](LICENSE). Provider names and the
project's unofficial display artwork are addressed separately in
[NOTICE.md](NOTICE.md); the project is independent and is not endorsed by the
named providers.
