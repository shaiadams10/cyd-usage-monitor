# CLI Profile Authentication Guide

Do not copy browser cookies, OAuth refresh tokens, `auth.json`, `adc.json`, or
provider client secrets into this project.

Open the protected monitor dashboard, create an isolated Codex or Antigravity
profile, then choose **Sign in**. Complete the provider’s browser or device-code
flow shown by the host-side CLI collector. Credentials stay in the collector
profile on the private monitor host and are refreshed by the CLI itself.

If a provider asks for a device or authorization code, enter it into the
dashboard’s login input for that request. The server writes it to a private,
one-time inbox; the collector consumes and deletes it, and the admin status API
never returns it. Login URLs, device codes, and provider transcripts are
cleared from runtime state when the workflow completes, fails, expires, or is
cancelled.

Never paste credentials into source files, issue trackers, logs, or chat.
