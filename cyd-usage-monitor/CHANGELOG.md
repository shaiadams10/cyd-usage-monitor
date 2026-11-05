# Changelog

## 2026-11-05 — Scheduled attempts with active or unclear windows

- Match the operator's scheduled-send preference: attempt one prompt with active
  or unclear five-hour windows when a fresh healthy same-account panel reports
  positive weekly quota. Apply to existing schedules; retain identity, model,
  duplicate, interval, daily and uncertain-outcome guards with no prompt retry.
- Do not assume a reset restart for active/unknown windows. Explain exhausted vs
  unavailable weekly quota separately, include exhausted-window resets on skips,
  and label skipped CLI clocks as reported. Retain bounded normalized preflight
  facts in saved results for future diagnosis, without raw panels or credentials.

## 2026-11-04 — Accurate guarded failures and quota-window explanations

- Preserve confirmed failures behind account guards as failed results with their
  recorded cause; distinguish them from genuinely unconfirmed attempts. A new
  request blocked by that guard does not pretend another prompt was submitted.
- Attribute usage/rate-limit failures using fresh same-account CLI panels. Show
  weekly/five-hour exhaustion and their reported resets in Activity and grouped
  text/image receipts; disclose when the affected window cannot be confirmed.
- Reuse healthy quota facts where possible; otherwise perform one bounded
  read-only check alongside existing reset reads. Keep all guards and no-retry
  behavior, and continue processing other accounts after any failure.

## 2026-11-04 — Faster wake-ups, stable activity and visible reset times

- Replace immediate Codex/Claude pre-send quota-screen reads with fresh official
  identity metadata; replace Codex's repeated identity screen with local
  `account/read`. Reuse only healthy same-account quota panels under two minutes
  old. Keep scheduled eligibility and all durable no-resend guards.
- Publish each confirmed send immediately and overlap up to three read-only
  reset checks. Keep one final grouped receipt, with no extra model prompts.
- Retain fresh CLI reset clocks when rounded-full quota leaves activity unknown;
  label these CLI reported in text/image receipts and show resets in Activity.
- Keep a stable row per selected account and distinguish checking/sending/reset
  verification from a genuine failure or interruption. A live reservation no
  longer appears as a failed/interrupted attempt with an acknowledgement button.

## 2026-11-04 — Provider defaults, simpler receipts and explicit immediate sends

- Add server-persisted model/reasoning defaults per provider, with save/remove
  controls under Wake-ups → Defaults. Prefill new actions; one-off overrides and
  changes to defaults never retarget existing jobs or schedules. Flag retired
  selections without silently substituting models.
- Redesign receipts as compact account rows on a light background, with reset
  times aligned in a separate column and timezone printed once in the header.
  Keep confirmed/estimated/unavailable states explicit; stress-check 9/50 accounts.
- Format WhatsApp receipts like collection alerts, using bold headings, status
  emojis, provider/model sections and quoted reasons. Preserve summary counts
  in short image captions and formatted inline-image email fallback.
- Honor explicit Send now requests with one prompt regardless of active/unknown
  window or reported quota. Keep all identity/model/duplicate/interval/uncertainty
  guards. Scheduled sends retain confirmed-idle checks. A rounded-full quota and
  reset clock label are no longer incorrectly classified as proof of activity.

## 2026-11-04 — Visual wake-up receipts and persistent master state

- Replace per-account failure alerts with one scheduled/Send now run receipt,
  including successes, skips, failures and unconfirmed outcomes grouped by
  provider/model. Preserve schedule name/time and completed account progress.
- Render a local branded JPEG with prominent reset-time badges: confirmed in a compact neutral tag,
  estimates with a distinct warm-toned label. Try one read-only post-send quota check, with no new prompts.
  Convert reset epochs to the configured timezone with DST support.
- Deliver one WhatsApp image plus caption, with the existing email fallback carrying
  inline image and full plain text. Rendering failure falls back to text; durably
  claimed receipts are never replayed. Keep legacy pending-alert compatibility.
- Preserve enabled/disabled preference across restarts and delivery errors. Clock
  safety holds block sending separately; interrupted attempts are summarized and
  remain guarded rather than retried. Existing schedules/ledger are preserved.
- Pin Pillow 13.0.0 for runtime/CI report rendering; package local raster provider
  marks derived from their existing SVGs. Verify grouping, delivery, MIME image,
  restart persistence, interruption, model safety and timezone rendering.

## 2026-11-04 — Wake-up schedule management and navigation redesign

- Open wake-ups on a schedule-first screen with readable time/day/status cards,
  clear account/model/message sections, next-run details, filters and explicit
  edit/pause/resume/delete actions. Confirm deletion and preserve keyboard focus
  during background refresh.
- Give New schedule, Send now and Activity their own views, with grouped searchable
  accounts, clear selection counts and local provider SVG icons replacing initials.
