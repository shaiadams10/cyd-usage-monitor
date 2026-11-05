"""Official CLI wake-up adapters. No credentials or private provider APIs are read.

Claude is pinned to versions whose one-request failure behavior was
verified against a local synthetic HTTP server. Unsupported CLI versions fail
closed instead of silently inheriting different retry or agent-loop behavior.
"""
from __future__ import annotations

import datetime as dt
import functools
import json
import os
import re
import signal
import subprocess
import time
import threading
from pathlib import Path

try:
    from .wakeups import WakeupAdapter, WakeupError, PROMPT, validate_prompt
except ImportError:
    from wakeups import WakeupAdapter, WakeupError, PROMPT, validate_prompt

CLAUDE_MODEL = "claude-haiku-5-5"
CLAUDE_VERIFIED_VERSIONS = {"2.1.311", "2.1.316"}


def normalize_snapshot(profile: dict, snapshot: dict, now: float | None = None) -> dict:
    """Normalize only explicit, fresh CLI facts; 100% by itself is not idle."""
    provider = profile.get("provider")
    metrics = snapshot.get("metrics", {})
    if provider == "antigravity":
        model = str(profile.get("wakeup_model", "")).lower()
        group = "gemini" if model.startswith("gemini-") else "claude" if model.startswith(("claude-", "gpt-")) else None
        # The Antigravity CLI has separate Gemini and Claude/GPT pools.
        # Unknown models must never borrow a different pool's allowance.
        metrics = metrics.get(group, {}) if group else {}
    primary = metrics.get("five_hour", {})
    weekly = metrics.get("weekly", {})
    identity = snapshot.get("account_name", "")
    # Existing provider panels identify accounts by email. Never substitute a
    # user-defined label or the generic "Claude Code" provider heading.
    verified = isinstance(identity, str) and bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", identity))
    reset = primary.get("reset_at")
    state = primary.get("window_state", "unknown")
    if provider == "claude" and state == "idle":
        # The current complete /usage panel reports no active reset together
        # with numeric zero usage. Require independent confirmation and retain
        # the raw percentage so a rounded remaining100 cannot establish idle.
        if (primary.get("used_percentage") != 0 or primary.get("reset_reported") is not False
                or snapshot.get("capture", {}).get("confirmation_requests", 0) < 2):
            state = "unknown"
    text = str(primary.get("reset", "")).strip().casefold()
    if text in {"quota available", "no activity", "not started", "window not started"}:
        state = "idle"
    elif reset is not None:
        try:
            reset = float(reset)
            state = "active" if reset > (now or time.time()) else "idle"
        except (TypeError, ValueError):
            reset, state = None, "unknown"
    elif primary.get("remaining_pct", 100) < 100:
        state = "active"
    elif text:
        # A reset clock label with rounded full quota does not prove activity.
        # Some CLI panels display a prospective now+5h time before the first use.
        state = "unknown"
    if snapshot.get("status") != "ok" or snapshot.get("retrying") or snapshot.get("stale"):
        state = "unknown"
    windows = []
    for name, metric in (("five_hour", primary), ("weekly", weekly)):
        # A disabled 5h pool can be a consequence of weekly exhaustion, rather
        # than evidence that its own independent five-hour allowance was used.
        if name == "five_hour" and re.search(r"weekly limit|does not currently apply", str(metric.get("reset", "")), re.I):
            continue
        windows.append({"window": name, "remaining_pct": metric.get("remaining_pct"),
                        "reset_at": metric.get("reset_at"), "reset_text": metric.get("reset", "")})
    return {"account_identity": identity, "identity_verified": verified, "quota_windows": windows,
            "quota_collected_at": snapshot.get("collected_at"),
            "quota_valid": snapshot.get("status") == "ok" and not snapshot.get("retrying") and not snapshot.get("stale"),
            "collected_at": snapshot.get("collected_at"), "weekly_remaining_pct": weekly.get("remaining_pct"),
            "five_hour_remaining_pct": primary.get("remaining_pct"),
            "window_state": state, "window_reset_at": reset, "window_reset_text": primary.get("reset", "")}


