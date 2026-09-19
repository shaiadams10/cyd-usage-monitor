# Authentication and Token Guide

Do not copy browser cookies, OAuth refresh tokens, `auth.json`, `adc.json`, or
provider client secrets into this project. Use the protected dashboard to
create an isolated Codex or Antigravity profile, then complete the official
CLI's browser or device-code flow. Provider credentials remain in the private
profile directory on the monitor server.

OpenRouter is the documented exception to CLI-only collection. Create a
dedicated Management API key in OpenRouter, paste it into the protected
dashboard's **Accounts / OpenRouter account** form, and clear it from your
clipboard. The server stores it in ignored runtime data with mode `0600`; it is
never returned to the browser, firmware, device API, logs, or CLI processes.
Use **Remove OpenRouter** to delete both the saved key and normalized snapshot.
The integration calls only the documented credits, key-list, and activity read
endpoints and never creates, changes, or deletes an OpenRouter key.

## Credential boundaries

Optional Windows message hooks use the official local Codex `account/read`
operation solely to identify the signed-in managed ChatGPT account. They do
not refresh tokens, read credential files, collect quota, or call private
provider endpoints. This requires the desktop and local client to share the
configured Codex authentication home. Email hashes and CYD profile mappings
stay in `%USERPROFILE%\.cyd-usage-monitor\chat-switch.json`; the existing Windows
user `CYD_API_TOKEN` is read at request time and is never copied into hook files.
Antigravity currently uses one configured profile, without reading its account
credentials. Keep all hook configuration, mappings, and backups outside Git.

- `CLOUDFLARE_TUNNEL_TOKEN` belongs only in the ignored `.env` on the monitor
  server. It exposes the browser dashboard, not the device API.
- `MONITOR_ADMIN_PASSWORD` protects the dashboard behind Cloudflare Access.
- `CYD_API_TOKEN` is the independent application token shared by the server
  and firmware. Use at least 24 random characters.
- `CLOUDFLARE_API_TOKEN` is optional provisioning-only configuration. Keep it
  out of containers and revoke it after setup when it is no longer required.
- The OpenRouter Management API key belongs only in the private Compose data
  directory after dashboard setup. Treat it as high-value because management
  keys can administer other keys even though this monitor is read-only.
- Optional `CYD_MONITOR_SMTP_USERNAME` and `CYD_MONITOR_SMTP_PASSWORD` belong
  only in the ignored server `.env`. Use a dedicated SMTP credential or app
  password with permission to send only from the configured monitor address.
  SMTP credentials are not stored in dashboard state and are not passed to
  Codex or Antigravity child processes.

The protected **Alerts → Email integration** form is the easier alternative to
environment variables. Gmail mode accepts a Google/Workspace address and a
revocable app password; custom mode accepts a transactional provider's TLS
SMTP endpoint and API credential. The secret is stored in
`email-secret.json` inside the private data volume with mode `0600`; only the
provider, sender, recipient, host, port, and configured state are returned to
the authenticated dashboard. The password and SMTP username are never returned.
Host environment SMTP variables take precedence and make the dashboard form
read-only until those variables are removed.

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
Follow `instructions/FLASHING_GUIDE.md`; the dashboard's **Utilities** tab links to
the same admin-protected guide.