- Match the dashboard sidebar item and mobile navigation to the existing controls;
  return links open the correct dashboard section. Preserve sending safeguards.
- Verify real authenticated HTTP form flows, duplicate protection, provider icons,
  filtering, search, delete cancellation, focus retention and responsive layouts
  from 320 to 1440 pixels, without starting collectors or sending real prompts.

## 2026-11-04 — Larger quota visuals, current models and custom wake-up messages

- Match ChatGPT to Claude's equal two-card layout, enlarge remaining bars and
  percentage labels across dashboard, physical CYD and shared LVGL preview;
  retain ChatGPT credits, available resets, plan and reset times.
- Use integrity-verified official Codex 0.166.0 for GPT-6/6.1 and 5.6 discovery
  and wake-up sending. Keep quota collection on 0.147.0 because the newer CLI
  omits its visible banked-reset notice; optional `CODEX_WAKEUP_HOST_DIR` separates
  the two read-only official installations. Invalidate catalogue
  caches after binary replacement and retain visible Codex-only model entries.
- Add a shared editable wake-up message, default `say OK`, to immediate sends
  and schedules; persist exact text, restore on edit, review before sending,
  and include text in idempotency checks. Preserve legacy scheduled/queued text.
- Reject invalid text before queuing and preserve one-prompt, no-resend guards;
  custom text stays out of alerts and console logs.

## 2026-11-04 — Explicit wake-up models and provider designs

- Select models and supported reasoning per provider for immediate and scheduled
  prompts, applied across selected accounts and snapshotted into each job.
- Discover choices through official CLIs; reject unavailable account/model pairs
  without fallback. Keep one submitted prompt, bounded execution and no automatic
  resend; failed schedules and uncertain attempts pause for review.
- Record per-account outcomes and safe reasons, with one notification delivery
  attempt through configured channels and visible delivery failures.
- Redesign Claude and Codex dashboard cards and shared LVGL screens with distinct
  terracotta/burst and emerald/OpenAI-inspired branding; compact reset labels
  retain timezone information in the normalized snapshots.


## 2026-11-04 — Claude Code and guarded wake-up controls

- Preserve Claude quota feature fetching with granular privacy settings; normalize
  native cursor-rendered rows and guard startup input timing.
- Handle Claude first-run theme and default-deny workspace trust without importing
  credentials or approving unrelated folders.
- Add isolated official Claude Code sign-in and `/usage` collection, independent
  panel confirmation, account validation, cached-panel rejection and reset text.
- Add Claude profiles to the dashboard, device API, physical CYD and shared LVGL
  browser preview; clearly show weekly exhaustion and unavailable reset times.
- Accept Claude profile IDs in both Stream Deck direct-selection helpers.
- Add verified native CLI mounting with `CLAUDE_HOST_PATH` / `CLAUDE_BIN`.
- Add mobile wake-up account selection, immediate actions and timezone-aware
  one-time/recurring schedules with master stop and visible provider readiness.
- Persist attempt reservations, account deduplication, idempotent requests,
  five-hour safety intervals and unknown-result pauses in a private ledger.
  Collection remains free of inference prompts; only verified sending adapters
  can send the fixed wake-up prompt.


## 2026-11-03 — Display profile IDs on the web dashboard

- Display stable profile IDs on the protected web dashboard for all configured
  OpenAI Codex and Google Antigravity profiles on both the Overview cards and the
  Accounts management list.
- Provide a one-click copy button next to each ID with clipboard feedback to
  simplify configuring Stream Deck account-switching buttons and desktop automation scripts.
- Enhanced global copy event handling to support direct text values (`data-copy-text`)
  alongside existing DOM element references (`data-copy`).
- Added dashboard template assertions in server test regressions.

## 2026-10-26 — Recover after power loss and delayed LAN startup

- Diagnosed the app's failed private-LAN port bind during host boot. Docker
  left the app stopped despite `restart: always`; starting it subsequently
  left its bridge attachment absent. Recreating the app restored both listeners.
- Add an installable Linux user-systemd timer, with verified lingering, to
  check existing monitor services at boot and every minute. Recreate stopped
  or disconnected services and restart persistently unhealthy services at most
  once per five minutes. Use existing images without builds, pulls or changes
  to other services; retain private runtime volumes and Compose configuration.
- Document maintenance pause/resume and recovery checks; test delayed-start
  failures, lost networking, healthy-service preservation and safe error logs.

## 2026-10-16 — Restore Gemini quotas with the current official CLI

- Confirmed `agy` 1.1.11 omitted Gemini in both its TUI and official `/usage`
  JSON for the same account that reports both groups with 1.4.0. The parser
  already reads the current panel correctly; missing data came from the old
  client rather than a changed Gemini heading or scroll position.
- Verified the official release checksum, preserved the prior host binary,
  and updated the configured collector host to 1.4.0. No model turns were sent.
