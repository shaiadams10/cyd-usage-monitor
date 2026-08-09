# Project Context

## Current State

CYD Usage Monitor is a self-hosted quota dashboard for the ESP32-2432S028R
Cheap Yellow Display. It collects usage snapshots through locally
authenticated Codex and Antigravity CLI panels, serves an Access-protected
public browser dashboard plus a separate private-LAN device API from
Python/Docker, and renders the selected account on physical and WebAssembly
LVGL displays.

The repository currently contains one self-contained project under
`cyd-usage-monitor/`. Project Brain Protocol v1.1.0 is initialized at the
repository root. Existing workspace and project-specific instructions remain
authoritative outside the managed Brain Protocol block.

## Recent Changes
<!-- Newest first. Max 10 entries. Oldest auto-compress to History Summary. -->

### 2026-08-09 — Restored LAN-only CYD and Wokwi Telemetry
- Replaced device-side Cloudflare HTTPS with short-timeout local HTTP to the
  monitor server's private RFC1918 address, removing CA, NTP, TLS, Access
  Service Auth, and the separate Wokwi build from the interaction path.
- Split the Python service into a Tunnel-only dashboard listener and a
  Bearer-protected device listener published only on the configured LAN
  interface; each listener returns `404` for the other surface's routes.
- Deployed the change to the operator-configured monitor server, retained a
  timestamped rollback copy, and measured warm LAN API responses around 20 ms.
- Removed the obsolete Cloudflare device ingress, DNS record, Access app, and
  dedicated service token while preserving the owner-only public dashboard.
- Updated the dashboard Flash tab and all setup, token, deployment, flashing,
  configuration, changelog, and architecture documentation. Cleaned revoked
  device/Tunnel credentials from ignored workstation configuration.
- Refreshed the curated dependency-free Graphify graph at 182 nodes, 392
  edges, and 14 communities across its 12-source-file scope.
- Files affected: `docs/context.md`, `docs/map.md`, and
  `cyd-usage-monitor/{.env.example,AGENTS.md,CHANGELOG.md,README.md,docker-compose.yml,`
  `include/secrets.h.example,instructions/DEPLOYMENT_RUNBOOK.md,`
  `instructions/FLASHING_GUIDE.md,instructions/TOKEN_GUIDE.md,platformio.ini,`
  `server/dashboard.html,server/server.py,server/test_server.py,src/main.cpp,`
  `wokwi.toml}`; deleted obsolete CA headers and TLS verification helper;
  ignored `.env` and `include/secrets.h` now contain only required local
  deployment/device values.

### 2026-08-09 — Persistent Wokwi HTTPS and Deliberate Touch Control
- Replaced the simulator's rotating leaf-certificate fingerprint with normal
  leaf signature, hostname, and validity checks against the narrower GTS WE1
  issuing CA. Physical firmware continues to trust GTS Root R4.
- Enabled HTTP/1.1 keep-alive end to end and retained the ESP32 secure client
  across polls, eliminating repeated TLS handshakes during normal operation.
- Changed the account-rotation API to return the newly selected CYD payload,
  so switching consumes one response without an immediate second request.
- Replaced whole-screen account switching with a visible top-right arrow
  button while preserving `n` and space as Wokwi serial shortcuts; updated the
  WebAssembly preview to match.
- Removed the obsolete pin-refresh helper and all certificate-rotation steps.
- Refreshed the curated dependency-free Graphify graph to 182 nodes, 392
  edges, and 14 communities across the same 12-source-file scope.
- Files affected: `docs/context.md`, `docs/map.md`, and
  `cyd-usage-monitor/{CHANGELOG.md,README.md,include/gts_we1.h,`
  `include/secrets.h.example,instructions/FLASHING_GUIDE.md,platformio.ini,`
  `scripts/verify-tls-chain.ps1,server/dashboard.html,server/server.py,server/test_server.py,`
  `simulator/lvgl_cyd_sim.c,src/main.cpp}`; deleted
  `cyd-usage-monitor/scripts/update-wokwi-tls-pin.ps1`; ignored
  `include/secrets.h` now selects the WE1 CA for Wokwi without changing private
  credentials.

### 2026-08-09 — Wokwi TLS Handshake Compatibility
- Identified mbedTLS `-0x0050` / decimal `-80` as a peer reset during the TLS
  handshake, after the earlier trust-anchor failure had already been fixed.
- Confirmed the live Cloudflare endpoint offers its ECDSA certificate path but
  not an RSA certificate to the tested TLS 1.2 client.
- Added a dedicated Wokwi PlatformIO target that completes encrypted TLS and
  verifies the exact live SHA-256 leaf fingerprint plus hostname before any
  Bearer or Cloudflare Access headers are attached. The physical target keeps
  full CA-chain and certificate-time validation.
- Added a safe pin-refresh helper, pointed `wokwi.toml` at the isolated target,
  suppressed startup touch transients, and updated the dashboard Flash tab and
  canonical provisioning documentation.
- Refreshed the curated dependency-free Graphify graph after the firmware
  change; it now covers 12 source files with 179 nodes, 389 edges, and 10
  communities.
- Files affected: `docs/context.md`, `docs/map.md`, and
  `cyd-usage-monitor/{CHANGELOG.md,README.md,include/secrets.h.example,`
  `instructions/FLASHING_GUIDE.md,platformio.ini,scripts/update-wokwi-tls-pin.ps1,`
  `server/dashboard.html,server/test_server.py,src/main.cpp,wokwi.toml}`; ignored
  `include/secrets.h` holds the refreshed deployment-specific public pin.

