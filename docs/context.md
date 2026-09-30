# Project Context

## Current State

CYD Usage Monitor is the sole project in the current public repository tree.
It includes the collector, authenticated dashboard/device API, ESP32 firmware,
shared LVGL WebAssembly preview and optional Windows account-switching helpers.

## Recent Changes

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