- Record safe CLI banner versions in collection diagnostics and display them
  in the searchable timeline. Add current-panel and version/privacy regressions.
- Document read-only CLI mount maintenance and collector recreation after
  replacing a binary, including checks for incomplete model groups.

## 2026-10-16 — Collection recovery and durable diagnostics

- Accept finished Antigravity quota panels containing one model group; show
  absent groups as N/A across dashboard, physical CYD and LVGL preview. Reject
  truncated panels and incomplete reported groups.
- Prevent malformed Codex `/status` input by disabling paste-burst detection,
  connector startup and startup update checks during quota capture. Preserve
  two independent confirmations and keep reset times readable during retries.
- Add a private, searchable SQLite collection timeline with 30-day/100,000-event
  retention, safe structured Docker logs, capture timing/request/exit metadata,
  categories and exception locations. Preserve first outage evidence and open
  incidents; retain 200 recent captures plus referenced incident evidence.
- Add collector heartbeat/health checks, privacy-safe browser disconnect logs,
  native CLI error hints, bounded hourly Antigravity dated-log maintenance, and
  explicit Docker log rotation (three 10 MB files per service).
- Record the deferred Luna wake-up design and safeguards; no model requests
  or scheduled wake-ups are introduced.

## 2026-10-02 — Preserve Antigravity sessions during quota retries

- Guard Escape retries with a complete quota panel from the current request;
  never send Escape to an authentication screen, where the CLI logs out and
  deletes the saved session. A transient startup/network failure now remains
  a collection failure without the collector removing credentials.
- Add regressions for empty/partial panels, sign-in after a prior panel,
  independent request boundaries, and the actual PTY input loop.


## 2026-09-30 — Stop repeated fallback emails and confirm Antigravity refills

- Deduplicate accepted fallback emails by account and outage start time in a
  bounded durable history, preserving WhatsApp retries without emailing on each
  changing failure count or diagnostic capture. Failed SMTP sends still retry.
- Close Antigravity's `/usage` modal before each new request so quota refills
  can be independently confirmed. Allow small consumption between confirmation
  reads and require the same account.
- Document WAHA QR pairing recovery and add regression tests for changing and
  interleaved incidents, SMTP retry, and modal/refill confirmation.

## 2026-09-30 — README device artwork

- Replace the dashboard screenshot in both README introductions with the
  operator-provided Codex/Antigravity device illustration using example accounts.

## 2026-09-30 — CYD-only public repository and refreshed homepage

- Publish only CYD source and support documentation; remove unrelated ESP32
  projects from the current GitHub tree while preserving local work.
- Replace the homepage with a visual overview, provider coverage, architecture,
  quick start and focused documentation links. Correct hardware and collection
  confirmation descriptions, and guard CI against unrelated project publication.

## 2026-09-29 — Confirmed quota collection and accurate account switching

- Confirm Codex values across independent /status requests, allowing small
  consumption while rejecting transient large startup corrections. Parse only
  the latest account panel and reject incomplete or out-of-range quotas.
- Stop synthesizing full/missing quotas or borrowing weekly values from older
  panels. Label retained retry values Last confirmed and keep existing expiry.
- Snap quota bars to the newly selected account and bind next-account responses
  to that selected profile. Show weekly exhaustion even with unused 5-hour quota.
- Align browser validation and warning thresholds with firmware; add regression
  cases for startup refills, partial panels, malformed values and full-to-empty
  account switches. Provider reset activation remains absent.

## 2026-09-29 — Codex available resets

- Parse the available usage-limit reset count from the read-only CLI notice
  captured alongside `/status` and display it beside Credits on Codex cards.
- Compile only the canonical firmware entry point, excluding local duplicate
  backup sources; include the visible reset label in device diagnostics.
- Version the updated LVGL assets so browsers load the matching footer export.
- Style the physical and preview Credits/Resets headings white, with blue
  values inside compact rounded badges.
- Send reset counts in the authenticated device payload and display them beside
  Credits on both the physical CYD and shared LVGL browser preview.
- Preserve explicit zero counts; missing notices show **Not reported**. No
  reset activation controls or changes to collection commands were added.

## 2026-09-21 — Quota draining and warning color threshold fix

- Fix primary and weekly quota bar color coding and warning logic to consistently evaluate remaining quota draining from 100% to 0%.
- Correct primary bar and value text color thresholds: green above 50% remaining, amber from 21% to 50%, red at or below 20%, and display "100% QUOTA EXHAUSTED" only when quota is depleted (at or below 0% remaining).
- Align weekly bar color thresholds with remaining quota percentage (red at <=20%, amber at <=50%, green above 50%).
- Prefer `codex_5h_pct` when present with fallback to `100 - primary_pct`, and clean up default subtext/fallback strings.

## 2026-09-19 — Faster, steadier usage refresh

