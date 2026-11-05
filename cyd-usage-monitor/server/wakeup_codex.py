"""One submitted Codex prompt with explicit model selection and no app retries."""
from __future__ import annotations
import json
import queue
import re
import subprocess
import threading
import time
from pathlib import Path
try:
    from .wakeups import WakeupAdapter, WakeupError, PROMPT, validate_prompt
    from .wakeup_catalog import provider_models, require_model
except ImportError:
    from wakeups import WakeupAdapter, WakeupError, PROMPT, validate_prompt
    from wakeup_catalog import provider_models, require_model

MODEL = ""
REASONING = ""


def account_identity(executable: str, env: dict, workdir: Path, timeout: float = 5) -> str:
    """Documented local account/read only; never create a thread or a turn."""
    process = subprocess.Popen([executable, "app-server", "-c", "check_for_update_on_startup=false"], env=env, cwd=str(workdir),
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    messages = queue.Queue(maxsize=64)
    deadline = time.monotonic() + timeout

    def read():
        try:
            for line in process.stdout:
                if len(line) > 128 * 1024:
                    break
                messages.put_nowait(json.loads(line))
        except (ValueError, OSError, queue.Full):
            pass
        finally:
            try: messages.put_nowait(None)
            except queue.Full: pass

    worker = threading.Thread(target=read, daemon=True)
    worker.start()

    def send(message):
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()

    def receive(identifier):
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise WakeupError("The account identity check timed out. No prompt was sent.")
            try: message = messages.get(timeout=remaining)
            except queue.Empty: raise WakeupError("The account identity check timed out. No prompt was sent.") from None
            if not isinstance(message, dict):
                raise WakeupError("The account identity check failed. Reconnect this account.")
            if message.get("id") == identifier:
                if "error" in message or not isinstance(message.get("result"), dict):
                    raise WakeupError("The account identity check failed. Reconnect this account.")
                return message["result"]
    try:
        send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "cyd_wakeup_identity", "version": "1.0"}}})
        receive(1)
        send({"method": "initialized"})
        send({"id": 2, "method": "account/read", "params": {"refreshToken": False}})
        account = receive(2).get("account") or {}
        identity = account.get("email", "")
        if account.get("type") != "chatgpt" or not isinstance(identity, str) or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", identity):
            raise WakeupError("The account identity could not be verified. Reconnect this account.")
        return identity
    finally:
        if process.poll() is None: process.terminate()
        try: process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=1)
        worker.join(timeout=0.2)
        process.stdin.close()
        process.stdout.close()

def codex_command(executable: str, model: str, reasoning: str, instructions: Path, prompt: str = PROMPT) -> list[str]:
    settings = {
        "model_provider": "cyd-wakeup", "model_providers.cyd-wakeup.name": "OpenAI",
        "model_providers.cyd-wakeup.requires_openai_auth": True,
        "model_providers.cyd-wakeup.wire_api": "responses",
        "model_providers.cyd-wakeup.request_max_retries": 0,
        "model_providers.cyd-wakeup.stream_max_retries": 0,
        "model_providers.cyd-wakeup.supports_websockets": False,
        "model_providers.cyd-wakeup.stream_idle_timeout_ms": 15000,
        "model_instructions_file": str(instructions), "project_doc_max_bytes": 0,
        "model_reasoning_summary": "none", "web_search": "disabled",
        "check_for_update_on_startup": False, "personality": "none",
        "features.shell_tool": False, "features.view_image": False,
        "features.apps": False, "features.multi_agent": False,
        "features.hooks": False, "features.plugins": False,
        "features.memories": False, "features.goals": False,
        "features.shell_snapshot": False, "tools.update_plan.enabled": False,
    }
    if reasoning != "fixed": settings["model_reasoning_effort"] = reasoning
    command = [executable, "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
               "--skip-git-repo-check", "--json", "--sandbox", "read-only", "--model", model]
    for key, value in settings.items(): command.extend(["-c", key + "=" + json.dumps(value)])
    # End CLI parsing so a message such as "resume" stays a prompt.
    command.extend(["--", validate_prompt(prompt)])
    return command

def build_adapter(collector, model: str = MODEL, reasoning: str = REASONING, catalogue: list[dict] | None = None) -> WakeupAdapter:
    try:
        from .wakeup_cli import run_guarded_once, collect_preflight, safe_cli_reason, manual_identity_reading
    except ImportError:
        from wakeup_cli import run_guarded_once, collect_preflight, safe_cli_reason, manual_identity_reading
    executable = getattr(collector, "wakeup_cli_executable", collector.cli_executable)("codex")
    if catalogue is None: catalogue = provider_models(collector, "codex") if executable else []
    def preflight(profile):
        require_model(collector, profile, model, reasoning)
        if profile.get("wakeup_source") == "manual":
            with collector.profile_lock(profile["id"]):
                identity = account_identity(executable, collector.profile_environment(profile), collector.profile_workdir(profile))
            return manual_identity_reading(collector, profile, identity)
        return collect_preflight(collector, profile)
    def send(profile, prompt, attempt_id):
        prompt = validate_prompt(prompt)
        if profile.get("wakeup_model", model) != model or profile.get("wakeup_reasoning", reasoning) != reasoning:
            raise WakeupError("The selected model changed. Sending was stopped.")
        with collector.profile_lock(profile["id"]):
            identity = account_identity(executable, collector.profile_environment(profile), collector.profile_workdir(profile))
            if identity.strip().casefold() != profile.get("wakeup_account_identity", "").strip().casefold():
                raise WakeupError("Account changed after the usage check. Sending was stopped.")
            env = collector.profile_environment(profile)
            workdir = collector.profile_workdir(profile) / "wakeups" / attempt_id
            workdir.mkdir(parents=True, mode=0o700, exist_ok=False)
            instructions = workdir / "instructions.md"
            instructions.write_text("Reply briefly. Do not use tools or delegate tasks.", encoding="utf-8")
            result = run_guarded_once(codex_command(executable, model, reasoning, instructions, prompt), env, workdir, timeout=27)
        try: events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        except (ValueError, TypeError): return {"state": "unknown", "reason": "Codex returned an unreadable outcome. No prompt was resubmitted."}
        if result.returncode == 0 and any(item.get("type") == "turn.completed" for item in events): return {"state": "sent"}
        if any(item.get("type") in {"turn.failed", "error"} for item in events):
            return {"state": "failed", "reason": safe_cli_reason("Codex", result.stdout + result.stderr, "The CLI reported a failure for the selected model.")}
        return {"state": "unknown", "reason": "Codex did not confirm completion. No prompt was resubmitted."}
    def select(model_id, effort):
        if not any(choice["id"] == model_id and effort in choice["reasoning_levels"] for choice in catalogue):
            raise WakeupError("Choose an available Codex model and reasoning level.")
        return build_adapter(collector, model_id, effort, catalogue)
    return WakeupAdapter(model, reasoning, send, preflight, bool(executable),
                         "Codex CLI is not installed on the collector host.", catalogue=catalogue, select=select, postflight=lambda profile: collect_preflight(collector, profile),
                         execution_note="One prompt; HTTP and stream retries disabled, with a 27-second execution limit and tool-activity stop.")
