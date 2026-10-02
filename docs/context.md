# Project Context

## Current State

CYD Usage Monitor is the sole project in the current public repository tree.
It includes the collector, authenticated dashboard/device API, ESP32 firmware,
shared LVGL WebAssembly preview and optional Windows account-switching helpers.

## Recent Changes

### 2026-10-02 — Antigravity Retry Logout Guard
- Traced repeated disconnection to a transient user-info TLS timeout followed
  by the collector sending Escape on the CLI sign-in screen. CLI logs then
  recorded logout; the saved session disappeared despite a valid token.
- Guard Escape with a complete quota panel from the current request, preserving
  modal confirmation without sending destructive keys during authentication.
- Passed 77 server tests, a deployed Linux PTY sign-in/no-Escape regression,
  and authenticated dashboard/device API plus unauthorized rejection checks.
- Preserved remote source and rollback image; deployed only the collector.
  Existing removed sessions require the official dashboard reconnect flow.
- Publication checks: 77 server tests, Gitleaks public-tree scan, added-text
  privacy review, whitespace checks and Brain validation passed.
- Files: cyd-usage-monitor/{server/collector.py,server/test_collector.py,
  README.md,CHANGELOG.md}, docs/{context.md,map.md}.

### 2026-09-30 — CYD Notification Flood and Antigravity Modal Recovery
- Fixed fallback email deduplication to use account/outage identity rather than
  changing retry text; retain a bounded durable history across interleaved profiles.
- Close Antigravity's /usage modal before independent requests, allowing real
  refills to confirm with small consumption tolerance and matching account identity.
- Passed 75 server tests and live captures of both enabled Antigravity profiles.
  Backed up remote source/state and rollback image, migrated the existing email
  receipt, and deployed only the collector to the configured private host.
  All six enabled CLI profiles recovered/continued healthy; email timestamp did
  not advance. App remained healthy and protected API smoke checks passed.
- Both configured WAHA sessions still exist but require QR pairing. Container
  uptime and storage mount are intact; retained logs show no initiating unpair
  event, so the cause is unresolved. No WAHA session was changed or removed.
- Publication checks: 75 server tests and 21 helper tests passed; Gitleaks
  found no secrets, diff whitespace checks passed, and Brain is healthy.
- Files: cyd-usage-monitor/{server/collector.py,server/test_collector.py,
  README.md,CHANGELOG.md}, docs/{context.md,map.md}; private remote backups.

### 2026-09-30 — README Device Artwork
- Use the operator-provided Codex/Antigravity device illustration in the public
  homepage and operator README; label it illustrative with example accounts.
- Preserve the existing dashboard screenshot as a documentation asset.
- Verified PNG format/dimensions, byte-identical copy and README asset paths.
- Files: README.md, cyd-usage-monitor/{README.md,CHANGELOG.md},
  docs/{images/cyd-usage-monitor-hero.png,context.md,map.md}.

### 2026-09-30 — CYD-only Public Release and Homepage
- Removed unrelated ESP32 projects from the current public tree, preserving
  the operator's local workspace and existing Git history.
- Published pending CYD quota-confirmation fixes, reset badges and matching
  WASM assets. Reset activation is absent; counts are read-only.
- Rebuilt the homepage with a screenshot, provider table, architecture diagram,
  setup paths and documentation index. Corrected current E32R40T hardware and
  collection timing; added a CI publication-scope guard and footer ABI check.
- Replaced workspace-specific instructions/context/map with CYD-only public
  guidance. Private operator configuration and duplicate copies are excluded.
- Validation: 72 server tests and 21 Windows helper/transport tests passed;
  README paths/anchors and dashboard JavaScript syntax passed. Public tree
  contains 79 CYD/support files; Gitleaks found no secrets. Prior firmware and
  LVGL builds passed, and CI repeats them for this published commit.
- Files: README.md, AGENTS.md, CONTRIBUTING.md, .gitignore,
  .github/workflows/ci.yml, cyd-usage-monitor/{README.md,CHANGELOG.md,
  instructions/FLASHING_GUIDE.md,server/,src/,simulator/,platformio.ini},
  docs/{context.md,map.md}; removed unrelated project directories.

## History Summary

- 2026-09-29: Confirmed Codex reads across independent requests, rejected
  incomplete/out-of-range quotas, labeled retained data Last confirmed,
  snapped bars on account changes and warned on exhausted weekly quota.
  Passed 72 server tests, firmware and LVGL/WASM checks; deployed and flashed.
- 2026-09-29: Added read-only available reset counts beside credits, white
  footer titles and blue badges on physical and browser interfaces.
- Earlier CYD releases added independent profile collection, private device
  routing, OpenRouter telemetry, alert delivery, Windows account selection,
  Stream Deck controls and shared LVGL animations. See the project changelog.