- Collect CLI profiles in parallel on per-profile worker threads (bounded by
  `CYD_MONITOR_MAX_PARALLEL_COLLECTIONS`, default 3) instead of one sequential
  90-second cycle. The account selected for the CYD refreshes every
  `CYD_MONITOR_ACTIVE_POLL_SECONDS` (default 30 s) and becomes due immediately
  when selected; other profiles keep `CYD_MONITOR_POLL_SECONDS` (floor lowered
  to 30 s). The dashboard countdown shows both cadences.
- Request Codex `/status` from six seconds after launch with more retries,
  cutting a warm Codex capture from about twenty seconds to about ten.
- Keep the last healthy result (`last_ok`) with each failed snapshot and stamp
  every snapshot with its refresh interval and stale budget. The CYD and
  dashboard preview keep showing the last good values through unconfirmed
  failures (`degraded` payload flag, `retrying` ticker suffix) and show the
  error card only once the alert threshold confirms the outage or the values
  exceed the stale budget. This removes the intermittent error card caused by
  a single missed capture.
- Firmware: raise the LAN read timeout from 750 ms to 1.5 s and show the
  telemetry/OpenRouter error state only after three consecutive transport
  failures when data is already on screen. Token rejection and server-reported
  errors still surface immediately.
- WhatsApp failure alerts now quote the failed account's own refresh interval.
- Require a repeated panel before accepting an abrupt quota drop. When a
  Codex `/status` or Antigravity `/usage` panel reports a limit at least 30
  points below the last healthy reading (or 0% from 10%+), the capture keeps
  asking for the panel until a later one repeats the value. A capture that
  ends on an unrepeated cliff is recorded as an unconfirmed reading and the
  display keeps the previous values, so a transient wrong panel can no longer
  show a full weekly limit for a poll cycle. Antigravity gets a third
  `/usage` request at 17 s to allow confirmation within its capture window.

## 2026-09-18

- Support Antigravity disabled 5-hour quota when weekly limit is reached (0.00%
  remaining) for Claude and Gemini model groups. Parse the disabled state as
  0% remaining with "Weekly limit reached" subtext, avoiding collection failures
  and timeout errors.

## 2026-09-09

- Repair Codex message selection after Codex Desktop updates replace its
  versioned bundled-CLI directory. The hook now rediscovers the newest standard
  desktop `codex.exe` when its configured executable no longer exists.

## 2026-09-06 — Restart recovery and switch diagnostics

- Move Windows helpers/private mappings to the user home to avoid Codex MSIX
  LocalAppData redirection, which made the old helper invisible to Windows
  startup and Antigravity. Preserve existing mappings and trusted live commands.
- Install a per-user scheduled watcher with logon and one-minute recovery,
  unlimited runtime, battery support and single-instance handling. Refresh
  heartbeat status and exit on receiver failure so it can recover.
- Add bounded local outcome/phase/timing history and private server source
  history for accepted selections and device route reports. Tag desktop and
  Stream Deck requests; retain no prompts, credentials or raw routing IDs.
- Add on-demand `--diagnose` with process/heartbeat health and an optional
  metadata-only native Antigravity hook probe. Document the verified path
  defect and remaining native discovery/feature-flag uncertainty.
- Verified Windows scheduled launch, recovery after forced process termination,
  and an operator-confirmed Antigravity message. Full reboot remains untested.


## 2026-09-06 — Refresh GitHub homepage documentation

- Summarize desktop message selection, recovery, Stream Deck, animations,
  OpenRouter and alerts in the repository homepage. Correct outdated firmware
  HTTPS and display-hardware instructions to match the current implementation.


## 2026-09-06 — Isolate collector test runtime

- Place every collector runtime path, including optional SMTP secrets, in
  temporary test storage and clear inherited notification credentials. This
  fixes clean Linux CI permissions and keeps tests out of operator data.


## 2026-09-06 — Public release security review

- Harden both Windows Stream Deck helpers with canonical private IPv4 validation,
  direct connections, redirect rejection, no automatic Windows authentication,
  bounded requests, and generic network errors. Reject malformed profile IDs.
- Include desktop account-switching helpers and the fresh-computer recovery guide.
- Run Windows helper regression tests and real LVGL motion checks in CI.


## 2026-09-06 — Desktop switching recovery documentation

- Add a source-audited fresh Windows runbook covering prerequisites, private
  settings, custom-label identity mappings, installer limitations, hook trust,
  startup recovery, diagnostics, and changed-login/steering/reboot acceptance.
- Explicitly distinguish supported local Codex Desktop selection from browser
  ChatGPT and Antigravity primary-profile selection; record validation limits.

## 2026-09-06 — Stream Deck endpoint repair

- Correct the private Windows helper endpoint left on the former server LAN
  address. Verify account discovery and VBS selection without changing accounts.
- Document updating the shared Windows setting when the server address changes.

## 2026-09-06 — Stable transitions and connection diagnostics

- Replace costly full-screen movement with narrow-strip directional reveals.
  Coalesce navigation and preserve values on arrival/account changes.
