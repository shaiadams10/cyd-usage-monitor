# Project Context

## Current State

CYD Usage Monitor is a self-hosted quota dashboard for the ESP32-2432S028R
Cheap Yellow Display. It collects usage snapshots through locally authenticated
Codex and Antigravity CLI panels plus OpenRouter's documented management API,
serves an Access-protected dashboard and separate private-LAN device API, and
renders normalized usage on physical and WebAssembly LVGL displays.

The device now boots into a two-app pastel launcher. Usage Monitor displays the
selected Codex or Antigravity profile, while OpenRouter independently displays
account credits, period spend, seven completed days, and the top model. Both
apps use scoped LAN polling, Home navigation, and matching WebAssembly behavior.

The repository currently contains one self-contained project under
`cyd-usage-monitor/`. Project Brain Protocol v1.1.0 is initialized at the
repository root. Existing workspace and project-specific instructions remain
authoritative outside the managed Brain Protocol block.

## Recent Changes

### 2026-09-06 — CYD Desktop Switching and Public Release
- CI follow-up: isolated all collector test paths and inherited notification
  credentials after clean Linux exposed two accidental production-path reads.
  Files: cyd-usage-monitor/{server/test_collector.py,README.md,CHANGELOG.md}.
- Added per-submission managed Codex identity mapping, an event-driven Antigravity
  primary-profile selector, recovery instructions, and private diagnostics.
- Added stable account selection/discovery, timezone propagation, email fallback,
  persisted display controls, shared animated LVGL and responsive firmware I/O.
- Hardened Windows helper transport against redirects, proxies, malformed endpoints
  and automatic Windows authentication; private configuration stays outside Git.
- Release is based directly on upstream main and excludes unrelated local projects
  and unpublished mixed-project commits. No provider credentials are included.
- Validation: 51 server and 15 Windows helper tests passed; firmware build,
  real LVGL motion tests, production WASM and dashboard syntax passed.
  Gitleaks history/release scans and private-value/binary checks found no leaks.
- CI now runs Windows helper and real LVGL motion checks; affected workflow:
  .github/workflows/ci.yml.
- Files: cyd-usage-monitor source, tests, configuration examples, generated WASM,
  scripts and documentation; docs/{context.md,map.md}.

<!-- Newest first. Max 10 entries. Oldest auto-compress to History Summary. -->

### 2026-08-11 — Debounced Transient CLI Failure Alerts
- Correlated six Antigravity alert/recovery pairs with isolated incomplete CLI
  captures: temporary authentication prompts and upstream
  `RESOURCE_EXHAUSTED` eligibility responses. Most recovered on the next poll;
  one timestamp pair indicates two failed polls before recovery.
- Changed WhatsApp outage detection to require three consecutive failed CLI
  collections by default, configurable from 1–10, while preserving every
  failed capture and recovery in protected incident history.
- Fixed recovery duration reporting to measure from the first failed capture
  rather than the most recent failed poll, and added the confirmation count to
  failure messages.
- Added regression coverage for silent transient recovery, confirmed outage
  transitions, durable deduplication state, incident counts, and full duration.
- Deployed the change to the operator-configured live host with a timestamped
  source rollback; verified the exact collector hash, threshold, container and
  Tunnel health, private device authentication/route isolation, preserved CLI
  profiles and telemetry, and clean collector startup logs.
- Files affected: `docs/{context.md,map.md}` and
  `cyd-usage-monitor/{.env.example,CHANGELOG.md,README.md,docker-compose.yml,`
  `server/collector.py,server/test_collector.py}`.

### 2026-08-09 — Collector Incident Diagnostics and WhatsApp Alerts
- Diagnosed the 20:53 Antigravity alert as one transient incomplete `/usage`
  capture followed by a normal successful scheduled poll; no reconnect,
  credential update, profile rewrite, or container restart repaired it.
- Added bounded structured incident history, redacted host-only evidence files,
  diagnostic IDs, capture facts, repeated failure counts, recovery durations,
  and a protected dashboard incident timeline.
- Redesigned test/failure/recovery WhatsApp messages with formatting, emojis,
  configurable local timestamps, evidence, automatic retry behavior, and an
  explicit statement of what did—or did not—change during recovery.
- Refreshed the dependency-free 12-file Graphify source graph to 248 nodes,
  536 edges, and 10 communities.
