# CYD CLI Usage Monitor

An ESP32 Cheap Yellow Display (ESP32-2432S028R) that displays usage snapshots
from locally authenticated OpenAI Codex and Google Antigravity CLIs. A small
Docker-hosted dashboard manages isolated CLI profiles and serves the CYD API.

![CYD Usage Monitor dashboard](../docs/images/cyd-usage-monitor-dashboard.png)

## How it works

```text
Codex /status + Antigravity /usage
                 |
     collector (isolated CLI profiles)
                 |
       normalized telemetry snapshot
           |                 |
   authenticated CYD API   protected dashboard
           |
     ESP32-2432S028R display
```

The collector reads only the CLIs' visible quota panels. It does not copy
browser cookies, `auth.json`, refresh tokens, or provider credentials, and it
does not call private provider HTTP APIs.

## Hardware

| Peripheral | Pins |
| --- | --- |
| ILI9341 display | MOSI 13, MISO 12, SCK 14, CS 15, DC 2, backlight 21 |
| XPT2046 touch | CS 33, IRQ 36, MOSI 32, MISO 39, CLK 25 |
| RGB LED | red 4, green 16, blue 17 |

## Security model

- The dashboard uses HTTP Basic authentication. Set a long, unique
  `MONITOR_ADMIN_PASSWORD`; if it is absent, the service generates a password
  on first start and stores it only in the private data directory.
- `CYD_API_TOKEN` is required. The firmware and server must use the same
  value and it must contain at least 24 characters; requests without it
  receive `401 Unauthorized`.
- Dashboard writes require JSON plus a browser-only verification header. The
  physical CYD endpoint remains Bearer-only, while the browser preview uses a
  separate Basic-authenticated endpoint.
- Provider authorization input is consumed from a private one-time inbox. It
  is never included in dashboard status responses, and temporary login URLs,
  device codes, and transcripts are scrubbed when a workflow ends.
- Run the service on a private network, or place it behind a TLS-terminating
  reverse proxy with firewall rules. Do not expose port 8000 directly to the
  public internet because Basic authentication requires HTTPS in transit.
- Keep the Compose data directory and CLI profile directory private. They may
  contain dashboard state, CLI credentials, and account usage data.
- Optional WAHA alert credentials remain only in `.env`; the dashboard never
  returns the API key, and provider CLI child processes do not inherit it.
- Removing an account queues deletion of its complete isolated CLI credential
  directory in addition to removing monitor telemetry.

## Setup

### 1. Configure the server

Install Docker Compose, the Codex CLI, and the Antigravity CLI on a private
Linux host. Clone this repository, then copy the example configuration:

```sh
cd cyd-usage-monitor
cp .env.example .env
```

Set all of the following in the private `.env` file:

- `MONITOR_ADMIN_PASSWORD` — a unique password of at least 16 characters.
- `CYD_API_TOKEN` — a random shared device token of at least 24 characters.
- `AGY_HOST_PATH`, `CODEX_HOST_DIR`, and `NODE_BIN_HOST_DIR` — absolute paths
  to the host-installed CLI executable/installations.
- Optional WAHA settings if WhatsApp alerts are required.

`CYD_MONITOR_HOST_DATA_DIR` and `CYD_MONITOR_HOST_PROFILE_DIR` default to
ignored `./data` and `./profiles` directories. Assign a non-root
`CYD_MONITOR_UID` and `CYD_MONITOR_GID` if Docker must write files as a
specific host user.

Start the services:

```sh
docker compose up -d --build
docker compose ps
```

The Compose services run read-only, drop Linux capabilities, enable
`no-new-privileges`, and use bounded PID and temporary-filesystem resources.
The app listens on port 8000. Visit the private HTTPS endpoint through your
reverse proxy, sign in as `admin`, create an account profile, and complete the
CLI login flow. The collector stores each CLI profile in its isolated private
directory and polls usage every 90 seconds by default.

### 2. Configure the CYD firmware

Copy `include/secrets.h.example` to the ignored `include/secrets.h`, then set
your monitor's private HTTPS URL, its validating PEM CA certificate, and the
same `CYD_API_TOKEN` used by the server. HTTPS fails closed if the CA is empty.
Plain HTTP exposes the reusable device token and is disabled unless
`TELEMETRY_ALLOW_INSECURE_HTTP` is explicitly set to `1`; use that override
only on an isolated, trusted LAN.
The ESP32 holds only the monitor endpoint and its device token—not provider
credentials.

Build and upload with PlatformIO:

```sh
pio run
pio run --target upload
```

The build uses Espressif's standard `min_spiffs` partition table. This retains
two OTA-capable application slots while giving the LVGL firmware substantially
more room than the default layout; the monitor does not use SPIFFS.

### 3. Optional local UI preview

The dashboard includes an LVGL WebAssembly preview built from the shared CYD
visual assets. Rebuild it after changing `simulator/lvgl_cyd_sim.c`:

```powershell
.\simulator\build-wasm.ps1
```

The simulator build requires Emscripten 3.1.74. Set `EMSDK_ROOT` when emsdk is
not installed under the default per-user `.tools/emsdk` directory.

`diagram.json` and `wokwi.toml` support optional Wokwi firmware simulation.
The simulator models the display UI; it does not emulate Wi-Fi, touch, or
ESP32 peripherals.

## Optional WAHA alerts

The collector can send one WhatsApp alert when a profile first fails and one
recovery message after the next successful collection. Set `WAHA_URL`,
`WAHA_API_KEY`, `WAHA_SESSION`, and `WAHA_ALERT_CHAT_ID` in the private `.env`
file. The dashboard stores only the group routing ID; it never exposes the
WAHA API key.

## Development checks

```sh
python -m unittest discover -s server -v
pio run
```

For server changes, also start the stack with a private test configuration and
verify an authenticated dashboard request plus a CYD API request with a valid
Bearer token.

## Repository hygiene

Tracked source and configuration contain no real credentials, personal
endpoints, routing IDs, or operator account data. The promotional screenshot
uses illustrative account labels. Do not commit `.env`, `include/secrets.h`, `data/`,
`profiles/`, generated build output, or private keys. See `AGENTS.md` and
`instructions/TOKEN_GUIDE.md` for the project maintenance and authentication
rules.

Pinned PlatformIO, library, Docker, and Emscripten versions make local and CI
builds repeatable. GitHub CI runs server/API tests, Compose and Docker checks,
the firmware build, and a clean WebAssembly regeneration with JavaScript syntax
and exported-ABI smoke checks. Tests keep all
runtime state in temporary directories so clean Linux and Windows runners do
not depend on host paths or permissions. Simulator sources are sorted and
path-normalized before compilation; generated binaries can still differ between
operating-system toolchain environments while remaining functionally equivalent.

Provider names belong to their respective owners. The tiny RGB565 pictures are
unofficial project-created compatibility artwork; see the repository
[`NOTICE.md`](../NOTICE.md) for the non-endorsement and trademark notice.

## License

This project is released under the repository's
[MIT License](../LICENSE).
