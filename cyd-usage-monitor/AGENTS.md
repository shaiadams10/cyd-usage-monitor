# CYD Usage Monitor Change Contract

Read this file and the workspace `AGENTS.md` before changing this project.

1. Collect Codex and Antigravity usage only through their authenticated
   `/status` and `/usage` CLI panels. OpenRouter may use only its documented
   read endpoints with the dashboard-managed Management API key. Do not import
   credential files, call private provider APIs, or use OpenRouter mutation
   endpoints.
2. Keep `.env`, `include/secrets.h`, CLI profiles, OpenRouter keys, runtime snapshots, logs,
   private endpoints, and routing identifiers out of Git, browser output, and
   logs. Use value-free examples and configurable paths instead.
3. Treat `server/collector.py`, `server/server.py`, `server/dashboard.html`,
   `server/static/`, `docker-compose.yml`, and the LVGL simulator as one
   runtime. Rebuild the WebAssembly preview if its shared assets change.
4. The physical CYD and WebAssembly preview must share LVGL assets and
   behavior. Preview-specific sizing fixes must not degrade the device UI.
5. Update `README.md` and `CHANGELOG.md` for every behavior, API,
   configuration, authentication, deployment, UI, or hardware change. Update
   `instructions/TOKEN_GUIDE.md` when authentication behavior changes.
6. Before handoff, run relevant parser tests, the PlatformIO build for
   firmware changes, the WASM build for simulator changes, and a dashboard/API
   smoke test.
7. The dashboard may retain only a WAHA group routing ID in
   `monitor-settings.json`; WAHA keys remain in the private host `.env`, and
   test alerts are sent only by the collector.
8. Cloudflare Tunnel exposes only the dashboard listener. Device telemetry
   must use the separate Bearer-protected listener bound to the monitor
   server's private RFC1918 address; never add a public device ingress.

## Deployment

Deployment paths, hostnames, and credentials are operator-owned configuration.
Use `.env` to configure the Compose mounts, deploy to the operator's chosen
private host, then verify the dashboard and both containers. Never add a
specific deployment target to this repository.

Record the active target only in ignored `.env` values such as
`CYD_MONITOR_DEPLOY_HOST` and `CYD_MONITOR_DEPLOY_DIR`. Run the `cloudflared`
connector only beside the origin application on that selected host; do not
run or retain its Tunnel token on development workstations.
