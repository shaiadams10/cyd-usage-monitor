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

## ESP32 Workspace Guidelines

This repository contains independent ESP32 projects. Keep changes scoped to
the relevant project directory and read that project's `AGENTS.md` before
editing.

## Public-repository rules

1. Never commit credentials, API keys, Wi-Fi credentials, access tokens,
   session data, device identifiers, private hostnames, private IP addresses,
   email addresses, or personal filesystem paths.
2. Keep real configuration in ignored files such as `.env` and
   `include/secrets.h`. Commit only safe, value-free examples.
3. Keep generated firmware, dependency caches, runtime data, CLI profiles,
   logs, and local editor settings out of version control.
4. Use configurable environment variables or documented placeholders for
   deployment-specific paths and endpoints.
5. Update the affected project's `README.md` and `CHANGELOG.md` with every
   behavior, configuration, authentication, deployment, UI, or hardware
   change.
6. Run the relevant build, tests, and smoke checks before handoff. Deploy only
   to an environment explicitly identified by the project operator; do not
   embed a deployment target in the repository.

Each project must be self-contained, document its hardware and pin mapping,
and retain its own build configuration.

## Project Facts

- The two primary projects are `esp32s3-home-assistant` (the main Home
  Assistant voice satellite) and `cyd-usage-monitor`, both documented at the
  repository root and in their project READMEs.
- `esp32s3-home-assistant` v2 uses ESPHome 2026.7.0 with the ESP-IDF backend,
  on-device microWakeWord, the encrypted native API, and the standard Home
  Assistant Assist pipeline. Its previous custom Arduino implementation is a
  dated rollback-only directory and must not be used as a source of networking
  or voice-state code.
- Firmware targets the ESP32-2432S028R Cheap Yellow Display using C++,
  Arduino, PlatformIO, LVGL 8, TFT_eSPI, XPT2046_Touchscreen, and ArduinoJson.
- The self-hosted server and dashboard use Python, HTML, JavaScript, Docker,
  and Docker Compose. A C/LVGL simulator produces the browser WebAssembly
  preview with Emscripten.
- Dependencies are pinned in `cyd-usage-monitor/platformio.ini`, the
  container configuration, and the simulator build tooling. There is no
  repository-wide package manager.

## Build, Test, and Run Commands

Run commands from the repository root unless a command changes directories:

```sh
python -m unittest discover -s cyd-usage-monitor/server
cd cyd-usage-monitor
pio run
docker compose --env-file .env.example config --quiet
docker compose up -d --build
cd ../esp32s3-home-assistant
.venv/Scripts/esphome.exe config device.yaml
.venv/Scripts/esphome.exe compile device.yaml
docker compose -f server/docker-compose.yml config --quiet
```

For simulator changes, run `cyd-usage-monitor/simulator/build-wasm.ps1` in
PowerShell with Emscripten 3.1.74 available.

## Conventions and Architecture

- Codex and Antigravity authentication remains inside isolated official CLI
  profiles. The collector parses their visible usage panels and must not import
  credentials or call private provider APIs. OpenRouter is the sole documented
  public-API exception: its dashboard-managed Management API key remains in
  private runtime storage and only normalized credits/activity are persisted.
- The protected browser dashboard and authenticated CYD API consume the
  normalized snapshot. The physical display and browser preview share LVGL
  assets and behavior.
- Follow `cyd-usage-monitor/AGENTS.md` for project-specific security,
  cross-runtime, documentation, testing, and deployment requirements.
- Keep durable project-wide facts and commands in this file. Keep temporary
  status, recent work, and short-lived follow-ups in `docs/context.md`.
