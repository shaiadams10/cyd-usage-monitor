"""Read model choices through official CLI commands, never inference or credentials."""
from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from pathlib import Path

CACHE_SECONDS = 300
_cache = {}
_lock = threading.Lock()
LEVELS = {"none", "minimal", "low", "medium", "high", "xhigh", "max", "fixed"}


def parse_models(provider: str, output: str) -> list[dict]:
    models = []
    if provider == "antigravity":
        for line in output.splitlines():
            if "\t" not in line:
                continue
            identifier, label = line.split("\t", 1)
            effort = re.search(r"-(low|medium|high|xhigh|max)$", identifier)
            models.append({"id": identifier, "label": label, "reasoning_levels": [effort[1] if effort else "fixed"]})
    else:
        payload = json.loads(output)
        if provider == "claude":
            response = payload.get("response", {}).get("response", payload)
            for item in response.get("models", []):
                identifier = item.get("resolvedModel") or item.get("value")
                if identifier == "default":
                    continue
                levels = item.get("supportedEffortLevels") or ["fixed"]
                models.append({"id": identifier, "label": item.get("displayName", identifier), "reasoning_levels": levels})
        elif provider == "codex":
            for item in payload.get("models", []):
                # API-key eligibility is distinct from availability in Codex.
                if item.get("visibility") == "hide":
                    continue
                levels = [level.get("effort") for level in item.get("supported_reasoning_levels", [])]
                models.append({"id": item.get("slug"), "label": item.get("display_name") or item.get("slug"), "reasoning_levels": levels or ["fixed"]})
    result = {}
    for item in models:
        if (not isinstance(item.get("id"), str) or not re.fullmatch(r"[a-zA-Z0-9._:/-]{1,120}", item["id"])
                or not isinstance(item.get("label"), str)):
            continue
        levels = [level for level in item["reasoning_levels"] if level in LEVELS]
        if levels and item["id"] not in result:
            result[item["id"]] = dict(item, label=item["label"][:120], reasoning_levels=list(dict.fromkeys(levels)))
    return list(result.values())


def profile_models(collector, profile: dict, *, force: bool = False) -> list[dict]:
    provider = profile["provider"]
    executable = getattr(collector, "wakeup_cli_executable", collector.cli_executable)(provider)
    if not executable:
        return []
    try:
        modified = Path(executable).stat().st_mtime_ns
    except OSError:
        modified = None
    key = (executable, modified, profile["id"])
    now = time.monotonic()
    with _lock:
        saved = _cache.get(key)
        if saved and not force and now - saved[0] < CACHE_SECONDS:
            return saved[1]
    try:
        try:
            from .wakeup_cli import run_once
        except ImportError:
            from wakeup_cli import run_once
        with collector.profile_lock(profile["id"]):
            env, workdir = collector.profile_environment(profile), collector.profile_workdir(profile)
            if provider == "claude":
                request = json.dumps({"type": "control_request", "request_id": "cyd-model-list", "request": {"subtype": "initialize"}}) + "\n"
                command = [executable, "--print", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose", "--safe-mode"]
                process = run_once(command, env, workdir, timeout=18, input_text=request)
                responses = []
                for line in process.stdout.splitlines():
                    try: responses.append(json.loads(line))
                    except ValueError: continue
                output = json.dumps(next(item for item in responses if item.get("type") == "control_response"))
            else:
                command = [executable, "debug", "models"] if provider == "codex" else [executable, "models"]
                process = run_once(command, env, workdir, timeout=18)
                output = process.stdout
            result = parse_models(provider, output) if process.returncode == 0 else []
            if provider == "antigravity":
                for item in result:
                    effort = run_once([executable, "-p", "/effort", "--model", item["id"], "--output-format", "json"], env, workdir, timeout=12)
                    try:
                        data = json.loads(effort.stdout).get("command", {}).get("data", {})
                        levels = data.get("available") if data.get("adjustable") is True else ["fixed"]
                        verified = [level for level in (levels or []) if level in LEVELS]
                        if effort.returncode == 0 and verified: item["reasoning_levels"] = verified
                    except (ValueError, TypeError):
                        pass
    except (OSError, ValueError, StopIteration, subprocess.SubprocessError):
        result = []
    with _lock:
        _cache[key] = (now, result)
    return result


def provider_models(collector, provider: str) -> list[dict]:
    config = collector.read_json(collector.PROFILES_FILE, {"profiles": []})
    profiles = [profile for profile in config.get("profiles", []) if profile.get("provider") == provider and profile.get("enabled", True)]
    combined = {}
    for profile in profiles:
        for model in profile_models(collector, profile):
            if model["id"] not in combined:
                combined[model["id"]] = dict(model, reasoning_levels=list(model["reasoning_levels"]))
            else:
                combined[model["id"]]["reasoning_levels"] = list(dict.fromkeys(combined[model["id"]]["reasoning_levels"] + model["reasoning_levels"]))
    return list(combined.values())


def require_model(collector, profile: dict, model: str, reasoning: str) -> None:
    for choice in profile_models(collector, profile):
        if choice["id"] == model and reasoning in choice["reasoning_levels"]:
            return
    try:
        from .wakeups import WakeupError
    except ImportError:
        from wakeups import WakeupError
    raise WakeupError("The selected model or reasoning is unavailable for this account. Refresh the model list.")
