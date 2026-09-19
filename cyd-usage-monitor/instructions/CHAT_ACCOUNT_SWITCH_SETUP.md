# Desktop message account switching: fresh Windows setup

This is the recovery runbook for the implementation in `scripts/chat-account-switch.py`,
`install-chat-account-switch.py`, `watch-antigravity-messages.py`, and
`install-antigravity-startup.ps1`.
Run commands in PowerShell from the repository root.

## What this integration does

A local Codex Desktop submission selects the CYD profile mapped to the currently
signed-in ChatGPT email. Identity is queried again for every submission, including
steering messages in an active turn. It uses the configured desktop authentication
home and official local `account/read`; it does not determine identity from message
text or the task's project. Browser ChatGPT, mobile ChatGPT, remote/cloud tasks,
CLI-originated hooks, and externally managed app tokens are not supported by this
integration. Separate homes require configuration matching the submitting desktop.

Antigravity selects one explicitly configured primary profile on a new explicit
user message. It does **not** discover or follow changes of Google login. Its
windowless Python process waits for Windows file notifications, reads bounded
transcript tails, and ignores assistant continuations and existing messages at
startup. Transcript format compatibility depends on the installed app version.

Selection requests go to the private CYD API and queue a Usage Monitor display
command. A successful API request does not by itself prove the physical screen
received it. Quota collection and provider authentication on the server are separate.

## 1. Recover prerequisites

- Obtain a repository copy containing all four scripts above and
  `scripts/test_chat_account_switch.py`. An uncommitted/untracked local script is
  absent from a fresh clone; preserve it in a private backup or include it in the
  repository before retiring the old computer.
- Install Windows Python 3.10 or newer with `python.exe` and sibling `pythonw.exe`.
  Use a stable installation path: the installer records the Python path in hooks
  and Windows startup. No third-party Python packages are required.
- Install and sign into Codex Desktop with managed local ChatGPT authentication.
  Launch Antigravity and send an initial message so its local brain directory
  exists. This initial message will not be replayed after setup.
- Confirm the existing monitor server is running, its private device listener is
  reachable from this computer, and the CYD already receives usage. Use the
  [project README](../README.md) and [token guide](TOKEN_GUIDE.md) if rebuilding the
  server too. Authenticate each server profile through the official dashboard
  login flow; a desktop login does not create a server quota profile.
- Obtain the server's current private device URL and `CYD_API_TOKEN` from private
  operator records. Keep a separate encrypted backup of those records and
  `docs/map.local.md`; Git intentionally excludes them. Do not place a server
  Tunnel token on the workstation.

## 2. Restore Windows user settings

Open **Edit environment variables for your account** and create these User variables:

| Name | Value to supply privately |
| --- | --- |
| `CYD_API_TOKEN` | The existing token shared by the monitor server and CYD firmware |
| `CYD_USAGE_MONITOR_NEXT_ACCOUNT_URL` | `http://<private-ipv4>:<device-port>/api/v1/next-account` |

Replace the placeholders with the actual private listener address. Only RFC1918
IPv4 HTTP endpoints are accepted; dashboard URLs, DNS names, HTTPS, proxies and
redirects are not supported by this helper. It reads User settings on each request.
Changing only the server `.env` does not update these workstation settings.

Discover profiles (the output contains private labels and IDs; keep it local):

```powershell
& ./cyd-usage-monitor/scripts/stream-deck-next-account.ps1 -ListAccounts
```

Check enabled profiles against the dashboard. IDs survive renaming but change if
a profile is deleted and recreated. Fix connectivity/token errors before installing.

## 3. Prepare mappings and install

Automatic Codex mapping requires an enabled profile label containing exactly one
email address. A custom label that hides the email needs manual mapping below.
Duplicate profiles for the same email are ambiguous and will not be selected.

The installer currently requires a valid Antigravity profile even for a Codex-only
use case. If there is exactly one enabled Antigravity profile it chooses it. If
there are several, create `%USERPROFILE%\.cyd-usage-monitor\chat-switch.json` first
with this minimal JSON, substituting the intended enabled ID from discovery:

```json
{"antigravity_profile": "<enabled-antigravity-profile-id>"}
```

With zero enabled Antigravity profiles, this installer cannot complete; configure
one on the monitor first. Do not assume there is a Codex-only installer flag.

```powershell
python ./cyd-usage-monitor/scripts/install-chat-account-switch.py
```

