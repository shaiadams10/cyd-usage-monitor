# Account wake-ups

Updated 2026-11-05. The operator authorized manual and scheduled wake-ups across
Codex, Antigravity and Claude Code. This replaces the deferred Codex-only design.
Collection remains read-only; wake-ups are a separate, explicitly controlled
feature that consumes subscription usage.

## Operator interface

Open **Wake-ups** from the protected dashboard. The dedicated page works on
phones and desktop browsers and provides two separate actions:

- **Send now:** select accounts, review them and submit one request.
- **Schedule:** select accounts, choose a one-time date or recurring weekdays,
  set the time and an IANA timezone, then save. Pause or delete schedules anytime.

The message defaults to `say OK` and can be edited (1–500 plain-text characters).
The exact text is retained per schedule/job and included in duplicate-request checks. Account rows show the selected model and explain
when the installed CLI cannot meet the single-request requirement. Schedules can
be saved while sending is stopped. The master switch starts disabled; enabling
it permits eligible queued requests and future schedules. Saving a schedule does
not enable sending. Stop cancels queued requests and prevents unreserved sends.
A prompt already reserved or running may finish; it cannot be unsent.

Times follow each schedule's timezone. A nonexistent spring-forward time is
skipped; the first occurrence of a repeated autumn time is used. Runs missed by
more than two minutes are skipped, with no catch-up batches after downtime.
An on-time claimed batch has 180 seconds per selected profile, capped at 15
minutes, to complete serial checks and bounded sends. Processing jobs are never
reclaimed after interruption; this budget does not extend queued catch-up time.

## Delivery and eligibility

Only the collector process can send. HTTP handlers create durable jobs; they
never invoke a model. Before an attempt the collector refreshes official CLI
quota panels and verifies the account's CLI-visible identity. The identity is
hashed with the provider for duplicate-account protection. Labels are never
account identities, and duplicate profiles share the same guards.

Scheduled sending requires fresh healthy same-account quota data and available
weekly allowance. Active or unclear five-hour windows do not block a single
scheduled attempt. Exhausted/unavailable weekly quota and stale/invalid panels
are skipped. For current Claude Code panels, numeric zero used with **no reset
line**, corroborated in two independent `/usage` requests, is interpreted as
no active five-hour window. This is an interpretation of the CLI display,
not a provider guarantee. A displayed remaining 100% alone is insufficient:
raw fractional usage is retained, so 0.4% used cannot establish idle by rounding.
Any reported reset means the window is active, even at displayed zero usage.

## Durable duplicate protection

`server/wakeups.py` stores schedules, jobs, attempts and pauses in the private
`wakeups.sqlite3` ledger with SQLite FULL synchronization and process-safe
transactions. The file is created with private permissions. A missing or corrupt
ledger after initialization stops sending instead of silently clearing history.

- Reserve and commit an attempt **before** launching a CLI.
- At least five hours and two minutes between attempts to the same account.
- At most five attempts per account in a rolling 24 hours.
- Manual actions, overlapping schedules, duplicate profiles and multiple workers
  all use the same guard. Repeated browser submissions retain a request ID.
- A timeout, crash, lost response or unexpected CLI output stays uncertain.
  There is no automatic retry or automatic reclamation of reservations.
- Uncertain accounts remain paused until the operator acknowledges the result
  after the minimum interval. Acknowledgement preserves safety history.
- Pause/delete/edit and the master switch are checked again after a slow
  preflight, before reserving. Clock jumps stop sending.

These safeguards provide at-most-one **attempt**, not exactly-once delivery.
A crash between durable reservation and launch may produce no request. A human
can concurrently start a window outside the monitor; that race cannot be made
atomic with provider state. Prefer a missed wake-up to an unintended repeat.

## Selected models and CLI execution

Choose a model and reasoning level separately for each selected provider. A
provider choice applies across that provider's selected accounts. Choices are
read from official CLI model listings, with per-model supported effort levels;
the catalogue is cached briefly and checked for each account before sending.
No model or reasoning is selected implicitly. Schedules store the exact choices,
and jobs snapshot them, so later UI selections cannot retarget an earlier job.
Old schedules without explicit choices require editing before they can run.

The operator's single-message requirement means one submitted operator-selected prompt,
without an automatic application resend, model fallback or resume loop. Native
transport retry controls are disabled where supported and verified. Every CLI
process has a deadline and its process group is killed on timeout. A timeout or
unreadable result is uncertain, pauses the account and is never replayed.
The selected model's availability and actual response are not guaranteed by a
successful catalogue lookup; a rejected model is reported for that account.

Claude disables tools, MCP servers, hooks, fallback chains and background work,
uses a minimal system prompt, one turn and a small output cap. Codex uses an
isolated ephemeral session and explicit zero HTTP/stream retry controls. The
installed CLI's remaining agent behavior is bounded by the deadline. Provider
implementation and native retry limitations are shown in the interface where
applicable; one process is not advertised as exactly one underlying HTTP call.
Antigravity has no configurable native retry count in the deployed interface.
Stop it on observed retry/error/tool events and after 27 seconds; an unreported
transport retry cannot be ruled out. Do not describe that as native retry-zero.

