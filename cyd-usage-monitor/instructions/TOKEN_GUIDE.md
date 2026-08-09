# Authentication and Token Guide

Do not copy browser cookies, OAuth refresh tokens, `auth.json`, `adc.json`, or
provider client secrets into this project. Use the protected dashboard to
create an isolated Codex or Antigravity profile, then complete the official
CLI's browser or device-code flow. Provider credentials remain in the private
profile directory on the monitor server.

## Credential boundaries

- `CLOUDFLARE_TUNNEL_TOKEN` belongs only in the ignored `.env` on the monitor
  server. It exposes the browser dashboard, not the device API.
- `MONITOR_ADMIN_PASSWORD` protects the dashboard behind Cloudflare Access.
- `CYD_API_TOKEN` is the independent application token shared by the server
  and firmware. Use at least 24 random characters.
- `CLOUDFLARE_API_TOKEN` is optional provisioning-only configuration. Keep it
  out of containers and revoke it after setup when it is no longer required.

The firmware has no Cloudflare Access token and no provider credential. Its
endpoint must be an HTTP URL containing a literal RFC1918 IPv4 address. The
firmware refuses public addresses and hostnames before attaching the Bearer
token. The server publishes that API only on its configured private LAN
address, and its public dashboard listener returns `404` for device routes.

Never forward the device port through a router, Cloudflare Tunnel, or public
reverse proxy. Use a trusted LAN; other devices on that LAN can observe plain
HTTP traffic. Rotate `CYD_API_TOKEN` and rebuild trusted devices if a configured
device or firmware binary is lost or distributed.

Never publish a firmware binary built with real Wi-Fi or device credentials.
Follow `instructions/FLASHING_GUIDE.md`; the dashboard's **Flash** tab links to
the same admin-protected guide.
