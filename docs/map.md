# Codebase Map

> Auto-maintained by agents. Run `brain check` to verify freshness.

## File Manifest

| File | Purpose | Last Updated |
|------|---------|--------------|
| `cyd-usage-monitor/scripts/test_stream_deck_security.py` | Windows synthetic-token HTTP tests for redirect rejection, endpoint validation and direct helper transport | 2026-09-06 |
| `cyd-usage-monitor/instructions/CHAT_ACCOUNT_SWITCH_SETUP.md` | Fresh Windows setup, private mapping recovery, verification and troubleshooting for desktop message selection | 2026-09-06 |
| `cyd-usage-monitor/scripts/watch-antigravity-messages.py` | Windowless Windows file-notification fallback with per-user startup and shared message deduplication | 2026-09-05 |
| `cyd-usage-monitor/scripts/install-chat-account-switch.py` | Installs private mappings, Codex hook, and Antigravity file-event fallback with configuration backups | 2026-09-05 |
| `cyd-usage-monitor/scripts/test_chat_account_switch.py` | Tests account changes, ambiguity, message deduplication, ordering, and LAN-only requests | 2026-09-05 |
| `cyd-usage-monitor/scripts/chat-account-switch.py` | Windows account selector with per-submission Codex identity, timestamp-ordered Antigravity deduplication, and diagnostics | 2026-09-05 |
| `cyd-usage-monitor/.dockerignore` | Project file | 2026-08-09 |
| `cyd-usage-monitor/.env.example` | Value-free server, private-LAN listener, dashboard Tunnel, WAHA, TLS SMTP fallback, timezone propagation, and consecutive-failure alert configuration template | 2026-09-05 |
| `cyd-usage-monitor/.gitignore` | Excludes credentials, runtime data, local message-hook mappings and backups | 2026-09-06 |
| `cyd-usage-monitor/AGENTS.md` | Security, parity, shared motion/thread ownership, testing and deployment contract | 2026-09-05 |
| `cyd-usage-monitor/CHANGELOG.md` | Change history including all-screen animations and responsive HTTP waits | 2026-09-06 |
| `cyd-usage-monitor/diagram.json` | Wokwi visual layout and pin connection diagram for ESP32-2432S028R | 2026-08-09 |
| `cyd-usage-monitor/docker-compose.yml` | Hardened app/collector/Tunnel orchestration with container TZ, private device binding, WAHA, and host-only TLS SMTP fallback configuration | 2026-09-05 |
| `cyd-usage-monitor/Dockerfile` | Python 3.14 server image definition including the protected flashing guide artifact | 2026-08-09 |
| `cyd-usage-monitor/include/lv_conf.h` | Physical LVGL 8.4 Canvas, Arc, Chart, layout, memory, font, and theme configuration | 2026-08-09 |
| `cyd-usage-monitor/include/mascot_img.h` | Project file | 2026-08-09 |
| `cyd-usage-monitor/include/secrets.h.example` | Value-free firmware Wi-Fi, private-LAN endpoint, and Bearer-token template | 2026-08-09 |
| `cyd-usage-monitor/instructions/DEPLOYMENT_RUNBOOK.md` | Public-safe remote deployment, dashboard/host SMTP setup, display-command verification, rollback, and release runbook | 2026-08-26 |
| `cyd-usage-monitor/instructions/FLASHING_GUIDE.md` | Canonical secure E32R40T preparation, conservative CH340C flashing, verification, and recovery guide | 2026-08-26 |
| `cyd-usage-monitor/instructions/TOKEN_GUIDE.md` | Provider credential boundaries and identity-only local message hook configuration | 2026-09-05 |
| `cyd-usage-monitor/platformio.ini` | Shared physical-CYD/Wokwi firmware target with pinned dependencies, E32R40T ST7796S flags, and conservative CH340C upload speed | 2026-08-26 |
| `cyd-usage-monitor/README.md` | Operator guide including per-screen motion, HTTP/UI responsiveness and validation | 2026-09-06 |
| `cyd-usage-monitor/scripts/stream-deck-next-account.ps1` | Private-LAN WinHTTP discovery and selection with redirect/proxy/authentication safeguards | 2026-09-06 |
| `cyd-usage-monitor/scripts/stream-deck-next-account.vbs` | Windowless private-LAN WinHTTP selection with redirect/proxy/authentication safeguards | 2026-09-06 |
| `cyd-usage-monitor/server/collector.py` | CLI/OpenRouter collector with local timezone propagation, dual Codex quotas, durable identity, incidents, WAHA retry, and environment/dashboard TLS SMTP fallback | 2026-09-05 |
| `cyd-usage-monitor/server/dashboard.html` | Upright synchronized LVGL preview, physical-orientation indicator, protected display controls, email setup, alert health, and favicon/touch icons | 2026-08-27 |
| `cyd-usage-monitor/server/server.py` | Route-isolated APIs with transactional account selection and new-command-only profile-bound cached telemetry | 2026-09-05 |
| `cyd-usage-monitor/server/static/apple-touch-icon.png` | 180x180 high-DPI iOS/mobile touch icon asset | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-badge-icon-32.png` | 32x32 compact Stream Deck cycle-action badge icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-badge-icon-192.png` | 192x192 Stream Deck cycle-action badge icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-badge-icon-512.png` | 512x512 high-resolution cycle-action badge icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-badge-icon-1024.png` | 1024x1024 master cycle-action badge icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-icon-32.png` | 32x32 compact account-cycle action icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-icon-180.png` | 180x180 account-cycle touch/launcher icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-icon-192.png` | 192x192 account-cycle action icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-icon-512.png` | 512x512 high-resolution account-cycle action icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-icon-1024.png` | 1024x1024 master pixel-art CYD Usage Monitor icon with integrated cycle indicator | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-icon-1024.png` | 1024x1024 master high-resolution CYD Usage Monitor app branding icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-sync-icon-32.png` | 32x32 compact dashboard/device synchronization action icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-sync-icon-180.png` | 180x180 dashboard/device synchronization touch/launcher icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-sync-icon-192.png` | 192x192 dashboard/device synchronization action icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-sync-icon-512.png` | 512x512 high-resolution dashboard/device synchronization action icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/cyd-monitor-sync-icon-1024.png` | 1024x1024 master dashboard/device synchronization action icon | 2026-08-27 |
| `cyd-usage-monitor/server/static/favicon-16x16.png` | 16x16 crisp raster favicon asset | 2026-08-27 |
| `cyd-usage-monitor/server/static/favicon-32x32.png` | 32x32 standard browser tab raster favicon asset | 2026-08-27 |
| `cyd-usage-monitor/server/static/favicon.ico` | Multi-resolution 16/32/48/64px Windows and browser ICO favicon asset | 2026-08-27 |
| `cyd-usage-monitor/server/static/favicon.svg` | Scalable vector SVG favicon with dark theme, glowing arc meter, and CYD monogram | 2026-08-27 |
| `cyd-usage-monitor/server/static/icon-192.png` | 192x192 PWA web app manifest icon asset | 2026-08-27 |
| `cyd-usage-monitor/server/static/icon-512.png` | 512x512 high-resolution app icon asset | 2026-08-27 |
| `cyd-usage-monitor/server/static/lvgl/cyd_lvgl.js` | Generated loader for animated shared LVGL preview | 2026-09-06 |
| `cyd-usage-monitor/server/static/lvgl/cyd_lvgl.wasm` | Generated animated launcher, ChatGPT, Antigravity and OpenRouter LVGL runtime | 2026-09-06 |
| `cyd-usage-monitor/server/storage.py` | Python module | 2026-08-09 |
| `cyd-usage-monitor/server/test_collector.py` | Isolated collector runtime, credential boundaries, timezone, quota, incident and notification regression tests | 2026-09-06 |
| `cyd-usage-monitor/server/test_server.py` | Server security, account selection, profile-bound inline/new-only and legacy command contracts, and display tests | 2026-09-05 |
| `cyd-usage-monitor/server/test_storage.py` | Python module | 2026-08-09 |
| `cyd-usage-monitor/server/__init__.py` | Python module | 2026-08-09 |
| `cyd-usage-monitor/simulator/test_motion.c` | Real LVGL/WASM regression checks for animation state, bounds, refreshes, errors and rapid navigation | 2026-09-06 |
| `cyd-usage-monitor/simulator/build-wasm.ps1` | Pinned production WASM build and real LVGL motion tests with failure propagation | 2026-09-05 |
| `cyd-usage-monitor/simulator/lvgl_cyd_sim.c` | WASM launcher, quota and OpenRouter screens with shared motion and pointer navigation | 2026-09-06 |
| `cyd-usage-monitor/simulator/lv_conf.h` | WebAssembly LVGL 8.4 Canvas, Arc, Chart, layout, memory, font, and theme configuration | 2026-08-09 |
| `cyd-usage-monitor/src/ui_motion.h` | Shared LVGL motion with coalesced strip reveals, stable arrival values, quota sweeps, counters and charts | 2026-09-06 |
| `cyd-usage-monitor/src/main.cpp` | Physical CYD with strip transitions, HTTP worker, retry backoff, Wi-Fi/reset/memory/render diagnostics | 2026-09-06 |
| `cyd-usage-monitor/src/mascot_img.h` | Project file | 2026-08-09 |
| `cyd-usage-monitor/wokwi.toml` | Wokwi simulator mapping to the shared LAN-only firmware target | 2026-08-09 |
| `docs/map.md` | Codebase file manifest and architecture map | 2026-08-11|
| `.github/workflows/ci.yml` | Server, Windows helper transport, firmware, real LVGL motion and WASM release checks | 2026-09-06 |
| `.gitignore` | Git ignore patterns | 2026-08-09 |
| `AGENTS.md` | AI agent instructions and project context | 2026-08-09|
| `CODE_OF_CONDUCT.md` | Documentation | 2026-08-09 |
| `CONTRIBUTING.md` | Documentation | 2026-08-09 |
| `docs/context.md` | Living project state, recent changes, and short-lived follow-ups | 2026-08-11|
| `LICENSE` | Project file | 2026-08-09 |
| `NOTICE.md` | Documentation | 2026-08-09 |
| `README.md` | Project documentation | 2026-08-09 |
| `SECURITY.md` | Documentation | 2026-08-09 |

## Architecture Overview

The repository is organized as a public workspace with one self-contained
project, `cyd-usage-monitor/`:

1. `server/collector.py` normalizes isolated Codex/Antigravity CLI panels plus
   documented read-only OpenRouter credits, key usage, and activity while
   keeping the management key private.
2. `server/server.py`, `server/storage.py`, and `server/dashboard.html` expose
   the protected dashboard, flashing guide, browser preview, and CYD APIs.
3. `src/main.cpp` builds the ESP32-2432S028R firmware with Arduino,
   PlatformIO, LVGL, and TFT_eSPI.
4. `simulator/` and `server/static/lvgl/` provide a WebAssembly preview built
   from shared LVGL assets so browser and device behavior stay aligned.
5. Docker Compose packages the server and collector for a private,
   operator-configured deployment. Secrets and runtime state remain in
   ignored local files and directories.

## Graphify

Status: ✅ Active — deterministic source-only knowledge graph generated.

- Report: [`graphify-out/GRAPH_REPORT.md`](../graphify-out/GRAPH_REPORT.md)
- Interactive graph: [`graphify-out/graph.html`](../graphify-out/graph.html)
- Data: [`graphify-out/graph.json`](../graphify-out/graph.json)
- Scope: 12 tracked C/C++, Python, and PowerShell source files; generated
  assets, documentation, local secrets, and untracked files are excluded.
- Result: 248 nodes, 536 edges, and 10 communities.
- Model usage: none; extraction used Graphify's deterministic AST pipeline.

Last generated: 2026-08-09

> Reference `GRAPH_REPORT.md` for architectural navigation. Regenerate the
> curated graph after durable source changes so it stays current.