Failures and uncertain outcomes are retained with account, selected model,
reasoning and a safe explanation. The current batch continues for other accounts.
A failed scheduled batch pauses its source schedule, and actual failed/uncertain
attempts pause that account. Ordinary active-window or exhausted-quota skips appear in the same run summary,
without individual failure alerts. Notification events are durably claimed before one
attempt through configured WhatsApp/email alerts; delivery failure remains
visible in the page, without automatic notification replay after uncertainty.

## Verification and maintenance

Run deterministic safety tests from the repository root:

```powershell
python -m unittest discover -s cyd-usage-monitor/server -p test_wakeups.py
python -m unittest discover -s cyd-usage-monitor/server -p test_wakeup_cli.py
python -m unittest discover -s cyd-usage-monitor/server -p test_wakeup_codex.py
node --check cyd-usage-monitor/server/static/wakeups.js
```

The optional native probe uses **only** an isolated temporary HOME, fake API key
and local HTTP server. It never signs in or sends to Anthropic. Set
`CYD_TEST_NATIVE_CLAUDE=1` and `CYD_TEST_NATIVE_CLAUDE_BIN` to the native executable,
then run `test_wakeup_cli.py`. It counts requests for a successful stream, HTTP
502/429/529, a truncated stream and a hallucinated tool call. Every case must
produce exactly one local model request with no tools and the pinned model.
Run it before adding an installed CLI version to the allowlist.

Native probes passed for workstation 2.1.316 and deployment-host 2.1.311 with
only synthetic loopback requests. No real-provider wake-up pilot was performed
during development. Keep the master switch stopped until choosing an eligible
account for a controlled first use. An exhausted weekly quota is skipped even
when its five-hour usage is zero.

## References

- [Claude environment and retry controls](https://code.claude.com/docs/en/env-vars)
- [Claude CLI flags](https://code.claude.com/docs/en/cli-reference)
- [Claude model selection](https://code.claude.com/docs/en/model-config)
- [Codex configuration](https://learn.chatgpt.com/docs/config-file/config-reference)
- [Antigravity headless mode](https://antigravity.google/docs/cli/headless/)

The public documentation contains no private profile identities, endpoints,
runtime schedules or deployment targets.


Codex discovery and sending may use `CODEX_WAKEUP_BIN` from the optional
`CODEX_WAKEUP_HOST_DIR` mount, while quota reads use `CODEX_BIN`. The deployed
0.166.0 catalogue includes current models; 0.147.0 remains the quota reader
because its visible startup banked-reset count is omitted by 0.166.0.


Run notifications are now one durable summary, covering all outcomes grouped by
provider and model. Scheduled summaries retain schedule name/local planned time;
Send now summaries explicitly identify the immediate action. A local Pillow JPEG
shows provider marks and highlighted reset badges. One read-only postflight can
confirm the same account's next reset; otherwise completion+5h is explicitly an
estimate. WAHA receives image+caption in one message; existing email fallback gets
inline image and full plain text. No inference is used to render reports.

Each summary is committed with job outcomes and claimed before external delivery;
uncertain delivery is not replayed. Expired interrupted work retains completed
results and reports unknown reservations without submitting prompts again. The
master preference survives restarts; clock-safety holds are separate and require
operator acknowledgement. Individual uncertain accounts/failed schedules remain
paused independently of the master preference.


Provider Defaults now persist operator model/effort choices per provider on the
server. New manual and scheduled forms prefill them; existing jobs and schedules
retain their snapshots. Removed models/efforts remain visible as unavailable and
require explicit replacement, never silent fallback.

The operator clarified Send now should attempt one prompt regardless of current
five-hour-window state, including an already active window. Quota-window and
weekly-remaining eligibility gates originally applied to schedules. On November
5 the operator authorized scheduled attempts with active or unclear five-hour
windows too; only the fresh weekly-quota gate remains. Both paths retain
fresh official identity/model verification and all durable duplicate/interval/
uncertainty guards. A human-readable reset clock paired with rounded-full quota
is not proof of either active or idle state. Do not infer timer restarts.

Receipts now use a compact light report layout with provider/account rows and an
aligned reset-time column. The timezone appears once in the header. WhatsApp text
uses bold section/account labels, status emojis, model subheadings and quoted
failure reasons consistent with collection alerts; email includes formatted
headings, full plain text and the inline image.

Immediate Codex/Claude preflight now checks fresh identity through documented
local `account/read` / `auth status`, reusing saved quota facts only if healthy,
same-account and under two minutes old. Scheduled eligibility still requires a
fresh panel. Codex uses `account/read` again immediately before submission rather
than launching another quota screen. This metadata path never creates a thread
or turn and never collects quota through account APIs.

Save confirmed sends before reset verification and overlap at most three
read-only reset checks. Activity keeps one row per selected account through
checking, sending and reset verification; a live reservation is not an
interruption. Fresh same-account clock labels remain visible as CLI reported
when rounded-full quota cannot prove activity. Reset-read failure cannot turn a
confirmed send into a failure or cause another prompt. Keep one final receipt.

Account holds retain the distinction between a confirmed failure and an unknown
outcome. Later blocked requests show the original confirmed cause as failed,
without suggesting a new provider submission; uncertain attempts stay unknown.
No guards are removed and there is no automatic retry/resume. For usage/rate
limits, annotate receipts with fresh same-account weekly/five-hour exhaustion
and each reported reset, reusing fresh cached quota or one read-only panel check.
Do not infer the affected window from the timer or a disabled dependent pool.
Unconfirmed attribution is explicit; continue with other accounts and one receipt.