- Remove post-arrival card jumps and pressed-control zoom allocations.
- Add reset, Wi-Fi, heap/stack, HTTP and redraw diagnostics plus failed telemetry
  backoff and clearer Wi-Fi-connected/server-unreachable messages.
- Repair private deployment binding/firmware endpoint after the server LAN
  address changed; no addresses or credentials are stored in tracked files.

## 2026-09-05 — Animated CYD screens

- Share bounded LVGL motion across the device and browser: launcher equalizer
  and node motion, ChatGPT drains, staggered Antigravity bars/cards, OpenRouter
  arc sweeps, exact-cent counters and seven-column chart growth.
- Throttle highlights on unchanged cached readings; preserve exact targets and
  immediately cancel unavailable OpenRouter readings.
- Keep LVGL drawing/touch sampling active during serialized HTTP worker waits;
  replace the blocking update LED delay and remove small container scrollbars.
- Add real LVGL/WASM motion checks and propagate compiler failures.

## 2026-09-05 — Steering-message selection and event ordering

- Select on every Codex UserPromptSubmit invocation: steering messages reuse
  turn IDs and were incorrectly discarded as duplicates.
- Order Antigravity events by message timestamp rather than transcript detection
  time, preventing delayed writes from overriding newer Codex submissions.
- Twelve helper tests pass, including same-turn account changes and delayed events.

## 2026-09-05 — Antigravity file-event fallback

- Replace the non-invoking Antigravity hook on this desktop with a windowless
  Windows directory-notification helper, automatically started at sign-in.
  No polling, screen access, or model requests; Codex hooks remain unchanged.
- Ignore historical messages at startup and deduplicate assistant continuations.
  Native file-event/live selection and continuation-isolation smoke checks pass.
- Retain only fixed diagnostic codes and hashed event markers. Disable only
  the old CYD Antigravity hook; preserve other customizations and the launcher.

## 2026-09-05 — Separate message-hook diagnostics

- Preserve each platform's latest fixed-code result independently, so a Codex
  reply cannot overwrite Antigravity troubleshooting evidence. Document a full
  Antigravity restart after initial hook installation.
- Use quoted forward-slash Windows paths for Antigravity hook command parsing;
  actual app invocation remains under verification.

## 2026-09-05 — Desktop message account selection

- Added optional Windows hooks that select an existing CYD profile on message
  submission, without a resident watcher, model call, or firmware change.
- Resolve managed local ChatGPT/Codex identity through official `account/read`
  on each submission; skip unknown or ambiguous mappings and non-desktop hooks.
- Select a configured Antigravity primary account on new explicit user-message
  metadata, deduplicating subsequent model invocations and stale activity.
- Added a private installer with configuration backups, preserved unrelated
  hooks, LAN-only requests, bounded failures, and tests for identity changes,
  ordering, deduplication, and network boundaries. Codex hook trust requires
  app review; actual cross-login desktop behavior needs a live switched-account test.

## 2026-09-05 — Faster Stream Deck account switching

- Send button requests directly with WinHTTP, preserving windowless launch, stable IDs, and private settings. Keep PowerShell discovery.
- Poll CYD commands at 400 ms with persistent TCP ownership, bounded LAN timeouts, and failure backoff; keep quota refresh at 3 seconds.
- Inline cached usage only for unseen commands, serialize selection writes, and fetch/render after route transitions before reporting state.
- Preserve legacy API clients and firmware fallback. Browser refresh remains independent; no measured end-to-end latency guarantee.

## Unreleased

- Propagated `CYD_MONITOR_TIMEZONE` into CLI profile execution environments (`TZ`)
  and Docker Compose service containers, ensuring OpenAI Codex 5-hour and
  weekly quota reset times render in the operator's configured local timezone
  rather than defaulting to container UTC.

- Account discovery now falls back to collected/remembered account names when
  no custom label is configured, so Stream Deck listings identify each account
  without manual labels. Custom labels retain priority.

- Added private authenticated account discovery and selection by stable profile
  ID for individual Stream Deck buttons. The existing windowless helper accepts
  an optional account ID, and its PowerShell companion lists current accounts.
  Existing cycling buttons retain their behavior; disabled/deleted accounts
  cannot be selected through the new route.

- Fixed ChatGPT usage quota bar length mismatch on the physical CYD: corrected
  `updateDashboard()` overwriting the 5-hour primary quota bar (`bar_primary`)
  with stale 296 px dimensions, restoring identical 440 px lengths and aligned
  bounds (x=8) for both 5-hour and weekly progress bars. Cleared scrollable
  flags on quota cards and added matching track border styling to the weekly bar.
- Improved physical CYD Wi-Fi reliability by disabling modem sleep on the
  continuously powered LAN display, recording disconnect reasons plus
  connected RSSI/channel diagnostics, and adding conservative staged recovery:
  passive auto-reconnect, explicit reconnect, one station-radio
  reinitialization, then a five-minute last-resort device restart only after a
  previously healthy connection. The launcher now reports `Recovering` while
  the fallback sequence is active.