def collect_preflight(collector, profile: dict) -> dict:
    with collector.profile_lock(profile["id"]):
        snapshot = collector.collect_profile(profile)
    return dict(normalize_snapshot(profile, snapshot), window_reset_timezone=getattr(collector, "ALERT_TIMEZONE_NAME", "UTC"))


def manual_identity_reading(collector, profile: dict, identity: str) -> dict:
    """Send now needs fresh identity, not an additional slow quota-screen read.

    Reuse quota facts only when the saved panel is healthy, fresh and belongs to
    this identity. A stale panel cannot establish a window or a reset time.
    """
    now = time.time()
    snapshot = {}
    try:
        candidate = collector.read_json(collector.STATE_FILE, {}).get("profiles", {}).get(profile["id"], {})
        stamp = candidate.get("collected_at")
        age = now - (float(stamp) if isinstance(stamp, (int, float)) else dt.datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).timestamp())
        if (0 <= age <= 120 and candidate.get("status") == "ok" and not candidate.get("stale") and not candidate.get("retrying")
                and candidate.get("account_name", "").strip().casefold() == identity.strip().casefold()):
            snapshot = candidate
    except (AttributeError, ValueError, TypeError, OSError):
        pass
    reading = normalize_snapshot(profile, dict(snapshot, account_name=identity))
    return dict(reading, collected_at=now, window_reset_timezone=getattr(collector, "ALERT_TIMEZONE_NAME", "UTC"))


