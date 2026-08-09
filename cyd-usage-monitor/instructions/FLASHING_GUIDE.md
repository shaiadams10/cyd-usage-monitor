# Flashing a CYD Device

This guide provisions an ESP32-2432S028R Cheap Yellow Display. Build locally
because Wi-Fi and the device token are compiled from ignored
`include/secrets.h`. Never publish the configured firmware binary.

## What you need

- An ESP32-2432S028R CYD and USB data cable, or the Wokwi simulator.
- PlatformIO Core or VS Code with PlatformIO.
- The monitor server's private LAN IPv4 address and `CYD_API_TOKEN`.
- Wi-Fi that can reach the monitor server's LAN address.

## 1. Prepare private configuration

```powershell
Copy-Item include/secrets.h.example include/secrets.h
```

Edit only ignored `include/secrets.h`:

- Set `WIFI_SSID` and `WIFI_PASS`. Use `Wokwi-GUEST` and an empty password only
  for Wokwi.
- Set `TELEMETRY_SERVER_URL` to
  `http://<private-LAN-IPv4>:8001/api/v1/cyd-status`, using the actual port
  from the server's ignored `.env`.
- Set `TELEMETRY_API_TOKEN` to the server's `CYD_API_TOKEN`.

Only literal RFC1918 addresses are accepted. This prevents an accidental
public destination from receiving the reusable token. Do not forward the LAN
port through a router or expose it through Cloudflare.

## 2. Build and flash a physical CYD

```powershell
pio device list
pio run -e esp32-2432S028R
pio run -e esp32-2432S028R --target upload --upload-port COM5
pio device monitor --baud 115200 --port COM5
```

Replace `COM5` with the detected data port. If upload does not begin, hold BOOT
while writing starts. A working device connects to Wi-Fi, completes a quick
LAN request, and shows the selected account. HTTP `401` means the Bearer token
does not match; `[NET]` generally means the LAN address or port is unreachable.

## Wokwi verification

Wokwi uses the same build:

```powershell
pio run -e esp32-2432S028R
```

Restart Wokwi after building so `wokwi.toml` reloads the binary. Wokwi must be
running with its private IoT gateway so `Wokwi-GUEST` can reach the local LAN.
Tap only the top-right arrow to switch accounts; `n` and space remain serial
shortcuts. Status polls and switches stay on local HTTP and do not perform TLS
or Cloudflare Access handshakes.

## Related documentation

- `README.md` — architecture and setup.
- `instructions/TOKEN_GUIDE.md` — credential boundaries and rotation.
- `instructions/DEPLOYMENT_RUNBOOK.md` — server deployment and verification.
- `AGENTS.md` and `../docs/context.md` — maintenance contract and current state.