- Added custom CYD Usage Monitor favicon and high-resolution app branding assets:
  multi-resolution `favicon.ico`, vector `favicon.svg`, raster `favicon-32x32.png`,
  `favicon-16x16.png`, `apple-touch-icon.png` (180x180), and master 1024x1024 / 512x512
  icons with public `/favicon.ico` route and dashboard `<head>` integration.
  Added complete cycle, cycle-badge, and sync action-icon families for Stream
  Deck and launcher shortcuts.
- Added a token-safe Windows Stream Deck helper and windowless WScript launcher
  for cycling through enabled Codex/Antigravity usage profiles without a
  console flash. Each press also commands both the physical CYD and browser
  preview into Usage Monitor.
- Added a persistent dashboard screen-orientation control that flips only the
  physical CYD by 180 degrees while retaining the 480x320 landscape layout.
  The CYD stores the last orientation in NVS for immediate reboot recovery;
  the upright browser preview uses a clear physical-orientation indicator.
- Added bidirectional screen-state synchronization for the launcher, Usage
  Monitor, OpenRouter, Home, and account selection. Browser LVGL interactions
  now command the physical CYD, while physical navigation reports through a
  private Bearer-protected endpoint so the preview follows on refresh.
- Fixed the email integration form losing previously entered values during the
  dashboard's 1.2-second status refresh. Once any email field is edited, the
  complete draft now remains browser-owned until a successful save or removal.
- Added protected dashboard email integration setup with Gmail/Google
  Workspace app-password and custom STARTTLS/implicit-TLS SMTP modes. SMTP
  credentials are written atomically as mode-`0600` private runtime data,
  never returned by the status API, and can be tested or removed from Alerts.
  Host environment configuration remains an explicit read-only override.
- Added current Codex quota support for both the rolling 5-hour window and the
  weekly window across normalized telemetry, the dashboard, physical CYD, and
  WebAssembly LVGL preview. The shared update-prompt responder remains part of
  the generic Codex collector path, so it applies automatically to every new
  isolated Codex profile.
- Persisted the last CLI-visible account identity in each profile after a
  successful capture. Later collection failures, incidents, alerts, the
  dashboard, and the device API now identify the affected account instead of
  falling back to a generic provider label.
- Added dashboard-to-device app commands and an OpenRouter **Show on CYD**
  control. The physical display polls the private Bearer-protected command
  endpoint, while the same action switches the live LVGL preview immediately.
- Added an independent TLS SMTP fallback when a WAHA delivery fails, including
  per-alert deduplication, protected dashboard health, and an explicit test
  action. SMTP credentials remain host-only and are never persisted in monitor
  state or inherited by provider CLI processes.
- Fixed Codex usage collection with newer CLI releases that show an
  interactive self-update prompt before `/status`: the collector now selects
  **Skip** once per capture and leaves CLI upgrades under operator control.
  Failed WAHA deliveries remain pending for retry, undelivered outages no
  longer produce misleading recovery messages, and the dashboard overview
  turns red when alert delivery itself is failing.
- Fixed physical and simulated launcher navigation by making decorative tile
  children click-through, using TFT_eSPI's full resistive-touch calibration
  transform, clearing competing route requests, and enlarging the Home targets.
  OpenRouter taps now open OpenRouter, and Home reliably returns to the
  launcher on the Hosyond 4.0-inch display.
- Corrected the physical firmware target for the Hosyond/LCDWiki E32R40T
  4.0-inch board: ST7796S at 320x480, backlight on GPIO27, red status LED on
  GPIO22, and XPT2046 resistive touch sharing the LCD SPI bus. Removed the
  incompatible GT911/ESP32-3248S035 probing path that could interfere with
  touch chip select during startup, and lowered the upload speed from 921600
  to a more reliable 460800 baud for the onboard CH340C bridge.
- Debounced CLI outage notifications until three consecutive collection cycles
  fail (configurable from 1–10), while retaining first-failure diagnostics in
  incident history. One-cycle Antigravity authentication/eligibility glitches
  now recover silently instead of producing misleading alert/recovery pairs.
- Added durable, bounded collector incident history with privacy-safe terminal
  evidence, host-only redacted diagnostic captures, repeated-poll counts,
  recovery durations, and a protected Alerts dashboard timeline. Redesigned
  WhatsApp alerts with clear emoji/formatting, observed failure evidence,
  diagnostic IDs, configurable local timestamps, retry behavior, and explicit
  recovery explanations that do not imply credentials were repaired when a
  later poll simply succeeded.
- Updated the pinned production server image from
  `python:3.11.15-slim-bookworm` to `python:3.14.0-slim-bookworm` and verified
  the current server test suite and container startup on Python 3.14.
