# Changelog

## Unreleased

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
