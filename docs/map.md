# Codebase Map

> Auto-maintained by agents. Run `brain check` to verify freshness.

## File Manifest

| File | Purpose | Last Updated |
|------|---------|--------------|
| `docs/map.md` | Codebase file manifest and architecture map | 2026-08-09|
| `.gitignore` | Git ignore patterns | 2026-08-09 |
| `AGENTS.md` | AI agent instructions and project context | 2026-08-09|
| `CODE_OF_CONDUCT.md` | Documentation | 2026-08-09 |
| `CONTRIBUTING.md` | Documentation | 2026-08-09 |
| `cyd-usage-monitor/.dockerignore` | Project file | 2026-08-09 |
| `cyd-usage-monitor/.env` | Environment variables (local) | 2026-08-09 |
| `cyd-usage-monitor/.env.example` | Value-free server, private-LAN device listener, dashboard Tunnel, and alert configuration template | 2026-08-09 |
| `cyd-usage-monitor/.gitignore` | Git ignore patterns | 2026-08-09 |
| `cyd-usage-monitor/AGENTS.md` | Project contract, documented OpenRouter read-API exception, and deployment boundary | 2026-08-09 |
| `cyd-usage-monitor/CHANGELOG.md` | Unreleased and historical project changes | 2026-08-09 |
| `cyd-usage-monitor/diagram.json` | JSON configuration | 2026-08-09 |
| `cyd-usage-monitor/docker-compose.yml` | Hardened app/collector/Tunnel orchestration with a private-address-only device port | 2026-08-09 |
| `cyd-usage-monitor/Dockerfile` | Docker image definition including the protected flashing guide artifact | 2026-08-09 |
| `cyd-usage-monitor/include/lv_conf.h` | Physical LVGL 8.4 Canvas, Arc, Chart, layout, memory, font, and theme configuration | 2026-08-09 |
| `cyd-usage-monitor/include/mascot_img.h` | Project file | 2026-08-09 |
| `cyd-usage-monitor/include/secrets.h` | Project file | 2026-08-09 |
| `cyd-usage-monitor/include/secrets.h.example` | Value-free firmware Wi-Fi, private-LAN endpoint, and Bearer-token template | 2026-08-09 |
| `cyd-usage-monitor/instructions/DEPLOYMENT_RUNBOOK.md` | Public-safe remote deployment, login, credential, verification, rollback, and release runbook | 2026-08-09 |
| `cyd-usage-monitor/instructions/FLASHING_GUIDE.md` | Canonical secure CYD preparation, flashing, verification, and recovery guide | 2026-08-09 |
| `cyd-usage-monitor/instructions/TOKEN_GUIDE.md` | CLI provider, OpenRouter, Cloudflare, Tunnel, and device credential guide | 2026-08-09 |
| `cyd-usage-monitor/platformio.ini` | Shared physical-CYD/Wokwi firmware target with pinned dependencies | 2026-08-09 |
| `cyd-usage-monitor/README.md` | Project architecture, security, deployment, hardware, and development guide | 2026-08-09 |
| `cyd-usage-monitor/server/collector.py` | CLI collector plus OpenRouter credits, key-usage, activity aggregation, pagination, and normalized persistence | 2026-08-09 |
| `cyd-usage-monitor/server/dashboard.html` | Protected OpenRouter setup/status, compact account actions, overview, alerts, interactive two-app LVGL preview, and Utilities UI | 2026-08-09 |
| `cyd-usage-monitor/server/server.py` | Route-isolated listeners with private OpenRouter configuration and normalized device/admin APIs | 2026-08-09 |
| `cyd-usage-monitor/server/static/lvgl/cyd_lvgl.js` | Generated Emscripten loader for the interactive two-app LVGL preview | 2026-08-09 |
| `cyd-usage-monitor/server/static/lvgl/cyd_lvgl.wasm` | Generated WebAssembly binary for launcher, Usage Monitor, OpenRouter, chart, and navigation rendering | 2026-08-09 |
| `cyd-usage-monitor/server/storage.py` | Python module | 2026-08-09 |
| `cyd-usage-monitor/server/test_collector.py` | Python module | 2026-08-09 |
| `cyd-usage-monitor/server/test_server.py` | Server security, API, account-action layout, protected-documentation, and interactive LVGL control contract tests | 2026-08-09 |
| `cyd-usage-monitor/server/test_storage.py` | Python module | 2026-08-09 |
| `cyd-usage-monitor/server/__init__.py` | Python module | 2026-08-09 |
| `cyd-usage-monitor/simulator/build-wasm.ps1` | Reproducible Emscripten 3.1.74 build exporting pointer input and Usage/OpenRouter render functions | 2026-08-09 |
| `cyd-usage-monitor/simulator/lvgl_cyd_sim.c` | WebAssembly launcher and app renderers with layered pointer controls, Home navigation, and browser-backed account rotation | 2026-08-09 |
| `cyd-usage-monitor/simulator/lv_conf.h` | WebAssembly LVGL 8.4 Canvas, Arc, Chart, layout, memory, font, and theme configuration | 2026-08-09 |
| `cyd-usage-monitor/src/main.cpp` | ESP32 two-app launcher, Usage Monitor and OpenRouter UIs, shortcuts, scoped RFC1918 polling, and touch runtime | 2026-08-09 |
| `cyd-usage-monitor/src/mascot_img.h` | Project file | 2026-08-09 |
| `cyd-usage-monitor/wokwi.toml` | Wokwi simulator mapping to the shared LAN-only firmware target | 2026-08-09 |
| `docs/context.md` | Living project state, recent changes, and short-lived follow-ups | 2026-08-09|
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
- Result: 234 nodes, 502 edges, and 9 communities.
- Model usage: none; extraction used Graphify's deterministic AST pipeline.

Last generated: 2026-08-09

> Reference `GRAPH_REPORT.md` for architectural navigation. Regenerate the
> curated graph after durable source changes so it stays current.