- Fixed the WebAssembly CI smoke test to validate the stable semantic module
  exports exposed by the generated Emscripten wrapper instead of brittle,
  optimization-dependent raw WASM export letters.
- Fixed Usage Monitor pointer handling in the browser LVGL preview by keeping
  the full-screen Antigravity content layer behind its Home and Next controls,
  and connected Next to the dashboard's active-profile selection.
- Tightened the Accounts layout: all four isolated-profile actions remain on
  one row, the redundant connected/quota text was removed, and the OpenRouter
  removal action now sits as a compact header control.
- Added an independent OpenRouter launcher app with an LVGL balance arc,
  today/week/month spend cards, a seven-day bar chart, and top-model summary on
  both the physical CYD and interactive WebAssembly preview. The host collector
  now aggregates documented OpenRouter credits, key usage, and completed-day
  activity using a dashboard-managed Management API key kept in private
  runtime storage; new route-isolated APIs expose only normalized telemetry.
- Added protected OpenRouter setup, replacement, removal, overview telemetry,
  collector aggregation tests, device/API security tests, and the `O` Wokwi
  shortcut. OpenRouter remains independent from Codex/Antigravity profile
  selection and performs no account or key mutations.
- Added semantic Wokwi serial shortcuts that simulate the launcher and Usage
  Monitor touch targets: `U` opens Usage Monitor, `H` returns Home, `N` switches
  accounts, and `?` prints help. Renamed the dashboard Flash tab to
  **Utilities** and added the same keybind cheat sheet above the flashing guide.
  The live LVGL preview now stays centered in the right rail at normal desktop
  widths, renders slightly larger for inspection, and uses simulator-only
  Antigravity grid gutters so its right and bottom card borders are not clipped.
- Added a pastel LVGL app launcher as the deterministic CYD boot screen, with
  a compact Canvas-drawn Usage Monitor icon, reusable app descriptors, animated
  tile/screen transitions, background Wi-Fi connection, app-scoped polling,
  release-latched touch startup, and a Home control. The WebAssembly preview is
  now pointer-interactive and mirrors launcher navigation.
- Restored fast LAN-only CYD and Wokwi telemetry: the server now has isolated
  dashboard and device listeners, Compose binds the Bearer-protected device API
  only to a configured private address, firmware rejects non-RFC1918 endpoints,
  and only the browser dashboard remains available through Cloudflare Access.
- Removed device-side TLS certificates, NTP, Cloudflare Service Auth headers,
  and the separate Wokwi TLS build; local polling and account switches now use
  the same short-timeout HTTP/1.1 path on physical and simulated displays.
- Replaced the rotating Wokwi leaf-certificate pin with normal leaf,
  hostname, and time validation against the narrower long-lived GTS WE1
  issuing CA; physical firmware retains public-root validation.
- Added HTTP/1.1 connection reuse across CYD polls and account changes, and
  made `next-account` return the new display payload so a switch needs only
  one request and no repeated handshake.
- Replaced whole-screen account switching with a dedicated header arrow
  button, preventing ordinary touches and startup samples from issuing
  unintended actions while retaining the `n`/space simulator shortcuts.
- Fixed Cloudflare HTTPS validation by replacing the unrelated GlobalSign ECC
  root with the Google Trust Services Root R4 trust anchor used by the live
  edge chain, while keeping certificate verification fail-closed; added a
  credential-free helper for checking a hostname against that root.
- Moved the independently wired XPT2046 touch controller to HSPI while the
  display remains on VSPI, eliminating the duplicate ESP32 APB callback warning.
- Added an admin-protected dashboard **Flash** tab, a canonical CYD provisioning
  guide, a protected Markdown documentation route, container packaging, and
  regression coverage for guide authentication and availability.
- Increased the ESP32 HTTPS, TLS-handshake, and NTP timeouts for Wokwi's slower
  CPU/network emulation and added credential-safe serial diagnostics for
  lower-level TLS failures without weakening certificate validation.
- Added a hardened Cloudflare Tunnel deployment: the application now stays on
  a private Compose network with no published host port, a pinned
  `cloudflared` connector uses a separate runtime tunnel token, and documented
  ingress separates the identity-protected dashboard from the route-limited
  device API.
- Added optional Cloudflare Access service-token headers to ESP32 requests and
  bounded NTP synchronization before HTTPS certificate validation, retaining
  the independent CYD Bearer token and fail-closed TLS behavior.
- Added a public-safe deployment runbook covering the two-stage dashboard
  login, private credential locations, remote-only Tunnel boundary,
  verification matrix, rollback procedure, and pre-push secret checks.

- Hardened dashboard and device authentication: enforced bounded secret
  lengths, kept the CYD API Bearer-only, added a separate Basic-authenticated
  admin preview endpoint, required JSON plus a custom CSRF header for
  administrative writes, capped request bodies, validated identifiers, and
  added restrictive browser security headers.