By default it uses `%USERPROFILE%\.codex` and the most recently modified
`%LOCALAPPDATA%\OpenAI\Codex\bin\*\codex.exe`. If your desktop uses other paths,
pass `--codex-home` and `--codex-executable` with those actual paths. It does not
infer a custom home from `CODEX_HOME`. A missing executable/directory causes failure.

The installer copies helpers into `%USERPROFILE%\.cyd-usage-monitor`, merges Codex
`UserPromptSubmit` hooks, backs up existing hook/configuration files, and installs
Antigravity startup as the current user's scheduled task
`CYD Antigravity Messages`. The task has a logon trigger, one-minute recovery
trigger, restart-on-failure, unlimited runtime, battery support and IgnoreNew
instance handling. Installation replaces only the verified watcher process and
removes its legacy Run entry after task registration succeeds. Only its own ineffective Antigravity global hook is
disabled. **Review and trust the Codex hook in the app's Hooks settings or `/hooks`.**
A missing trust UI or hook support must be resolved in the app before verification.

### Custom labels, unmapped identities, or ambiguous accounts

The private JSON `codex_accounts` object maps SHA-256 hashes of
`email.strip().casefold()` encoded as UTF-8 to lists of stable Codex profile IDs.
Use the exact email of the signed-in ChatGPT account, not a display name. Compute
a hash locally without placing the email in shell history:

```powershell
python -c "import hashlib; from getpass import getpass; print(hashlib.sha256(getpass('ChatGPT email (hidden): ').strip().casefold().encode('utf-8')).hexdigest())"
```

Back up the private JSON, then edit it with a local editor, preserving all other
keys. Insert the hash and the matching enabled ID from account discovery:

```json
"codex_accounts": {
  "<computed-email-hash>": ["<matching-codex-profile-id>"]
}
```

This is a field fragment, not a replacement for the whole configuration. Save as
UTF-8 without a BOM. Repeat for every login. Exactly one valid ID per email is
required; do not guess based on a custom label. Confirm the account through the
server dashboard's profile identity before mapping. Rerunning the installer
preserves mappings and merges email-label discoveries, so recheck ambiguity after
adding duplicate profiles. Hashes and IDs remain private even though they are not
authentication credentials.

## 4. Verify the recovered computer

```powershell
python -m unittest discover -s cyd-usage-monitor/scripts -p test_chat_account_switch.py
python -m unittest discover -s cyd-usage-monitor/server
Get-Content "$env:USERPROFILE/.cyd-usage-monitor/chat-switch-codex-last-result.json"
Get-Content "$env:USERPROFILE/.cyd-usage-monitor/antigravity-watcher-status.json"
```

Tests are offline regression checks; they do not prove app integration. Complete
these manual acceptance checks using harmless messages you send yourself:

1. Send in Codex under account A. Confirm a fresh `selected` result and matching
   dashboard **and physical CYD** account.
2. Switch the desktop login to B and send again; verify B. Repeat for every mapped
   login. A test under only the original login is insufficient.
3. Send in Antigravity; verify its configured primary profile. Then send in Codex
   while Antigravity continues responding: assistant updates must not reclaim it.
4. During a running Codex turn, select Antigravity with a user message, then send
   a steering message in Codex: it must select the current Codex account again.
5. Sign out of Windows and back in (or reboot). Verify watcher status `ready`
   with a current process, then repeat a new message in each app.

## Troubleshooting and maintenance

| Evidence | Next check |
| --- | --- |
| No fresh Codex result file | Hook path, Python path, trust approval, local desktop event delivery |
| `unmapped` | Exact login email hash, custom label, one enabled matching ID, ambiguity |
| `unavailable` | User URL/token, server reachability, configured executable/home, managed ChatGPT login |
| `ignored` | Enabled flag, desktop origin, event format, or stale/unrecognized Antigravity transcript |
| `duplicate` / `superseded` | Deduplication or a newer submission; send a fresh message to retest |
| `selected`, wrong/stale physical screen | Dashboard mapping, server command delivery and device connectivity |
| Antigravity status absent / `watch_failed` / `overflow` | Existing brain roots, Python startup path, process health; restart the verified watcher and send a new message |

