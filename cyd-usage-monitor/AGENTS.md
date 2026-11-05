# CYD Usage Monitor Change Contract

Read this file and the workspace `AGENTS.md` before changing this project.

1. Collect Codex, Antigravity and Claude Code usage only through their authenticated
   `/status` and `/usage` CLI panels. OpenRouter may use only its documented
   read endpoints with the dashboard-managed Management API key. Do not import
   credential files, call private provider APIs, or use OpenRouter mutation
   endpoints.

Quota collection must never send a model prompt. The separate operator-controlled
wake-up feature may submit one operator-selected plain-text prompt (default
`say OK`, at most 500 characters) once through an official CLI, using the
operator-selected model and supported reasoning setting. Store the exact prompt
with its job/schedule and include it in duplicate-request validation.
Do not automatically resubmit, resume, change models, or retry a failed prompt.
Bound CLI execution, disable native retries where supported and verified, and
record any remaining native behavior accurately. Reserve each distinct account attempt
durably before launch; uncertain outcomes must pause that account without retry.
Schedules and immediate actions share the same account/window guard.
Send one durable provider/model-grouped visual receipt per run through configured
WhatsApp or email fallback; never one alert per account. Render locally and never
include custom prompts or raw CLI transcripts. Confirm resets using read-only
quota panels or label estimates explicitly. Keep the master preference persisted
across restarts; clock-safety holds are separate from that saved preference.
Scheduled sends attempt once even with active or unknown five-hour windows,
requiring fresh healthy same-account panels and positive weekly quota. Do not
infer idle state or a new reset from rounded 100% plus a clock label.
Operator-requested Send now attempts one prompt regardless of active/unknown
window or reported quota, while identity freshness, model, durable duplicate,
uncertain-attempt, interval and daily guards remain enforced. Provider rejection
is reported without resending. Per-provider model/reasoning defaults are persisted
on the server and prefill new actions; they never retarget saved schedules/jobs.
Immediate Codex/Claude preflights may use documented official local identity
metadata instead of a quota panel; scheduled weekly eligibility must still use a fresh
panel. Never use account metadata APIs for quota collection. Publish confirmed
send outcomes before read-only reset checks finish; at most three reset reads
overlap across accounts. A fresh same-account clock with uncertain rounded quota
is labelled CLI reported, without inferring an active or newly started window.
Guarded confirmed failures must retain their cause and failed classification;
never call them uncertain or imply a new submission. Keep guards until review.
Attribute usage-limit windows only from fresh same-account CLI quota facts and
include each exhausted window/reset in receipts. When unavailable, state that
weekly vs five-hour attribution is unconfirmed; never guess from reset duration.
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
6. Install server/requirements.txt for the pinned report renderer.
   Before handoff, run relevant parser tests, the PlatformIO build for
   firmware changes, the WASM build for simulator changes, and a dashboard/API
   smoke test.
7. The dashboard may retain only a WAHA group routing ID in
   `monitor-settings.json`; WAHA keys remain in the private host `.env`, and
   test alerts are sent only by the collector.
8. Cloudflare Tunnel exposes only the dashboard listener. Device telemetry
   must use the separate Bearer-protected listener bound to the monitor
   server's private RFC1918 address; never add a public device ingress.
9. Optional Windows message hooks may use documented local Codex `account/read`
   solely for account identity; they must not read provider credentials or
   collect quota. Keep mappings outside Git, skip ambiguous identities, and
   preserve app hook trust review. Run `python -m unittest discover -s
   cyd-usage-monitor/scripts -p test_chat_account_switch.py` from the workspace
   root for message-hook changes.

## Windows helper runtime

Keep installed desktop helpers and mappings in `%USERPROFILE%/.cyd-usage-monitor`.
Do not use LocalAppData for shared helper installation: MSIX-packaged Codex
redirects writes there into a package cache invisible to ordinary startup tasks
and other desktop apps. Use the per-user `CYD Antigravity Messages` scheduled
task for logon/recovery and keep debug history bounded and metadata-only.

## Collector diagnostics

Use `server/diagnostics.py` for private, bounded collection events. Keep raw
terminal captures host-only; timeline/API/console records must use credential-safe
fields and hashed account references. Preserve first evidence for retained
incidents and never prune open outages to make room for recovered incidents.
The collector supports `--healthcheck`; listener health alone is insufficient.
CLI executables are read-only file bind mounts. Stage and checksum-verify
official updates, preserve the prior binary, and recreate the collector after
replacing a host binary so it receives the new inode. Verify `/usage` before
and after an Antigravity update; missing groups can indicate an outdated client.
The collected banner version is retained in private diagnostic events.
Codex can use a separate official `CODEX_WAKEUP_BIN` for current model metadata
and sending; quota collection must keep using `CODEX_BIN`. This preserves visible
reset/credit fields when newer official versions omit them. Both binaries share
the same isolated profile, without credential imports.
Claude Code uses an isolated `CLAUDE_CONFIG_DIR` per profile and official
`claude auth login`/`claude auth status`. Quota collection must not set
`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` or `DISABLE_TELEMETRY`: those broad
flags disable feature fetching needed by `/usage`. Use granular error-reporting
and updater controls. Native startup menus require settled, separate selection
and confirmation; approve only the verified empty collector workspace.
Never copy a workstation session or
parse credentials. Reject last-known `/usage` panels as fresh readings. Missing
reset times remain unavailable; missing model-specific windows are not invented.

## Shared UI motion

`src/ui_motion.h` is the C-compatible motion implementation for firmware and
WASM. Keep LVGL access on the UI task; the HTTP worker must never touch widgets.
For motion changes also run `simulator/build-wasm.ps1 -TestMotion` from this
project (or its full project-relative path from the workspace root).

## Deployment

Deployment paths, hostnames, and credentials are operator-owned configuration.
Use `.env` to configure the Compose mounts, deploy to the operator's chosen
private host, then verify the dashboard and both containers. Never add a
specific deployment target to this repository.

Record the active target only in ignored `.env` values such as
`CYD_MONITOR_DEPLOY_HOST` and `CYD_MONITOR_DEPLOY_DIR`. Run the `cloudflared`
connector only beside the origin application on that selected host; do not
run or retain its Tunnel token on development workstations.

Install `scripts/recover-monitor.py --project-dir "$PWD" --install` on the Linux
deployment host after initial Compose startup. Verify user lingering and the
enabled `cyd-monitor-recovery.timer`; Docker can miss private-address binds at
boot. Pause both recovery timer and service during intentional maintenance.
Run `python -m unittest discover -s cyd-usage-monitor/scripts -p test_recover_monitor.py`
for recovery changes. Keep recovery scoped to existing project services and
existing images; preserve the private LAN binding and runtime mounts.
