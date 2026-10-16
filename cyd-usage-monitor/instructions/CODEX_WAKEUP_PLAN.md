# Codex window wake-up plan

Status: draft for further discussion; implementation deferred. Updated 2026-10-16.
The current work fixes collection and diagnostics; it must not send model messages.
Do not implement or enable wake-ups until the operator asks to proceed.

## Purpose and operator knowledge

Keep eligible, configured Codex accounts' five-hour windows moving with minimal
usage. The operator confirms that Luna requests start the five-hour window.
Use the official authenticated CLI, never imported credentials or private APIs.
This does not increase allowance or bank unused windows. Requests consume usage.

## Scheduling direction

- Monitor continuously; send conditionally for each distinct account. Exact
  active hours, initial activation, buffer and final rollout remain to be settled.
- Follow fresh, corroborated CLI reset times instead of a fixed five-hour cron.
  Normal user activity that already started a new window makes a wake-up unnecessary.
- Recheck immediately before sending. A concurrent human request cannot be made
  atomic with the monitor; one unnecessary request remains possible.
- Weekly exhaustion blocks wake-ups. Weekly refill alone never triggers one.
- Unexpected provider resets cause a fresh evaluation, never clear safety counters.
- A rounded 100% reading alone does not establish an idle window. Unclear,
  missing, stale, or contradictory reset information blocks sending.

## Required limits

- At most one attempted wake-up per account/window, with a durable minimum
  interval of five hours plus a small buffer (proposed: two minutes).
- At most five attempts in any rolling 24 hours per account. Duplicate profiles
  share the same account guard. Manual actions obey the same restrictions.
- Reserve and persist an attempt before launching the CLI under a process-safe
  account lock. Reservations survive restarts and are never automatically reclaimed
  after an uncertain result. No catch-up batches after downtime.
- Unknown outcome, timeout, storage failure, ambiguous identity or clock anomaly:
  stop that account and show the reason. Never repeat until something works.
- Disable and verify CLI transport/stream retries as well as scheduler retries.
  One process launch is not proof of one provider request. If the installed CLI
  cannot enforce the required bounds, leave sending disabled.

## Request and visibility

Pin an available Luna model, Standard speed, lowest supported reasoning; no
expensive-model fallback. Use a fresh minimal session asking only "Reply exactly
OK." Disable tools, plugins, browsing and repository context. Apply a short
deadline; do not promise a hard token budget that the CLI cannot enforce.
Record attempt ID, reason, model, timestamps, outcome, available token usage,
next eligibility and skip/pause reason in the protected diagnostic timeline.
Expose a master stop and per-account controls, initially disabled.

## Delivery sequence and verification

1. Repair diagnostics and Antigravity/Codex collection first.
2. Build an observation-only scheduler showing decisions without sending.
3. Test duplicate workers/profiles, repeated UI actions, restarts, corrupted or
   unavailable state, clock changes, resets, exhausted quotas and lost responses.
4. Run one controlled account pilot to measure overhead and observe reset behavior.
5. Enable only after review of timing, guard verification and pilot evidence.

Reference documentation: [CLI automation](https://learn.chatgpt.com/docs/non-interactive-mode),
[usage limits](https://learn.chatgpt.com/docs/pricing),
[configuration and retry controls](https://learn.chatgpt.com/docs/config-file/config-reference).