- Files affected: `docs/{context.md,map.md}` and
  `cyd-usage-monitor/{.env.example,CHANGELOG.md,README.md,docker-compose.yml,server/collector.py,`
  `server/dashboard.html,server/server.py,server/test_collector.py,`
  `server/test_server.py}`.

### 2026-08-09 — Python 3.14 Production Container
- Updated the pinned production image from Python 3.11.15 to Python 3.14.0 on
  Debian Bookworm while retaining the complete current application.
- Verified the server regression suite and container imports/startup against
  the upgraded runtime before merging the Dependabot update.
- Updated the README, changelog, and codebase map for the runtime change.
- Files affected: `docs/{context.md,map.md}` and
  `cyd-usage-monitor/{Dockerfile,CHANGELOG.md,README.md}`.

### 2026-08-09 — Stable WebAssembly ABI CI Check
- Replaced the CI smoke test's brittle minified raw WASM export letters with
  semantic module-export validation through the generated Emscripten wrapper.
- Verified all eight public simulator functions and initialized the module in
  Node after a clean pinned-toolchain rebuild.
- Updated the README and changelog to document the stable ABI verification.
- Files affected: `.github/workflows/ci.yml`, `docs/{context.md,map.md}`, and
  `cyd-usage-monitor/{CHANGELOG.md,README.md}`.

### 2026-08-09 — Browser Usage Controls and Account Actions
- Restored Usage Monitor pointer interaction in the WebAssembly preview by
  placing its full-screen Antigravity content behind Home and Next controls.
- Connected the preview's Next button to the dashboard's active-profile
  selection and verified launcher, Home, and account rotation in a real browser.
- Kept all four isolated CLI profile actions on one row, removed the redundant
  green connected/quota line, and moved OpenRouter removal into a compact card
  header control.
- Rebuilt and deployed the dashboard and WASM assets with a timestamped remote
  rollback; verified healthy services, exact live asset hashes, route protection,
  and Cloudflare Access.
- Refreshed the curated 12-file source graph to 234 nodes, 502 edges, and 9
  communities without dependency caches or generated assets.
- Files affected: `docs/{context.md,map.md}` and
  `cyd-usage-monitor/{CHANGELOG.md,README.md,server/dashboard.html,`
  `server/static/lvgl/{cyd_lvgl.js,cyd_lvgl.wasm},server/test_server.py,`
  `simulator/lvgl_cyd_sim.c}`.

### 2026-08-09 — OpenRouter Credits and Usage App
- Added a second launcher app for account-wide OpenRouter credits and spend,
  including a balance arc, period cards, seven-day chart, top model, Home
  navigation, and `O` shortcut on physical and WebAssembly LVGL.
- Added dashboard-managed mode-`0600` Management API key storage, official
  read-only credits/keys/activity collection, cached normalized telemetry,
  route-isolated APIs, protected setup/removal, and dashboard overview status.
- Added aggregation, pagination, failure, secret-boundary, stale-state, route,
  build, and interactive 320×240 visual/touch verification.
- Deployed the server, collector, dashboard, and WebAssembly assets to the
  configured monitor host with a timestamped rollback archive; verified the
  protected setup form, isolated admin/device APIs, healthy services, and
  Cloudflare Access boundary while preserving private runtime state.
- Updated provider security contracts and operator documentation for the
  documented OpenRouter API exception.
- Files affected: `AGENTS.md`, `docs/{context.md,map.md}`, and the OpenRouter
  collector/server/tests, dashboard/WASM, firmware/LVGL, README, changelog,
  token guide, and project contract under `cyd-usage-monitor/`.

### 2026-08-09 — Wokwi Touch Keybinds and Utilities
- Added semantic Wokwi Serial Monitor shortcuts that route through the same
  navigation and account-action requests as touchscreen controls: `U` opens
  Usage Monitor, `H` returns Home, `N` advances accounts, and `?` prints help.
- Renamed the protected dashboard Flash tab to Utilities and added a matching
  keyboard cheat sheet while preserving the secure flashing workflow.
- Reworked the dashboard preview container so it remains in a wider right rail
  at normal desktop widths and scales the logical 320×240 canvas to 340×255.
- Compacted only the WebAssembly Antigravity grid to add explicit right and
  bottom gutters; the physical CYD layout remains unchanged.