@functools.lru_cache(maxsize=16)
def _claude_supported(executable: str, modified_ns: int) -> bool:
    try:
        result = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=5,
                                env={key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT") if key in os.environ})
        found = re.search(r"\b(\d+\.\d+\.\d+)\b", result.stdout)
        return result.returncode == 0 and bool(found) and found[1] in CLAUDE_VERIFIED_VERSIONS
    except (OSError, subprocess.TimeoutExpired):
        return False


def claude_command(executable: str, attempt_id: str, model: str = CLAUDE_MODEL, reasoning: str = "low", prompt: str = PROMPT) -> list[str]:
    command = [executable, "--print", validate_prompt(prompt), "--model", model, "--max-turns", "1", "--tools", "",
            "--safe-mode", "--setting-sources", "", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
            "--settings", json.dumps({"fallbackModel": [], "disableAllHooks": True, "availableModels": [model], "autoMemoryEnabled": False}),
            "--system-prompt", "Answer briefly.", "--output-format", "json", "--no-session-persistence",
            "--session-id", str(__import__("uuid").UUID(attempt_id))]
    if reasoning != "fixed":
        command.extend(["--effort", reasoning])
    return command


def claude_environment(base: dict[str, str], reasoning: str = "low") -> dict[str, str]:
    env = dict(base)
    # Whitelisted collector environments normally contain none of these;
    # discard inherited routing/model keys rather than permit paid API billing.
    for key in list(env):
        if key.startswith("ANTHROPIC_") or key in {"CLAUDE_CODE_OAUTH_TOKEN", "CLAUDECODE", "CLAUDE_CODE_SIMPLE"}:
            env.pop(key)
    env.update({"CLAUDE_CODE_MAX_RETRIES": "0", "CLAUDE_CODE_NONSTREAMING_TIMEOUT_RETRIES": "0",
                "CLAUDE_CODE_RETRY_WATCHDOG": "0", "CLAUDE_CODE_MAX_TURNS": "1",
                "CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK": "1",
                "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "CLAUDE_CODE_DISABLE_TERMINAL_TITLE": "1",
                "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",
                "CLAUDE_CODE_DISABLE_AGENT_VIEW": "1", "CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK": "1",
                "CLAUDE_CODE_ENABLE_CFC": "0", "CLAUDE_CODE_RESUME_INTERRUPTED_TURN": "0",
                "CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL": "1",
                "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "16",
                "CLAUDE_CODE_SAFE_MODE": "1", "CLAUDE_CODE_USE_HTTP2": "0", "DISABLE_AUTOUPDATER": "1"})
    if reasoning != "fixed":
        env["CLAUDE_CODE_EFFORT_LEVEL"] = reasoning
    else:
        env.pop("CLAUDE_CODE_EFFORT_LEVEL", None)
    return env


def run_once(command: list[str], env: dict[str, str], cwd: Path, timeout: float = 35, input_text: str | None = None) -> subprocess.CompletedProcess:
    """No retry. Terminate the entire CLI process group on a deadline."""
    process = subprocess.Popen(command, env=env, cwd=str(cwd), stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               start_new_session=os.name != "nt")
    try:
        stdout, stderr = process.communicate(input=input_text, timeout=timeout)
    except BaseException:
        if os.name != "nt":
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        else:
            process.kill()
        process.communicate()
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def build_claude_adapter(collector, model: str = CLAUDE_MODEL, reasoning: str = "low", catalogue: list[dict] | None = None) -> WakeupAdapter:
    try:
        from .wakeup_catalog import provider_models, require_model
    except ImportError:
        from wakeup_catalog import provider_models, require_model
    if catalogue is None:
        catalogue = provider_models(collector, "claude")
    executable = collector.cli_executable("claude")
    supported = False
    if executable:
        try:
            supported = _claude_supported(executable, Path(executable).stat().st_mtime_ns)
        except OSError:
            pass

    def send(profile, prompt, attempt_id):
        prompt = validate_prompt(prompt)
        if profile.get("wakeup_model", model) != model or profile.get("wakeup_reasoning", reasoning) != reasoning:
            raise WakeupError("The selected model changed. Sending was stopped.")
        with collector.profile_lock(profile["id"]):
            env = claude_environment(collector.profile_environment(profile), reasoning)
            workdir = collector.profile_workdir(profile)
            identity = collector.claude_account_status(executable, env, workdir)
            if identity.get("account_name", "").strip().casefold() != profile.get("wakeup_account_identity", "").strip().casefold():
                raise WakeupError("Account changed after the usage check. Sending was stopped.")
            result = run_once(claude_command(executable, attempt_id, model, reasoning, prompt), env, workdir)
        try:
            body = json.loads(result.stdout)
        except (ValueError, TypeError):
            return {"state": "unknown", "reason": safe_cli_reason("Claude", result.stdout + result.stderr, "The CLI returned an unreadable outcome.")}
        # Never treat an early CLI exit, model switch, or agent continuation as
        # a successful one-prompt outcome. Such results pause the account.
        model_usage = body.get("modelUsage", {})
        valid_models = not model_usage or all(key == model for key in model_usage)
        success = result.returncode == 0 and body.get("is_error") is False and body.get("num_turns") == 1 and valid_models
        return {"state": "sent" if success else "failed" if body.get("is_error") is True else "unknown",
                **({"reason": safe_cli_reason("Claude", result.stdout + result.stderr, "The CLI did not complete the selected model request.")} if not success else {})}

    def preflight(profile):
        require_model(collector, profile, model, reasoning)
        if profile.get("wakeup_source") == "manual":
            with collector.profile_lock(profile["id"]):
                identity = collector.claude_account_status(executable, collector.profile_environment(profile), collector.profile_workdir(profile))
            return manual_identity_reading(collector, profile, identity.get("account_name", ""))
        return collect_preflight(collector, profile)

    def select(model_id, effort):
        if not any(choice["id"] == model_id and effort in choice["reasoning_levels"] for choice in catalogue):
            raise WakeupError("Choose an available Claude model and reasoning level.")
        return build_claude_adapter(collector, model_id, effort, catalogue)

    return WakeupAdapter(model, reasoning, send, preflight, supported,
                         "Claude wake-ups require verified official CLI version 2.1.311 or 2.1.316; collection still works.",
                         catalogue=catalogue, select=select, postflight=lambda profile: collect_preflight(collector, profile))


def build_adapters(collector) -> dict[str, WakeupAdapter]:
    adapters = {
        "claude": build_claude_adapter(collector),
        "antigravity": build_antigravity_adapter(collector),
    }
    try:
        try: from .wakeup_codex import build_adapter
        except ImportError: from wakeup_codex import build_adapter
        adapters["codex"] = build_adapter(collector)
    except ImportError:
        adapters["codex"] = WakeupAdapter("gpt-5.6-luna", "low", unavailable_reason="Codex single-request safety is being verified. Sending is unavailable.")
    return adapters


def safe_cli_reason(provider: str, output: str, fallback: str) -> str:
    """Classify useful failures without leaking CLI output, URLs or account data."""
    checks = [(r"unknown model|model.{0,40}(?:not found|unavailable|not available|unsupported)", "The selected model is unavailable for this account."),
              (r"invalid.{0,20}(?:effort|reasoning)|unsupported.{0,20}(?:effort|reasoning)", "The selected reasoning level is unsupported."),
              (r"rate.?limit|quota|usage limit|exhausted|429", "The provider rejected the request because of a usage or rate limit."),
              (r"unauthorized|unauthenticated|not logged|sign.?in|401|403", "The provider rejected authentication or account access."),
              (r"timeout|timed out|deadline", "The CLI timed out before confirming completion."),
              (r"network|TLS|certificate|connection|502|503|504|529", "The CLI reported a network or provider availability failure.")]
    for pattern, message in checks:
        if re.search(pattern, output, re.I): return provider + ": " + message + " No prompt was resubmitted."
    return provider + ": " + fallback + " No prompt was resubmitted."


def antigravity_command(executable: str, model: str, reasoning: str, prompt: str = PROMPT) -> list[str]:
    command = [executable, "--print", validate_prompt(prompt), "--model", model, "--agent", "cyd-wakeup",
               "--output-format", "stream-json", "--disable-slash-commands", "--print-timeout", "25s"]
    if reasoning != "fixed": command.extend(["--effort", reasoning])
    return command


def antigravity_agent(workdir: Path, home: Path | None = None) -> None:
    # Global customizations are still inside this isolated monitor profile.
    # AGY 1.4 does not discover a fresh nested workspace before project setup.
    directory = home / ".gemini" / "config" / "agents" if home else workdir / ".agents" / "agents"
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    definition = directory / "cyd-wakeup.md"
    definition.write_text('---\nname: cyd-wakeup\ndescription: Minimal one-prompt account wake-up\nmainAgent: true\nsubagent: false\nhidden: false\ninheritMcp: false\ntools: []\ncommandExecutionPolicy: "off"\n---\n# System Prompt\nAnswer briefly. Do not use tools, delegate, plan, retry, or continue after answering.\n', encoding="utf-8")
    definition.chmod(0o600)


def build_antigravity_adapter(collector, model: str = "", reasoning: str = "", catalogue: list[dict] | None = None) -> WakeupAdapter:
    try:
        from .wakeup_catalog import provider_models, require_model
    except ImportError:
        from wakeup_catalog import provider_models, require_model
    executable = collector.cli_executable("antigravity")
    if catalogue is None: catalogue = provider_models(collector, "antigravity") if executable else []
    def preflight(profile):
        require_model(collector, profile, model, reasoning)
        return collect_preflight(collector, profile)
    def send(profile, prompt, attempt_id):
        prompt = validate_prompt(prompt)
        if profile.get("wakeup_model", model) != model or profile.get("wakeup_reasoning", reasoning) != reasoning:
            raise WakeupError("The selected model changed. Sending was stopped.")
        with collector.profile_lock(profile["id"]):
            identity = collector.collect_profile(profile).get("account_name", "")
            if identity.strip().casefold() != profile.get("wakeup_account_identity", "").strip().casefold():
                raise WakeupError("Account changed after the usage check. Sending was stopped.")
            workdir = collector.profile_workdir(profile) / "wakeups" / attempt_id
            workdir.mkdir(parents=True, mode=0o700, exist_ok=False)
            env = collector.profile_environment(profile)
            antigravity_agent(workdir, Path(env["HOME"]))
            result = run_guarded_once(antigravity_command(executable, model, reasoning, prompt), env, workdir, timeout=27)
        events = []
        for line in result.stdout.splitlines():
            try: events.append(json.loads(line))
            except ValueError: pass
        final = next((event for event in reversed(events) if isinstance(event, dict) and (event.get("type") == "result" or event.get("event") == "result")), {})
        if isinstance(final.get("result"), dict): final = final["result"]
        status = str(final.get("status", "")).upper()
        if result.returncode == 0 and status in {"SUCCESS", "COMPLETED"}: return {"state": "sent"}
        output = result.stdout + "\n" + result.stderr
        return {"state": "failed" if status in {"ERROR", "FAILED", "CANCELED", "CANCELLED"} else "unknown",
                "reason": safe_cli_reason("Antigravity", output, "The CLI did not confirm completion.")}
    def select(model_id, effort):
        if not any(choice["id"] == model_id and effort in choice["reasoning_levels"] for choice in catalogue):
            raise WakeupError("Choose an available Antigravity model and reasoning level.")
        return build_antigravity_adapter(collector, model_id, effort, catalogue)
    return WakeupAdapter(model, reasoning, send, preflight, bool(executable),
                         "Antigravity CLI is not installed on the collector host.", catalogue=catalogue, select=select, postflight=preflight,
                         execution_note="One prompt; stops on reported retry/tool activity or after 27 seconds. This CLI has no configurable native retry count.")


def run_guarded_once(command: list[str], env: dict[str, str], cwd: Path, timeout: float = 27) -> subprocess.CompletedProcess:
    """Submit once; stop on observed errors/retry/tool activity and on a hard deadline.

    Antigravity exposes no documented native retry count. This output guard stops
    observed retry/failure activity; it cannot promise to intercept an unreported
    transport retry. The deadline bounds even an unreported internal loop.
    """
    process = subprocess.Popen(command, env=env, cwd=str(cwd), stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               start_new_session=os.name != "nt")
    captured = [[], []]
    stop = threading.Event()
    def reader(stream, index):
        for line in iter(stream.readline, ""):
            captured[index].append(line)
            try: event = json.loads(line)
            except ValueError: event = {}
            kind = str(event.get("type") or event.get("event") or "") if isinstance(event, dict) else ""
            item = event.get("item", {}) if isinstance(event, dict) else {}
            nested_tool = kind in {"item.started", "item.completed"} and item.get("type") in {"command_execution", "mcp_tool_call", "web_search", "file_change", "function_call"}
            if (nested_tool or kind in {"error", "tool_call", "tool_use", "tool_start", "tool_execution_start", "tool_execution"}
                    or re.search(r"retrying|retry attempt|retry in \d|backoff|AGY_ERROR", line, re.I)):
                stop.set()
    workers = [threading.Thread(target=reader, args=(stream, index), daemon=True)
               for index, stream in enumerate((process.stdout, process.stderr))]
    for worker in workers: worker.start()
    deadline = time.monotonic() + timeout
    try:
        while process.poll() is None and not stop.wait(0.02):
            if time.monotonic() >= deadline: stop.set()
        if process.poll() is None:
            if os.name != "nt":
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            else: process.kill()
        process.wait(timeout=3)
    finally:
        if process.poll() is None: process.kill()
        for worker in workers: worker.join(timeout=2)
        for stream in (process.stdout, process.stderr): stream.close()
    return subprocess.CompletedProcess(command, process.returncode, "".join(captured[0]), "".join(captured[1]))
