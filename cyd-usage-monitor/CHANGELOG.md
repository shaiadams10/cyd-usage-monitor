# Changelog

## Unreleased

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