Run `python cyd-usage-monitor/scripts/chat-account-switch.py --diagnose` for
recent history and heartbeat age. It prints up to 40 local and 40 server records.
The private SQLite journal keeps 1,000 records; the server keeps 200 accepted
selections/route reports. Repeated ignored/duplicate notifications are throttled.
No message text, emails, credentials, paths, or raw task/account IDs are logged.
Hashed `context_ref` values group submissions by task; hashed `account_ref`
values correlate helpers with server selections. `selected` means the API
confirmed; `unavailable` includes a fixed failure stage/category, with no raw
exception text. A timeout may still have reached the server: compare both logs.

Server sources distinguish `codex-hook`, `antigravity-watch`, `antigravity-hook`,
`stream-deck`, `dashboard`, `device-api` (untagged client), and `device-report`.
Source headers are allowlisted diagnostic claims by already-authenticated
clients, not a security identity. Device reports describe route changes, with
the account inferred by the server; they do not prove physical account rendering.
The Bearer-protected `/api/v1/selection-history` is private-listener-only.

Check `Get-ScheduledTask -TaskName 'CYD Antigravity Messages'` and
`Get-ScheduledTaskInfo -TaskName 'CYD Antigravity Messages'`. A running task
can report result 267009 (0x41301). A repeated trigger while already running
can report 2147946720 (0x800710E0) because IgnoreNew refused an overlapping
instance; check task state and the live heartbeat instead of that code alone.
Saved `ready` is insufficient:
check a recent heartbeat (normally under 120 seconds) and the PID's exact
command line. Restart with `Stop-ScheduledTask` then `Start-ScheduledTask` for
that task only. Do not terminate unrelated Python processes. Root changes
require a restart; mappings are read on subsequent events.

### MSIX startup and native-hook investigation

On 2026-09-06, `GetFinalPathNameByHandleW` proved Codex's packaged Windows app
redirected the old `%LOCALAPPDATA%\CYDUsageMonitor` directory into its private
package cache. Task Scheduler could not see the directory/script at that path;
the old native Antigravity command pointed there too. Helpers now live under
`%USERPROFILE%\.cyd-usage-monitor`, visible from ordinary Windows processes.
The installer migrates existing private mappings when the new location is empty.
Installation stops only matching current/legacy windowless watcher commands
after task registration succeeds. A manually launched console watcher must be
stopped separately after verifying its exact command line; the legacy mutex
uses a different config path and cannot prevent a second watcher at the new path.
Back up private mappings before migration. A live update may preserve the
already-trusted Codex command through a compatibility helper at the old location.

The installed Antigravity 2.12.2 engine contains native hooks and a
`json-hooks-enabled` feature flag. Its [official hook schema](https://antigravity.google/docs/hooks)
matches our global `PreInvocation` configuration. Correcting the inaccessible
command path is necessary; it does not establish that hook discovery is enabled.
Use the installer's optional `--probe-antigravity-hooks` to add
`cyd-native-hook-probe`, which logs only `hook_called` and never selects an account.
Keep the watcher active while checking a new real message. If no probe appears,
check again after the next normal full Antigravity restart. No probe calls were
observed in the current running app after the corrected-path test; the effective
feature-flag value and reload behavior are not established. Do not modify
undocumented provider settings to bypass feature gates. To remove the probe,
remove only `cyd-native-hook-probe` from the private global hooks JSON.

After a Python/Codex path change, rerun the installer with the correct paths,
review hook trust again, and repeat acceptance checks. After a server address or
token change, update the Windows User settings. After server profile recreation,
rediscover IDs and replace stale private mappings. Runtime SQLite and diagnostic
files are disposable and should not be migrated as setup inputs.

To disable selection, set `enabled` to `false` in the private configuration. For
uninstall, remove only this integration's handlers from Codex/Antigravity hooks,
stop and unregister only `CYD Antigravity Messages`, remove any legacy
`CYDAntigravityMessages` Run entry, and stop the verified watcher. Preserve unrelated hooks. Keep private mapping backups encrypted; on a
new machine use a fresh installation to regenerate absolute paths and startup,
then restore only verified mappings rather than copying old hooks blindly.

## Validation scope

This guide was checked against repository source and offline tests on 2026-09-06.
Earlier operator tests confirmed changed-login Codex and real Antigravity selection.
A clean-machine rebuild and the complete acceptance sequence above have not been
performed as part of this documentation audit. Future app versions may require
adapter changes; retain this checklist as the recovery acceptance gate.