### 2026-08-09 — Cloudflare TLS Fix and CYD Flashing Guide
- Diagnosed Wokwi's X509 failure against the live Cloudflare edge chain and
  replaced the unrelated GlobalSign ECC root with the official Google Trust
  Services Root R4 trust anchor used by that chain.
- Added a credential-free OpenSSL verification helper, rebuilt the firmware,
  and confirmed the live device hostname validates against the included root.
- Assigned the independently wired touch controller to HSPI while retaining
  the TFT on VSPI, removing the duplicate APB callback registration at boot.
- Added a responsive dashboard Flash tab, a canonical provisioning guide, an
  admin-protected browser-readable documentation route, Docker packaging, and
  server regression coverage.
- Deployed the dashboard update to the configured remote monitor origin with a
  timestamped rollback copy, then verified container health, the Flash tab,
  the guide, and the externally protected device API.
- Refreshed the managed Brain Protocol block and regenerated the curated
  Graphify source graph after restoring its intended dependency-free scope.
- Files affected: `AGENTS.md`, `docs/context.md`, `docs/map.md`, and
  `cyd-usage-monitor/{Dockerfile,README.md,CHANGELOG.md,include/gts_root_r4.h,`
  `include/secrets.h.example,instructions/FLASHING_GUIDE.md,`
  `instructions/TOKEN_GUIDE.md,scripts/verify-tls-chain.ps1,server/dashboard.html,`
  `server/server.py,server/test_server.py}`; ignored `include/secrets.h` was
  updated with the public trust anchor while retaining private values.

### 2026-08-09 — Brain Protocol upgraded to v1.1.0
- Updated the managed Brain Protocol instructions in `AGENTS.md`
- Preserved project-specific content outside the managed protocol block
- Files affected: `AGENTS.md`, `docs/context.md`, `docs/map.md`

### 2026-08-09 — Wokwi HTTPS Timing and Diagnostics
- Replaced physical-device-oriented HTTPS and TLS timeouts with bounded values
  that accommodate Wokwi's slower CPU/network emulation while retaining CA
  certificate validation.
- Added credential-safe serial diagnostics that expose the underlying mbedTLS
  error when Arduino HTTPClient collapses transport failures into the generic
  `connection refused` message.
- Corrected the README's Wokwi networking guidance and documented how to use
  the serial diagnostics.
- Files affected: `cyd-usage-monitor/src/main.cpp`, `README.md`, and
  `CHANGELOG.md`.

### 2026-08-09 — Graphify Activated
- Generated a deterministic, source-only Graphify knowledge graph without an
  external or local language model.
- Analyzed 12 tracked C/C++, Python, and PowerShell source files while
  excluding generated assets, documentation, local secrets, and untracked
  files.
- Produced 175 nodes, 373 edges, and 13 communities in the ignored
  `graphify-out/` directory.
- Normalized generated source references to repository-relative paths and
  recorded the active graph in `docs/map.md`.

### 2026-08-09 — Secure Operator Runbook Added
- Added a public-safe runbook documenting the remote-only Tunnel boundary,
  Cloudflare-plus-Basic dashboard login, password retrieval and rotation,
  credential placement, deployment verification, rollback, and Git release
  checks.
- Kept the exact operator host and all real secrets exclusively in ignored
  configuration while linking the runbook from the project README.
- Files affected: `cyd-usage-monitor/instructions/DEPLOYMENT_RUNBOOK.md`,
  `README.md`, `CHANGELOG.md`, and `docs/map.md`.

### 2026-08-09 — Remote Tunnel Deployment Verified
- Deployed the hardened application, collector, and Cloudflare connector to
  the operator-confirmed remote Linux origin while preserving the existing
  dashboard password, telemetry state, CLI profiles, and a timestamped
  rollback copy.
- Migrated runtime state into a private data directory, removed the direct
  port 8000 listener, and restricted both data and CLI profile directories to
  the operator account.
- Verified layered device authentication (`403` without Access, `401` without
  the application token, `200` with both), route-limited ingress, owner-only
  dashboard redirection, live telemetry, and four healthy Tunnel connections.
- Recorded the exact deployment host and directory only in ignored `.env`;
  tracked files retain value-free placeholders suitable for the public repo.
- Files affected: `cyd-usage-monitor/.env.example`, `AGENTS.md`, and
  `README.md`; ignored `.env` and `include/secrets.h` hold operator/device
  configuration.

### 2026-08-09 — Cloudflare Tunnel and Access Deployment
- Added a pinned `cloudflared` service and moved the monitor application from
  host networking to a private Compose ingress network with no published port.
- Added separate Cloudflare Access protection for the human dashboard and CYD
  device API, including firmware service-token headers, trusted HTTPS CA
  validation, and bounded NTP synchronization.
- Created the operator's remotely managed Tunnel, route-limited ingress, DNS
  records, owner-only dashboard policy, and device-only Service Auth policy.
- Documented minimal API permissions, credential separation, deployment, and
  release hygiene. Real Tunnel and device credentials remain only in ignored
  `.env` and `include/secrets.h` files.
- Files affected: `cyd-usage-monitor/.env.example`, `docker-compose.yml`,
  `include/secrets.h.example`, `src/main.cpp`, `README.md`, `CHANGELOG.md`, and
  `instructions/TOKEN_GUIDE.md`.

## History Summary
<!-- Compressed summaries of older changes go here -->

- Project Brain Protocol v1.1.0 was initialized on 2026-08-09 with the
  discovered ESP32/Python/Docker architecture, build commands, repository
  map, context ledger, and preserved workspace policies.

## Next Steps
<!-- What should be worked on next? -->

*No application work is scheduled by the protocol setup.*

## Known Issues
<!-- Active bugs, tech debt, or blockers -->

*None identified during protocol setup.*
