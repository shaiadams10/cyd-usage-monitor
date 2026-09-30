# CYD Usage Monitor

> A self-hosted usage dashboard that collects quota snapshots from locally
> authenticated OpenAI Codex and Google Antigravity CLIs plus the documented
> OpenRouter management API, presents them in a
> browser, and displays the selected account on an ESP32 Cheap Yellow Display.

---

<!-- project-brain-protocol:start version=1.1.0 -->
## 🧠 BRAIN PROTOCOL — MANDATORY

> **STOP. READ THIS BEFORE DOING ANYTHING.**
>
> This project uses the Project Brain Protocol for context management.
> You MUST follow these rules for EVERY task.

### Pre-flight (Before ANY work)
1. Read `docs/context.md` — understand current state and recent changes
2. Read `docs/map.md` — understand the codebase structure

### Post-flight (After ANY code or doc change)
1. Run `brain check` in the terminal
2. If it reports issues, update the brain files:
   - `docs/map.md` — add/remove/update file entries for any files you created, deleted, renamed, or significantly changed
   - `docs/context.md` — add a new entry to Recent Changes describing what you did and why
3. Do NOT consider your task complete until `brain check` returns healthy

### Checkpoint Rule
After completing a feature, bug fix, or refactor:
- Add a rolling window entry to `docs/context.md` with: date, summary, what changed, why, files affected
- If there are more than 10 entries in Recent Changes, compress the oldest into the History Summary section

### Map Rule
When creating, deleting, or renaming ANY file:
- Update `docs/map.md` immediately with the file's path, purpose, and today's date
- This applies to ALL files: code, docs, config, assets — everything

### Protocol Upgrade Rule
- After updating the `brain` CLI, run `brain upgrade --check`
- If an update is available, review it with `brain upgrade` and apply it with `brain upgrade --apply`
- Treat content between the `project-brain-protocol:start` and `project-brain-protocol:end` markers as managed; keep project-specific instructions outside those markers

### AGENTS.md Maintenance
Treat `AGENTS.md` as the durable source of project-wide instructions:
- Update it when stable facts become known or change: project purpose, tech stack, package manager, build/test/run commands, coding conventions, or architectural constraints
- For a project initialized while blank, replace generic placeholders as soon as the project direction or implementation makes the real values clear
- Keep temporary status and recent work in `docs/context.md`, not `AGENTS.md`
- Record meaningful `AGENTS.md` changes in `docs/context.md` and keep its `docs/map.md` entry current

<!-- project-brain-protocol:end -->

---

## Local Operator Map

After the mandatory Brain pre-flight, read `docs/map.local.md` when it exists.
It is an intentionally Git-ignored operator map for private deployment hosts,
LAN targets, and machine-specific recovery details that must remain available
to future local sessions without entering the public repository.

---

## Public Project Scope

This repository contains only CYD Usage Monitor and its support documentation.
Keep unrelated ESP32 projects, duplicate backup copies and private configuration
out of the public tree. Read `cyd-usage-monitor/AGENTS.md` before editing.

## Project Facts and Boundaries

- Firmware uses C++, Arduino, PlatformIO, LVGL 8, TFT_eSPI,
  XPT2046_Touchscreen and ArduinoJson. Current physical target: Hosyond/LCDWiki
  E32R40T ESP32-32E, ST7796S 480x320 landscape and XPT2046 resistive touch.
  The historical PlatformIO environment remains `esp32-2432S028R`.
- Server/dashboard use Python, HTML, JavaScript, Docker and Compose. The
  C/LVGL simulator uses Emscripten 3.1.74 and shares firmware UI behavior.
- Codex quota collection uses authenticated `/status` panels only. Never
  activate banked resets or open Codex `/usage` during collection.
  Antigravity uses its authenticated `/usage` panel. OpenRouter is the sole
  documented public quota-API exception, using management read endpoints.
- Keep credentials, Wi-Fi secrets, profiles, logs, account identifiers,
  private hosts/addresses and personal paths out of Git. Use ignored `.env`
  and `include/secrets.h`, private runtime storage and value-free examples.
- Publish only the protected dashboard externally. Keep the Bearer-protected
  device API on the operator's private LAN, outside public tunnel ingress.
- Update project README and CHANGELOG for behavior, UI, hardware,
  configuration, authentication and deployment changes.
- Deploy only to the operator-designated environment. Read the ignored local
  operator map before running containers or deploying; no host is hard-coded.
- Dependencies are pinned in project build/container/simulator configuration.
  There is no repository-wide package manager.

## Validation

From the repository root:

```sh
python -m unittest discover -s cyd-usage-monitor/server
python -m unittest discover -s cyd-usage-monitor/scripts -p "test_*.py"
cd cyd-usage-monitor
pio run
docker compose --env-file .env.example config --quiet
```

For simulator changes run `simulator/build-wasm.ps1 -TestMotion` and
`simulator/build-wasm.ps1` in PowerShell with Emscripten 3.1.74 available.
Run container builds and live smoke checks on the configured deployment host.
Keep temporary status in `docs/context.md`, and durable facts here.