- Deployed the refreshed dashboard and WebAssembly assets to the configured
  monitor host after creating a timestamped remote rollback copy; preserved
  telemetry data, CLI profiles, collector state, and Tunnel configuration.
- Updated dashboard regression coverage and operator documentation.
- Refreshed the curated dependency-free Graphify graph across 12 source files
  to 208 nodes, 437 edges, and 9 communities.
- Files affected: `docs/context.md`, `docs/map.md`, and
  `cyd-usage-monitor/{CHANGELOG.md,README.md,instructions/TOKEN_GUIDE.md,server/dashboard.html,`
  `server/static/lvgl/cyd_lvgl.js,server/static/lvgl/cyd_lvgl.wasm,server/test_server.py,`
  `simulator/lvgl_cyd_sim.c,src/main.cpp}`.

### 2026-08-09 — Pastel CYD App Launcher
- Created and remotely pushed a public-safe pre-launcher checkpoint, plus a
  verified local Git bundle and ACL-protected hash-manifested snapshot of
  ignored configuration and local project state.
- Added a pastel `CYD Apps` boot launcher with a reusable app descriptor, a
  compact Canvas-drawn usage gauge, press/entry/screen animations, connection
  status, and the existing Usage Monitor as its first app.
- Made Wi-Fi startup non-blocking, scoped telemetry polling/account actions to
  Usage Monitor, added Home navigation, and replaced the fixed touch delay with
  a stable-release latch.
- Mirrored launcher and Home navigation in WebAssembly, added pointer input to
  the dashboard canvas, and visually verified both navigation directions.
- Refreshed the curated dependency-free Graphify graph across its 12 tracked
  source files to 207 nodes, 434 edges, and 9 communities.
- Files affected: `docs/context.md`, `docs/map.md`, and
  `cyd-usage-monitor/{CHANGELOG.md,README.md,include/lv_conf.h,server/dashboard.html,`
  `server/static/lvgl/cyd_lvgl.js,server/static/lvgl/cyd_lvgl.wasm,server/test_server.py,`
  `simulator/build-wasm.ps1,simulator/lv_conf.h,simulator/lvgl_cyd_sim.c,src/main.cpp}`.

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

## History Summary

- 2026-08-09 — Persistent Wokwi HTTPS and Deliberate Touch Control (details retained in earlier Git history).
<!-- Compressed summaries of older changes go here -->

- Project Brain Protocol was upgraded to v1.1.0 while preserving all
  project-specific instructions outside the managed block.
- Earlier Wokwi TLS work isolated an emulator-compatible verified certificate
  path and documented handshake diagnostics before device telemetry later
  returned to the private-LAN-only architecture.
- Wokwi networking diagnostics use bounded emulator-friendly TLS/NTP timeouts
  and credential-safe mbedTLS errors, with corrected operator guidance.
- Earlier CYD networking work corrected the Cloudflare trust chain, separated
  touch/TFT SPI buses, added the protected flashing guide, and verified the
  deployed dashboard/device boundary before telemetry later moved to LAN-only.
- Graphify was activated on 2026-08-09 as a deterministic, source-only graph
  over 12 tracked C/C++, Python, and PowerShell files, with repository-relative
  references and no dependency, generated-asset, secret, or LLM input.
- Project Brain Protocol v1.1.0 was initialized on 2026-08-09 with the
  discovered ESP32/Python/Docker architecture, build commands, repository
  map, context ledger, and preserved workspace policies.
- Initial deployment hardening introduced the Cloudflare Tunnel, separated
  human and device authentication, protected runtime secrets, and documented
  the public-release security boundary before later returning CYD telemetry to
  a private-LAN-only path.
- The hardened application and Tunnel were deployed to the operator-confirmed
  host with private runtime state, rollback protection, verified layered
  authentication, live telemetry, and no tracked deployment identifiers.
- A public-safe operator runbook documented the remote-only Tunnel boundary,
  layered dashboard login, credential operations, deployment verification,
  rollback, and Git release checks.

## Next Steps
<!-- What should be worked on next? -->

- Evaluate optional OpenRouter low-balance/spend alerts only if thresholds and
  delivery behavior are explicitly defined; collection is currently read-only.

## Known Issues
<!-- Active bugs, tech debt, or blockers -->

*None identified during protocol setup.*
