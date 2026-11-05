# Project Map

Public CYD source and supporting documentation only.

| Path | Purpose | Updated |
| --- | --- | --- |
| `.gitattributes` | Repository policy, configuration or public homepage | 2026-09-30 |
| `.github/dependabot.yml` | Repository policy, configuration or public homepage | 2026-09-30 |
| `.github/workflows/ci.yml` | CYD-only source guard, server and Windows tests, container/firmware builds and shared LVGL/WASM export checks | 2026-11-05 |
| `.gitignore` | Repository policy, configuration or public homepage | 2026-09-30 |
| `AGENTS.md` | AI agent instructions, Brain pre-flight, and optional local-operator-map discovery | 2026-11-05 |
| `CODE_OF_CONDUCT.md` | Repository policy, configuration or public homepage | 2026-09-30 |
| `CONTRIBUTING.md` | Repository policy, configuration or public homepage | 2026-09-30 |
| `LICENSE` | Repository policy, configuration or public homepage | 2026-09-30 |
| `NOTICE.md` | Repository policy, configuration or public homepage | 2026-09-30 |
| `README.md` | CYD public homepage with preview, provider coverage, architecture, quick start and documentation index | 2026-11-05 |
| `SECURITY.md` | Repository policy, configuration or public homepage | 2026-09-30 |
| `cyd-usage-monitor/.dockerignore` | Project file | 2026-11-05 |
| `cyd-usage-monitor/.env.example` | Value-free server, private-LAN listener, dashboard Tunnel, WAHA, TLS SMTP fallback, timezone propagation, and consecutive-failure alert configuration template | 2026-11-05 |
| `cyd-usage-monitor/.gitignore` | CYD .gitignore | 2026-09-30 |
| `cyd-usage-monitor/AGENTS.md` | Project credential boundaries, scheduled weekly-quota gate, single-prompt safeguards and deployment recovery | 2026-11-05 |
| `cyd-usage-monitor/CHANGELOG.md` | Behavior history including scheduled single-attempt window handling and skipped quota explanations | 2026-11-05 |
| `cyd-usage-monitor/Dockerfile` | Pinned Python/Pillow runtime and packaged local wake-up report assets | 2026-11-05 |
| `cyd-usage-monitor/README.md` | Operator guide including scheduled active/unknown-window attempts, quota skips and durable account safeguards | 2026-11-05 |
| `cyd-usage-monitor/diagram.json` | CYD diagram.json | 2026-09-30 |
| `cyd-usage-monitor/docker-compose.yml` | Hardened app/collector/Tunnel orchestration with private binding and separate official Codex quota/wake-up mounts | 2026-11-05 |
| `cyd-usage-monitor/include/lv_conf.h` | CYD include/lv_conf.h | 2026-09-30 |
| `cyd-usage-monitor/include/mascot_img.h` | CYD include/mascot_img.h | 2026-09-30 |
| `cyd-usage-monitor/include/secrets.h.example` | CYD include/secrets.h.example | 2026-09-30 |
| `cyd-usage-monitor/instructions/CHAT_ACCOUNT_SWITCH_SETUP.md` | CYD instructions/CHAT_ACCOUNT_SWITCH_SETUP.md | 2026-09-30 |
| `cyd-usage-monitor/instructions/CODEX_WAKEUP_PLAN.md` | Scheduled and manual attempt eligibility, CLI limitations, durable guards and rollout evidence | 2026-11-05 |
| `cyd-usage-monitor/instructions/DEPLOYMENT_RUNBOOK.md` | Secure deployment, Linux boot recovery installation, maintenance, acceptance checks and rollback | 2026-11-05 |
| `cyd-usage-monitor/instructions/FLASHING_GUIDE.md` | Canonical secure E32R40T preparation, conservative CH340C flashing, verification, and recovery guide | 2026-11-05 |
| `cyd-usage-monitor/instructions/TOKEN_GUIDE.md` | Credential boundaries and shared-home private desktop mappings | 2026-11-05 |
| `cyd-usage-monitor/platformio.ini` | Pinned E32R40T firmware configuration compiling only canonical main.cpp, LCD/touch pin mapping and upload settings | 2026-11-05 |
| `cyd-usage-monitor/scripts/chat-account-switch.py` | CYD scripts/chat-account-switch.py | 2026-09-30 |
| `cyd-usage-monitor/scripts/install-antigravity-startup.ps1` | CYD scripts/install-antigravity-startup.ps1 | 2026-09-30 |
| `cyd-usage-monitor/scripts/install-chat-account-switch.py` | CYD scripts/install-chat-account-switch.py | 2026-09-30 |
| `cyd-usage-monitor/scripts/recover-monitor.py` | Linux user-systemd boot/minute recovery of stopped, disconnected or persistently unhealthy existing Compose services | 2026-11-05 |
| `cyd-usage-monitor/scripts/stream-deck-next-account.ps1` | Secure private-LAN account selection/discovery with diagnostic source attribution | 2026-11-05 |
| `cyd-usage-monitor/scripts/stream-deck-next-account.vbs` | Windowless secure private-LAN selection with diagnostic source attribution | 2026-11-05 |
| `cyd-usage-monitor/scripts/test_chat_account_switch.py` | CYD scripts/test_chat_account_switch.py | 2026-09-30 |
| `cyd-usage-monitor/scripts/test_recover_monitor.py` | Boot failure, lost networking, bounded restart, service scope and private-error regression tests | 2026-11-05 |
| `cyd-usage-monitor/scripts/test_stream_deck_security.py` | Windows synthetic-token HTTP tests for redirect rejection, endpoint validation and direct helper transport | 2026-11-05 |
| `cyd-usage-monitor/scripts/watch-antigravity-messages.py` | CYD scripts/watch-antigravity-messages.py | 2026-09-30 |
| `cyd-usage-monitor/server/__init__.py` | CYD server/__init__.py | 2026-09-30 |
| `cyd-usage-monitor/server/collector.py` | Official CLI collection and formatted grouped receipts with quota-window causes/resets and email fallback | 2026-11-05 |
| `cyd-usage-monitor/server/dashboard.html` | Quota dashboard with matching wake-up navigation and section deep links | 2026-11-05 |
| `cyd-usage-monitor/server/diagnostics.py` | Private bounded SQLite collection timeline, validated CLI version metadata and safe query support | 2026-10-16 |
| `cyd-usage-monitor/server/requirements.txt` | Pinned Pillow runtime dependency for deterministic wake-up report rendering | 2026-11-05 |
| `cyd-usage-monitor/server/server.py` | Protected three-provider quota, wake-up controls, diagnostics and health APIs with explicit missing data | 2026-11-05 |
| `cyd-usage-monitor/server/static/apple-touch-icon.png` | Dashboard artwork or shared LVGL browser asset | 2026-09-30 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-badge-icon-1024.png` | Dashboard artwork or shared LVGL browser asset | 2026-09-30 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-badge-icon-192.png` | Dashboard artwork or shared LVGL browser asset | 2026-09-30 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-badge-icon-32.png` | Dashboard artwork or shared LVGL browser asset | 2026-09-30 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-badge-icon-512.png` | Dashboard artwork or shared LVGL browser asset | 2026-09-30 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-icon-1024.png` | Dashboard artwork or shared LVGL browser asset | 2026-09-30 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-icon-180.png` | Dashboard artwork or shared LVGL browser asset | 2026-09-30 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-icon-192.png` | Dashboard artwork or shared LVGL browser asset | 2026-09-30 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-icon-32.png` | Dashboard artwork or shared LVGL browser asset | 2026-09-30 |
| `cyd-usage-monitor/server/static/cyd-monitor-cycle-icon-512.png` | Dashboard artwork or shared LVGL browser asset | 2026-09-30 |
| `cyd-usage-monitor/server/static/cyd-monitor-icon-1024.png` | Dashboard artwork or shared LVGL browser asset | 2026-09-30 |
| `cyd-usage-monitor/server/static/cyd-monitor-sync-icon-1024.png` | Dashboard artwork or shared LVGL browser asset | 2026-09-30 |
| `cyd-usage-monitor/server/static/cyd-monitor-sync-icon-180.png` | Dashboard artwork or shared LVGL browser asset | 2026-09-30 |
| `cyd-usage-monitor/server/static/cyd-monitor-sync-icon-192.png` | Dashboard artwork or shared LVGL browser asset | 2026-09-30 |
| `cyd-usage-monitor/server/static/cyd-monitor-sync-icon-32.png` | Dashboard artwork or shared LVGL browser asset | 2026-09-30 |
| `cyd-usage-monitor/server/static/cyd-monitor-sync-icon-512.png` | Dashboard artwork or shared LVGL browser asset | 2026-09-30 |
| `cyd-usage-monitor/server/static/favicon-16x16.png` | Dashboard artwork or shared LVGL browser asset | 2026-09-30 |
| `cyd-usage-monitor/server/static/favicon-32x32.png` | Dashboard artwork or shared LVGL browser asset | 2026-09-30 |
| `cyd-usage-monitor/server/static/favicon.ico` | Dashboard artwork or shared LVGL browser asset | 2026-09-30 |
| `cyd-usage-monitor/server/static/favicon.svg` | Dashboard artwork or shared LVGL browser asset | 2026-09-30 |
| `cyd-usage-monitor/server/static/icon-192.png` | Dashboard artwork or shared LVGL browser asset | 2026-09-30 |
| `cyd-usage-monitor/server/static/icon-512.png` | Dashboard artwork or shared LVGL browser asset | 2026-09-30 |
| `cyd-usage-monitor/server/static/lvgl/cyd_lvgl.js` | Generated loader for validated account-safe LVGL quota preview | 2026-11-05 |
| `cyd-usage-monitor/server/static/lvgl/cyd_lvgl.wasm` | Generated quota preview with immediate account values and weekly exhaustion warnings | 2026-11-05 |
| `cyd-usage-monitor/server/static/providers/antigravity.png` | Rasterized local Antigravity mark for notification reports | 2026-11-05 |
| `cyd-usage-monitor/server/static/providers/antigravity.svg` | Google Antigravity provider icon from its official favicon | 2026-11-05 |
| `cyd-usage-monitor/server/static/providers/claude.png` | Rasterized local Claude mark for notification reports | 2026-11-05 |
| `cyd-usage-monitor/server/static/providers/claude.svg` | Claude burst provider icon from Simple Icons | 2026-11-05 |
| `cyd-usage-monitor/server/static/providers/codex.png` | Rasterized local OpenAI mark for notification reports | 2026-11-05 |
| `cyd-usage-monitor/server/static/providers/codex.svg` | OpenAI knot provider icon from Simple Icons | 2026-11-05 |
| `cyd-usage-monitor/server/static/wakeups.css` | Responsive schedule/account forms, shared dashboard navigation and visible activity reset lines | 2026-11-05 |
| `cyd-usage-monitor/server/static/wakeups.html` | Wake-up schedules with weekly-quota sending explanation, defaults, editor and activity views | 2026-11-05 |
| `cyd-usage-monitor/server/static/wakeups.js` | Provider defaults, schedule/send forms and stable activity with reported skipped clocks | 2026-11-05 |
| `cyd-usage-monitor/server/storage.py` | CYD server/storage.py | 2026-09-30 |
| `cyd-usage-monitor/server/test_claude.py` | Claude quota parser, isolated environment, login and collection regressions | 2026-11-05 |
| `cyd-usage-monitor/server/test_collector.py` | Collection safety, quota-window summaries, image transport, MIME fallback and notification privacy regressions | 2026-11-05 |
| `cyd-usage-monitor/server/test_diagnostics.py` | Timeline privacy, CLI version/current-panel compatibility, retention and outage evidence regressions | 2026-10-16 |
| `cyd-usage-monitor/server/test_server.py` | Authenticated CSRF-protected default APIs, quota validation and concurrent selection regressions | 2026-11-05 |
| `cyd-usage-monitor/server/test_storage.py` | CYD server/test_storage.py | 2026-09-30 |
| `cyd-usage-monitor/server/test_wakeup_catalog.py` | Model discovery, supported effort, catalogue cache and no-fallback regressions | 2026-11-05 |
| `cyd-usage-monitor/server/test_wakeup_cli.py` | CLI wake-up arguments, identity/cache freshness and independent quota-pool regressions | 2026-11-05 |
| `cyd-usage-monitor/server/test_wakeup_codex.py` | Codex identity-only protocol, selected model/effort, retry and no-fallback regressions | 2026-11-05 |
| `cyd-usage-monitor/server/test_wakeup_report.py` | Report stress layouts, quota failure-window/reset details, compact times and DST regressions | 2026-11-05 |
| `cyd-usage-monitor/server/test_wakeups.py` | Scheduled active/unknown-window attempts, seven-account morning replay, quota freshness and shared no-resend guards | 2026-11-05 |
| `cyd-usage-monitor/server/wakeup_catalog.py` | Cached version-aware official CLI model/effort discovery without model-family or API-only filters | 2026-11-05 |
| `cyd-usage-monitor/server/wakeup_cli.py` | Official CLI adapters, normalized preflight quota facts, identity checks and single-attempt prompts | 2026-11-05 |
| `cyd-usage-monitor/server/wakeup_codex.py` | Explicit-model Codex sender with fast official identity checks, zero transport retries and bounded single sending | 2026-11-05 |
| `cyd-usage-monitor/server/wakeup_report.py` | Grouped visual/text quota-limit reasons and reset times with shared timezone header | 2026-11-05 |
| `cyd-usage-monitor/server/wakeups.py` | Scheduled attempts with weekly quota, durable account guards, saved preflight facts and skipped-window attribution | 2026-11-05 |
| `cyd-usage-monitor/simulator/build-wasm.ps1` | Pinned WASM build exporting Codex footer updates and real LVGL motion tests | 2026-11-05 |
| `cyd-usage-monitor/simulator/lv_conf.h` | CYD simulator/lv_conf.h | 2026-09-30 |
| `cyd-usage-monitor/simulator/lvgl_cyd_sim.c` | LVGL browser screens with account-safe quota bars, weekly exhaustion warnings and styled footer badges | 2026-11-05 |
| `cyd-usage-monitor/simulator/test_motion.c` | Real LVGL motion, full-to-empty account switching, weekly exhaustion and footer regression checks | 2026-11-05 |
| `cyd-usage-monitor/src/main.cpp` | Physical CYD with validated quota fields, immediate account values, weekly exhaustion warnings and quota diagnostics | 2026-11-05 |
| `cyd-usage-monitor/src/mascot_img.h` | CYD src/mascot_img.h | 2026-09-30 |
| `cyd-usage-monitor/src/ui_motion.h` | Shared bounded LVGL motion with immediate quota bars on account identity changes | 2026-11-05 |
| `cyd-usage-monitor/src/ui_provider.h` | Shared native provider icons and balanced quota cards with distance-readable remaining bars | 2026-11-05 |
| `cyd-usage-monitor/wokwi.toml` | Wokwi simulator mapping to the shared LAN-only firmware target | 2026-11-05 |
| `docs/context.md` | Current project state, recent changes, validation and deployment results | 2026-11-05 |
| `docs/images/cyd-usage-monitor-dashboard.png` | Illustrative dashboard screenshot with sample accounts | 2026-09-30 |
| `docs/images/cyd-usage-monitor-hero.png` | User-provided promotional illustration of Codex and Antigravity CYD screens with example accounts | 2026-09-30 |
| `docs/map.md` | Codebase file manifest and architecture map | 2026-11-05 |