- Moved temporary CLI sign-in replies into a private one-time inbox, stopped
  returning login URLs, device codes, or transcripts after a workflow ends,
  bounded retained workflow history, and made profile removal delete its
  isolated CLI credential directory as well as local telemetry.
- Added cross-process locked, atomic JSON storage and serialized collection so
  the server and collector cannot lose concurrent state updates or launch
  duplicate workflows.
- Restricted collector subprocess environments to an allow-list, removed the
  unsafe Codex approval bypass, selected read-only/no-approval execution, hid
  local executable paths from public telemetry, redacted echoed WAHA keys,
  cleaned up child processes, and distinguished successful sign-in from
  timeout or early process exit.
- Hardened the ESP32 network path: HTTPS now requires an explicitly configured
  trusted CA, plaintext HTTP requires a development-only opt-in, response sizes
  are capped, stale data is replaced by a clear error state, Wi-Fi reconnects
  automatically, and touchscreen callbacks no longer perform blocking network
  requests.
- Updated the WebAssembly simulator to use real elapsed frame time and aligned
  its Codex threshold colors with the firmware. The existing mascot pixel art
  and promotional screenshot were intentionally left unchanged.
- Pinned the ESP32 platform, Arduino libraries, XPT2046 driver commit, Python
  container image, and Emscripten toolchain; removed the user-specific SDK
  path from the build script, and selected the standard OTA-capable
  `min_spiffs` partition layout to restore firmware development headroom.
- Added concurrency, HTTP security, workflow privacy, credential-deletion, and
  collector-isolation tests plus pinned GitHub Actions CI and Dependabot
  configuration.
- Added public contribution, conduct, security-reporting, and third-party
  notice documents; hardened the container with a read-only filesystem,
  dropped capabilities, process limits, a health check, and an init process.
- Fixed the Dockerfile paths to match the Compose build context so a clean
  public checkout can build both services successfully.
- Normalized generated simulator JavaScript whitespace so clean rebuilds pass
  repository diff checks consistently across local and CI environments.
- Fixed clean-runner CI portability by isolating every alert test file in its
  temporary directory and accepting Emscripten's setup diagnostics before its
  pinned version line.
- Made simulator compilation order and source paths independent of the runner
  filesystem, and updated pinned GitHub actions to their Node 24-compatible v7
  releases. CI now validates regenerated WebAssembly by syntax and exported-ABI
  smoke tests instead of requiring cross-operating-system byte identity.

- Added a GitHub-facing project overview, dashboard screenshot, and the
  permissive MIT License.

- Prepared the repository for public distribution: removed host-specific
  deployment details and obsolete tutorial artifacts, made Docker paths
  configurable, and now require `CYD_API_TOKEN` for device API access.

- Changed the default collector cadence to 90 seconds and added a live
  Overview flip-style countdown/collecting indicator backed by collector
  schedule state.

- Fixed WAHA delivery configuration to require the actual connected WAHA
  session name rather than assuming a `default` session, retain safe WAHA
  validation detail in the dashboard on a rejected message, and process test
  alerts immediately rather than behind scheduled quota polling.
- Replaced the Overview account list with Stitch-informed telemetry cards,
  including Codex quota/credits cards and the Antigravity four-metric matrix.
- Reused the exact CYD mascot pixels for web provider badges and added a
  simulator-only edge gutter for the Antigravity layout.
- Reworked the dashboard information architecture: Overview now lists all
  account quotas and display actions; connection activity lives in Accounts
  and stays open while a workflow requires attention without fighting the
  user's disclosure control.
- Grouped Accounts by Codex and Antigravity, added structured provider-choice
  buttons, color-coded account controls, and disabled Connect for healthy
  authenticated accounts.
- Corrected the WebAssembly preview bezel sizing and disabled simulator-screen
  scrolling so the Antigravity right-side quota cards are not clipped.

- Redesigned the dashboard as a three-pane operations console based on the
  tracked Stitch design system while preserving its live LVGL simulator and
  existing collector/auth flows.
- Added an Alerts view that edits the persistent WAHA group ID and queues an
  explicit test alert through the collector without exposing the WAHA API key.
- Collapsed connection activity when idle; it opens automatically only while a
  sign-in, collection, or failure needs attention.
- Added a dedicated LVGL error view for unavailable collector data and removed
  the obsolete exhausted-quota warning glyph.
- Made the dashboard simulator use the Antigravity mascot bitmap, disabled
  LVGL scrollbars in its quota grid, and disabled stale browser caching of its
  JavaScript/WASM assets.
- Reduced physical CYD display polling from 15 seconds to 3 seconds so a
  dashboard **Show** selection is reflected promptly.
- Added optional WAHA WhatsApp failure/recovery alerts with durable
  deduplication and dashboard delivery status.
- Added `.env.example`, project-level agent instructions, and the mandatory
  documentation-update policy.
