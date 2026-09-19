#!/usr/bin/env python3
"""Host-side provider collector for the CYD usage monitor.

Run this on the same host that owns the authenticated `codex` and `agy`
profiles. It also reads OpenRouter's documented management API using a
dashboard-managed key. It writes only normalized snapshots to shared storage.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import select
import shutil
import smtplib
import ssl
import subprocess
import struct
import threading
import time
import uuid
from email.message import EmailMessage
from pathlib import Path
from typing import Callable
from urllib import error as urlerror
from urllib import request as urlrequest
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    from .storage import data_lock, read_json, read_json_unlocked, update_json, write_json, write_json_unlocked
except ImportError:  # Docker runs this file as a top-level script.
    from storage import data_lock, read_json, read_json_unlocked, update_json, write_json, write_json_unlocked

try:
    import pty
except ModuleNotFoundError:  # Parser tests also run on the Windows firmware workstation.
    pty = None

try:
    import fcntl
    import termios
except ModuleNotFoundError:  # Only needed when a Unix PTY is available.
    fcntl = termios = None


DATA_DIR = Path(os.environ.get("CYD_MONITOR_DATA_DIR", "/app/data"))
PROFILES_FILE = DATA_DIR / "cli-profiles.json"
CONTROL_FILE = DATA_DIR / "collector-control.json"
RUNTIME_FILE = DATA_DIR / "collector-runtime.json"
STATE_FILE = DATA_DIR / "telemetry.json"
OPENROUTER_SECRET_FILE = DATA_DIR / "openrouter-secret.json"
OPENROUTER_STATE_FILE = DATA_DIR / "openrouter-telemetry.json"
ALERTS_FILE = DATA_DIR / "alert-status.json"
EMAIL_SECRET_FILE = DATA_DIR / "email-secret.json"
INCIDENTS_FILE = DATA_DIR / "collector-incidents.json"
SETTINGS_FILE = DATA_DIR / "monitor-settings.json"
LOGIN_INPUT_DIR = DATA_DIR / ".login-inputs"
DEBUG_EVIDENCE_DIR = DATA_DIR / ".collector-debug"
PROFILE_ROOT = Path(os.environ.get("CYD_MONITOR_PROFILE_ROOT", "/profiles"))
# Profiles are fully isolated (own HOME, CODEX_HOME, and workspace), so they
# collect in parallel. Each profile still serializes its own CLI runs.
_PROFILE_LOCKS: dict[str, threading.Lock] = {}
_PROFILE_LOCKS_GUARD = threading.Lock()
OPENROUTER_API_ROOT = "https://openrouter.ai/api/v1"
OPENROUTER_MAX_BYTES = 256 * 1024
OPENROUTER_TIMEOUT_SECONDS = 15


class OpenRouterError(RuntimeError):
    """A credential-safe OpenRouter collection failure."""


def bounded_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as error:
        raise RuntimeError(f"{name} must be an integer") from error
    if not minimum <= value <= maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return value


POLL_SECONDS = bounded_int_env("CYD_MONITOR_POLL_SECONDS", 90, 30, 86400)
# The account currently selected for the CYD is refreshed on a faster cadence;
# every other profile keeps the background interval above.
ACTIVE_POLL_SECONDS = bounded_int_env("CYD_MONITOR_ACTIVE_POLL_SECONDS", 30, 10, 86400)
MAX_PARALLEL_COLLECTIONS = bounded_int_env("CYD_MONITOR_MAX_PARALLEL_COLLECTIONS", 3, 1, 16)
ALERT_FAILURE_THRESHOLD = bounded_int_env("CYD_MONITOR_ALERT_FAILURE_THRESHOLD", 3, 1, 10)
# Longest single CLI capture (the Codex timeout below). A snapshot is stale once
# two refresh intervals plus one full capture have passed without a new result.
COLLECTION_TIMEOUT_BUDGET = 60


def profile_lock(profile_id: str) -> threading.Lock:
    with _PROFILE_LOCKS_GUARD:
        return _PROFILE_LOCKS.setdefault(profile_id, threading.Lock())


def stale_after_seconds(interval_seconds: int) -> int:
    return int(interval_seconds) * 2 + COLLECTION_TIMEOUT_BUDGET
INCIDENT_HISTORY_LIMIT = 50
ALERT_TIMEZONE_NAME = os.environ.get("CYD_MONITOR_TIMEZONE", "UTC").strip() or "UTC"
try:
    ALERT_TIMEZONE = ZoneInfo(ALERT_TIMEZONE_NAME)
except ZoneInfoNotFoundError as error:
    raise RuntimeError(f"Unknown CYD_MONITOR_TIMEZONE: {ALERT_TIMEZONE_NAME}") from error


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def utc_after(seconds: float) -> str:
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def _money(value, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OpenRouterError(f"OpenRouter response omitted numeric {field}")
    return round(max(0.0, float(value)), 6)


def openrouter_json(path: str, key: str) -> dict:
    request = urlrequest.Request(
        OPENROUTER_API_ROOT + path,
        headers={"Authorization": "Bearer " + key, "Accept": "application/json"},
    )
    try:
        with urlrequest.urlopen(request, timeout=OPENROUTER_TIMEOUT_SECONDS) as response:
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > OPENROUTER_MAX_BYTES:
                raise OpenRouterError("OpenRouter response exceeded the safe size limit")
            raw = response.read(OPENROUTER_MAX_BYTES + 1)
    except urlerror.HTTPError as error:
        messages = {
            401: "OpenRouter rejected the management key",
            403: "OpenRouter management permissions are required",
            429: "OpenRouter rate limit reached; collection will retry",
        }
        raise OpenRouterError(messages.get(error.code, f"OpenRouter returned HTTP {error.code}")) from None
    except (urlerror.URLError, TimeoutError, OSError, ValueError):
        raise OpenRouterError("OpenRouter could not be reached") from None
    if len(raw) > OPENROUTER_MAX_BYTES:
        raise OpenRouterError("OpenRouter response exceeded the safe size limit")
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise OpenRouterError("OpenRouter returned invalid JSON") from None
    if not isinstance(payload, dict):
        raise OpenRouterError("OpenRouter returned an unexpected response")
    return payload


def normalize_openrouter(credits_payload: dict, keys: list[dict], activity_payload: dict, label: str, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    credits = credits_payload.get("data")
    activity = activity_payload.get("data")
    if not isinstance(credits, dict) or not isinstance(activity, list):
        raise OpenRouterError("OpenRouter response omitted required data")
    total_credits = _money(credits.get("total_credits"), "total credits")
    total_usage = _money(credits.get("total_usage"), "total usage")
    remaining = round(max(0.0, total_credits - total_usage), 6)
    remaining_pct = round(min(100.0, remaining * 100.0 / total_credits), 1) if total_credits else 0.0

    aggregates = {"usage_today": 0.0, "usage_week": 0.0, "usage_month": 0.0}
    key_fields = {"usage_today": "usage_daily", "usage_week": "usage_weekly", "usage_month": "usage_monthly"}
    for item in keys:
        if not isinstance(item, dict):
            raise OpenRouterError("OpenRouter returned invalid API key data")
        for target, source in key_fields.items():
            aggregates[target] += _money(item.get(source, 0), source)

    completed = [(now.date() - dt.timedelta(days=offset)).isoformat() for offset in range(7, 0, -1)]
    by_date = {day: 0.0 for day in completed}
    by_model: dict[str, float] = {}
    for item in activity:
        if not isinstance(item, dict):
            raise OpenRouterError("OpenRouter returned invalid activity data")
        date = item.get("date")
        if date not in by_date:
            continue
        usage = _money(item.get("usage", 0), "activity usage")
        by_date[date] += usage
        model = str(item.get("model") or "Unknown model")[:80]
        by_model[model] = by_model.get(model, 0.0) + usage
    top_name, top_usage = max(by_model.items(), key=lambda pair: pair[1], default=("No completed usage", 0.0))
    return {
        "provider": "openrouter", "status": "ok", "account_label": label or "OpenRouter",
        "total_credits": total_credits, "total_usage": total_usage,
        "remaining_credits": remaining, "remaining_pct": remaining_pct,
        **{name: round(value, 6) for name, value in aggregates.items()},
        "daily_usage": [{"date": day, "usage": round(by_date[day], 6)} for day in completed],
        "top_model": {"name": top_name, "usage": round(top_usage, 6)},
        "collected_at": now.isoformat().replace("+00:00", "Z"), "source": "OpenRouter API",
    }


def collect_openrouter() -> dict | None:
    config = read_json(OPENROUTER_SECRET_FILE, {})
    key = config.get("key") if isinstance(config, dict) else None
    if not isinstance(key, str) or not key:
        return None
    try:
        credits = openrouter_json("/credits", key)
        keys: list[dict] = []
        offset = 0
        while True:
            page = openrouter_json(f"/keys?include_disabled=true&offset={offset}", key).get("data")
            if not isinstance(page, list):
                raise OpenRouterError("OpenRouter response omitted API key data")
            keys.extend(page)
            if len(page) < 100:
                break
            offset += len(page)
            if offset >= 10000:
                raise OpenRouterError("OpenRouter API key list exceeded the safe limit")
        snapshot = normalize_openrouter(credits, keys, openrouter_json("/activity", key), str(config.get("label", "OpenRouter")))
    except OpenRouterError as error:
        snapshot = {
            "provider": "openrouter", "status": "error", "account_label": str(config.get("label", "OpenRouter"))[:80],
            "error": str(error), "collected_at": utcnow(), "source": "OpenRouter API",
        }
    write_json(OPENROUTER_STATE_FILE, snapshot)
    return snapshot


def strip_terminal(text: str) -> str:
    return re.sub(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))", "", text).replace("\r", "")


def clean_terminal_transcript(text: str) -> str:
    """Keep human-readable CLI output while removing TUI repaint noise."""
    text = strip_terminal(text).replace("\x00", "").replace("\x08", "")
    # Antigravity's spinner is emitted as a long run of frames without a
    # terminal redraw in PTY capture. It does not communicate useful state.
    text = re.sub(r"(?:\s*[⣯⣟⡿⢿⣻⣽⣾⣷]){6,}", " [working] ", text)
    return text[-16000:]

def percentage(value: str) -> int:
    return max(0, min(100, int(round(float(value)))))


def extract_login_url(output: str) -> str:
    """Reassemble URLs that a narrow terminal wraps across multiple lines."""
    match = re.search(r"https?://.*?(?=\n\s*\n|\n\s*(?:If |authorization code)|\Z)", output, re.I | re.S)
    return re.sub(r"\s+", "", match.group(0)) if match else ""


def parse_codex_status(raw: str) -> dict:
    text = strip_terminal(raw)
    # Linux PTYs preserve the box-drawing border used by Codex's status card;
    # normalize it so the same parser also handles plain and legacy captures.
    text = text.replace("│", "|")
    account = re.search(r"^\s*(?:[│|]\s*)?Account:\s*(.+?)\s*\(([^)]*)\)\s*(?:[│|])?\s*$", text, re.MULTILINE)
    limits = list(re.finditer(
        r"(?P<label>5h|Five Hour|Monthly|Weekly) limit:\s*(?:\[[^\n]*\]\s*)?"
        r"(?P<pct>\d+(?:\.\d+)?)%\s+left\s*\(resets\s+(?P<reset>[^)]*)\)",
        text, re.I,
    ))
    credits = re.search(r"^\s*(?:[│|]\s*)?Credits:\s*(.+?)\s*(?:[│|])?\s*$", text, re.MULTILINE | re.I)
    if not account or not limits:
        raise ValueError("Codex /status did not contain account and a 5-hour, weekly, or monthly limit field")
    metrics = {}
    labels = {}
    for limit in limits:
        normalized = limit.group("label").lower()
        key = "five_hour" if normalized in {"5h", "five hour"} else normalized
        metrics[key] = {
            "remaining_pct": percentage(limit.group("pct")),
            "reset": limit.group("reset").strip(),
        }
        labels[key] = "5-Hour Limit" if key == "five_hour" else key.title() + " Limit"
    primary_key = next((key for key in ("five_hour", "weekly", "monthly") if key in metrics), None)
    metrics["primary"] = metrics[primary_key]
    return {
        "provider": "codex",
        "account_name": account.group(1).strip(),
        "plan_type": account.group(2).strip() or "ChatGPT",
        "metrics": metrics,
        "limit_label": labels[primary_key],
        "credits": credits.group(1).strip() if credits else "None",
    }


def account_name_from_transcript(provider: str, raw: str) -> str:
    """Extract only the CLI-visible account identity from a partial panel."""
    text = strip_terminal(raw).replace("│", "|")
    if provider == "codex":
        match = re.search(r"^\s*(?:[|]\s*)?Account:\s*(.+?)\s*\([^)]*\)\s*(?:[|])?\s*$", text, re.MULTILINE)
    else:
        match = re.search(r"^\s*Account:\s*(.+?)\s*$", text, re.MULTILINE | re.I)
    return match.group(1).strip()[:160] if match else ""


def parse_antigravity_usage(raw: str) -> dict:
    text = strip_terminal(raw)
    account = re.search(r"^\s*Account:\s*(.+?)\s*$", text, re.MULTILINE | re.I)
    if not account:
        raise ValueError("Antigravity /usage did not contain an account field")

    groups = {
        "gemini": r"GEMINI MODELS(?P<body>.*?)(?=CLAUDE AND GPT MODELS|\Z)",
        "claude": r"CLAUDE AND GPT MODELS(?P<body>.*?)(?=\Z)",
    }
    metrics = {}
    for key, pattern in groups.items():
        match = re.search(pattern, text, re.I | re.S)
        if not match:
            raise ValueError(f"Antigravity /usage did not contain the {key} quota group")
        body = match.group("body")
        group_metrics = {}
        for name, heading in (("weekly", "Weekly Limit Remaining"), ("five_hour", "Five Hour Limit Remaining")):
            # Antigravity has three valid layouts:
            # 1. A percentage and refresh time for partially used quota.
            # 2. A 100% value with a separate "Quota available" line.
            # 3. A "Disabled: ..." line when weekly limit is reached, where
            #    the 5-hour limit does not apply (0% remaining).
            block_match = re.search(
                re.escape(heading) + r"(?P<block>.*?)(?=\n\s*(?:Weekly|Five Hour) Limit Remaining|\Z)",
                body, re.I | re.S,
            )
            if not block_match:
                raise ValueError(f"Antigravity /usage did not contain {key} {name} data")
            block = block_match.group("block")
            value = re.search(r"(\d+(?:\.\d+)?)%\s*(?:remaining)?", block, re.I)
            reset = re.search(r"(?:Refreshes?|fully refresh(?:es)?|resets?)\s+in\s+([^\n.]+)", block, re.I)
            if not value:
                if re.search(r"\bdisabled\b|hit your (?:weekly|5-hour|five hour)?\s*limit|does not currently apply", block, re.I):
                    if reset:
                        reset_text = reset.group(1).strip()
                    elif re.search(r"weekly limit", block, re.I):
                        reset_text = "Weekly limit reached"
                    else:
                        reset_text = "Limit reached"
                    group_metrics[name] = {"remaining_pct": 0, "reset": reset_text}
                    continue
                raise ValueError(f"Antigravity /usage did not contain {key} {name} data")
            if reset:
                reset_text = reset.group(1).strip()
            elif re.search(r"Quota available", block, re.I):
                reset_text = "Quota available"
            elif re.search(r"weekly limit", block, re.I):
                reset_text = "Weekly limit reached"
            elif re.search(r"\bdisabled\b", block, re.I):
                reset_text = "Limit reached"
            else:
                reset_text = "Reset time unavailable"
            group_metrics[name] = {"remaining_pct": percentage(value.group(1)), "reset": reset_text}
        metrics[key] = group_metrics
    return {"provider": "antigravity", "account_name": account.group(1).strip(), "plan_type": "Antigravity", "metrics": metrics, "credits": "None"}


def open_terminal() -> tuple[int, int]:
    """Create a normal-sized terminal; zero-sized PTYs break modern TUIs."""
    if pty is None or fcntl is None or termios is None:
        raise RuntimeError("CLI collection requires a Linux/macOS pseudo-terminal host")
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
    return master, slave


def matching_pty_responses(
    text: str, responders: list[tuple[str, str, str]], handled: set[int]
) -> list[tuple[str, str]]:
    """Return newly matched one-shot PTY responses and mark them handled."""
    text = strip_terminal(text)
    matches: list[tuple[str, str]] = []
    for index, (pattern, response, message) in enumerate(responders):
        if index not in handled and re.search(pattern, text, re.I | re.S):
            handled.add(index)
            matches.append((response, message))
    return matches


def pty_command(
    command: list[str], env: dict[str, str], inputs: list[tuple[float, str, str]], timeout: float = 20.0,
    cwd: str | None = None, complete: Callable[[str], bool] | None = None,
    progress: Callable[[str], None] | None = None,
    responders: list[tuple[str, str, str]] | None = None,
) -> str:
    """Run a TUI command, stream meaningful progress, and stop once a panel is complete."""
    master, slave = open_terminal()
    process = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave, env=env, cwd=cwd, close_fds=True)
    os.close(slave)
    transcript = bytearray()
    deadline = time.monotonic() + timeout
    next_input = 0
    handled_responders: set[int] = set()
    started = time.monotonic()
    try:
        while time.monotonic() < deadline:
            elapsed = time.monotonic() - started
            while next_input < len(inputs) and elapsed >= inputs[next_input][0]:
                os.write(master, inputs[next_input][1].encode("utf-8"))
                if progress:
                    progress(inputs[next_input][2])
                next_input += 1
            readable, _, _ = select.select([master], [], [], 0.2)
            if readable:
                try:
                    data = os.read(master, 65536)
                except OSError:
                    break
                if not data:
                    break
                transcript.extend(data)
                decoded = transcript.decode("utf-8", errors="replace")
                for response, message in matching_pty_responses(decoded, responders or [], handled_responders):
                    os.write(master, response.encode("utf-8"))
                    if progress:
                        progress(message)
                if complete and complete(decoded):
                    if progress:
                        progress("Quota panel is complete. Parsing the normalized values now.")
                    break
            if process.poll() is not None and not readable:
                break
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        os.close(master)
    return transcript.decode("utf-8", errors="replace")


class CollectionError(RuntimeError):
    def __init__(self, message: str, transcript: str):
        super().__init__(message)
        self.transcript = transcript


def collection_diagnostics(error: Exception) -> dict:
    """Return useful, credential-safe facts about a failed CLI capture."""
    transcript = clean_terminal_transcript(error.transcript) if isinstance(error, CollectionError) else ""
    lines = [line.strip() for line in transcript.splitlines() if line.strip()]
    provider_error = next((
        line for line in reversed(lines)
        if re.search(r"\b(error|failed|timeout|timed out|network|offline|sign.?in|unauthenticated)\b", line, re.I)
    ), "")
    # A provider error line is useful, but URLs, email addresses, and long
    # opaque values are never copied into telemetry, alerts, or the browser.
    provider_error = re.sub(r"https?://\S+", "[url redacted]", provider_error)
    provider_error = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[account redacted]", provider_error)
    provider_error = re.sub(r"\b[A-Za-z0-9_-]{24,}\b", "[value redacted]", provider_error)
    return {
        "capture_chars": len(transcript),
        "nonempty_lines": len(lines),
        "account_field_seen": bool(re.search(r"^\s*Account:\s*\S", transcript, re.MULTILINE | re.I)),
        "gemini_group_seen": bool(re.search(r"GEMINI MODELS", transcript, re.I)),
        "claude_group_seen": bool(re.search(r"CLAUDE AND GPT MODELS", transcript, re.I)),
        "authentication_prompt_seen": bool(re.search(r"sign.?in|log.?in|authenticate|authorization", transcript, re.I)),
        "provider_error_hint": provider_error[:240],
    }


def archive_failure_evidence(profile: dict, error: Exception, diagnostics: dict) -> str:
    """Save a bounded host-only transcript with likely sensitive values redacted."""
    if not isinstance(error, CollectionError):
        return ""
    evidence_id = uuid.uuid4().hex[:12]
    transcript = clean_terminal_transcript(error.transcript)
    transcript = re.sub(r"https?://\S+", "[url redacted]", transcript)
    transcript = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[account redacted]", transcript)
    transcript = re.sub(r"\b[A-Za-z0-9_-]{24,}\b", "[value redacted]", transcript)
    DEBUG_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(DEBUG_EVIDENCE_DIR, 0o700)
    except OSError:
        pass
    write_json(DEBUG_EVIDENCE_DIR / f"{evidence_id}.json", {
        "evidence_id": evidence_id, "captured_at": utcnow(), "profile_id": profile["id"],
        "provider": profile["provider"], "error": str(error), "diagnostics": diagnostics,
        "redacted_transcript": transcript,
    })
    def modified_at(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:  # A parallel profile capture may have pruned it already.
            return 0.0

    evidence_files = sorted(DEBUG_EVIDENCE_DIR.glob("*.json"), key=modified_at, reverse=True)
    for expired in evidence_files[INCIDENT_HISTORY_LIMIT:]:
        try:
            expired.unlink()
        except OSError:
            pass
    return evidence_id


def profile_environment(profile: dict) -> dict[str, str]:
    profile_id = profile["id"]
    root = PROFILE_ROOT / profile_id
    home = root / "home"
    home.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    os.chmod(home, 0o700)
    # Provider CLIs receive only the variables needed to run. In particular,
    # WAHA keys and collector routing configuration must never reach a child.
    env = {
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "TERM": "xterm-256color",
        "NO_COLOR": "1",
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
    }
    timezone_name = os.environ.get("CYD_MONITOR_TIMEZONE", "").strip() or os.environ.get("TZ", "").strip() or ALERT_TIMEZONE_NAME
    if timezone_name:
        env["TZ"] = timezone_name
    for name in ("SSL_CERT_FILE", "SSL_CERT_DIR"):
        if os.environ.get(name):
            env[name] = os.environ[name]
    node_bin = os.environ.get("CYD_NODE_BIN", str(Path.home() / ".local" / "cyd-node" / "bin"))
    if Path(node_bin).is_dir():
        env["PATH"] = node_bin + os.pathsep + env.get("PATH", "")
    if profile["provider"] == "codex":
        codex_home = root / "codex"
        codex_home.mkdir(exist_ok=True)
        os.chmod(codex_home, 0o700)
        env["CODEX_HOME"] = str(codex_home)
        config = codex_home / "config.toml"
        if not config.exists():
            config.write_text('cli_auth_credentials_store = "file"\n', encoding="utf-8")
            os.chmod(config, 0o600)
    else:
        # Make fresh server-side profiles predictable and privacy-forward. The
        # official CLI supports these persisted settings; they avoid its visual
        # theme wizard and opt out of interaction telemetry by default. If a
        # CLI version still shows a consent screen, LoginSession surfaces it.
        ag_settings = home / ".gemini" / "antigravity-cli" / "settings.json"
        ag_settings.parent.mkdir(parents=True, exist_ok=True)
        if not ag_settings.exists():
            ag_settings.write_text(json.dumps({
                "colorScheme": "terminal", "altScreenMode": "never", "enableTelemetry": False,
            }, indent=2) + "\n", encoding="utf-8")
            os.chmod(ag_settings, 0o600)
    return env


def profile_workdir(profile: dict) -> Path:
    """Give interactive CLIs a writable workspace instead of the read-only image."""
    workdir = PROFILE_ROOT / profile["id"] / "workspace"
    workdir.mkdir(parents=True, exist_ok=True)
    os.chmod(workdir, 0o700)
    return workdir


def cli_executable(provider: str) -> str | None:
    override = os.environ.get("CODEX_BIN" if provider == "codex" else "AGY_BIN")
    candidates = [override] if override else []
    candidates.extend([
        "codex" if provider == "codex" else "agy",
        str(Path.home() / ".local" / "bin" / ("codex" if provider == "codex" else "agy")),
        str(Path.home() / ".local" / "cyd-codex" / "node_modules" / ".bin" / "codex") if provider == "codex" else "",
    ])
    for candidate in candidates:
        if candidate and (os.path.isabs(candidate) and os.access(candidate, os.X_OK) or shutil.which(candidate)):
            return candidate
    return None


CODEX_STATUS_INPUTS: list[tuple[float, str, str]] = [
    (6.0, "/status\r", "Codex started. Asking for the first /status panel…"),
    (14.0, "/status\r", "Codex is still warming up. Refreshing the /status panel…"),
    (24.0, "/status\r", "Waiting for rate-limit values. Retrying /status…"),
    (36.0, "/status\r", "Codex is slow to answer. Retrying /status…"),
    (52.0, "/status\r", "Waiting for final rate-limit values. Retrying /status…"),
]


def collect_profile(profile: dict, include_transcript: bool = False, progress: Callable[[str], None] | None = None):
    provider = profile["provider"]
    executable = cli_executable(provider)
    if not executable:
        raise RuntimeError(f"{'codex' if provider == 'codex' else 'agy'} is not installed on the collector host")
    env = profile_environment(profile)
    if provider == "codex":
        # The collector container is the isolation boundary. Codex otherwise
        # requires bubblewrap, which is intentionally absent from this image.
        # Inline mode avoids the alternate-screen redraw race in Codex 0.147.
        # Cold starts can initially return a refresh request, so retry while
        # watching for a complete panel instead of sleeping for a fixed 80 sec.
        # The capture stops as soon as the panel parses, so asking early costs
        # nothing on a warm start and the later retries cover slow ones.
        raw = pty_command(
            [executable, "--no-alt-screen", "--sandbox", "read-only", "--ask-for-approval", "never"], env,
            CODEX_STATUS_INPUTS,
            timeout=COLLECTION_TIMEOUT_BUDGET, cwd=str(profile_workdir(profile)),
            complete=lambda text: _panel_parses(parse_codex_status, text), progress=progress,
            responders=[(
                r"Update now\s*\(runs .*?\)\s*2\.?\s*Skip",
                "2\r",
                "Codex offered an interactive CLI update. Skipping it inside the read-only collector.",
            )],
        )
        try:
            parsed = parse_codex_status(raw)
        except Exception as error:
            raise CollectionError(str(error), clean_terminal_transcript(raw)) from error
    else:
        # /usage is a scrollable panel. Retry once, then stop as soon as all
        # four provider quota fields parse rather than using a blind timeout.
        raw = pty_command(
            [executable], env,
            [
                (3.0, "/usage\r", "Antigravity started. Opening /usage…"),
                (10.0, "/usage\r", "Refreshing Antigravity's /usage panel…"),
            ],
            timeout=25, cwd=str(profile_workdir(profile)),
            complete=lambda text: _panel_parses(parse_antigravity_usage, text), progress=progress,
        )
        try:
            parsed = parse_antigravity_usage(raw)
        except Exception as error:
            raise CollectionError(str(error), clean_terminal_transcript(raw)) from error
    parsed.update({"profile_id": profile["id"], "label": profile.get("label", ""), "status": "ok", "collected_at": utcnow(), "source": f"{provider} CLI"})
    return (parsed, clean_terminal_transcript(raw)) if include_transcript else parsed


def error_snapshot(profile: dict, error: Exception) -> dict:
    diagnostics = collection_diagnostics(error)
    try:
        diagnostics["evidence_id"] = archive_failure_evidence(profile, error, diagnostics)
    except (OSError, ValueError, TypeError) as storage_error:
        diagnostics["evidence_storage"] = f"unavailable ({type(storage_error).__name__})"
    account_name = account_name_from_transcript(profile["provider"], error.transcript) if isinstance(error, CollectionError) else ""
    account_name = account_name or str(profile.get("last_account_name") or "")[:160]
    return {
        "profile_id": profile["id"], "label": profile.get("label", ""), "provider": profile["provider"],
        "account_name": account_name,
        "status": "error", "error": str(error), "diagnostics": diagnostics,
        "collected_at": utcnow(), "source": "CLI collector",
    }


def waha_settings() -> dict:
    """Read alert routing without ever persisting the WAHA API key."""
    saved = read_json(SETTINGS_FILE, {})
    return {
        "url": os.environ.get("WAHA_URL", "http://127.0.0.1:3000").rstrip("/"),
        "api_key": os.environ.get("WAHA_API_KEY", "").strip(),
        "session": os.environ.get("WAHA_SESSION", "default").strip() or "default",
        "chat_id": str(saved.get("waha_alert_chat_id") or os.environ.get("WAHA_ALERT_CHAT_ID", "")).strip(),
    }


def email_settings() -> dict:
    """Read host-only SMTP fallback settings without persisting credentials."""
    saved = read_json(EMAIL_SECRET_FILE, {})
    env_host = os.environ.get("CYD_MONITOR_SMTP_HOST", "").strip()
    if not env_host and saved:
        return {
            "host": str(saved.get("host", "")).strip(),
            "port": max(1, min(65535, int(saved.get("port", 587)))),
            "security": str(saved.get("security", "starttls")).strip().lower(),
            "username": str(saved.get("username", "")).strip(),
            "password": str(saved.get("password", "")).strip(),
            "sender": str(saved.get("sender", "")).strip(),
            "recipients": [str(item).strip() for item in saved.get("recipients", []) if str(item).strip()][:5],
        }
    return {
        "host": env_host,
        "port": bounded_int_env("CYD_MONITOR_SMTP_PORT", 587, 1, 65535),
        "security": os.environ.get("CYD_MONITOR_SMTP_SECURITY", "starttls").strip().lower(),
        "username": os.environ.get("CYD_MONITOR_SMTP_USERNAME", "").strip(),
        "password": os.environ.get("CYD_MONITOR_SMTP_PASSWORD", "").strip(),
        "sender": os.environ.get("CYD_MONITOR_SMTP_FROM", "").strip(),
        "recipients": [item.strip() for item in os.environ.get("CYD_MONITOR_ALERT_EMAIL_TO", "").split(",") if item.strip()][:5],
    }


def email_fallback_configured(settings: dict | None = None) -> bool:
    settings = settings or email_settings()
    valid_recipients = bool(settings["recipients"]) and all(
        re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", item) for item in settings["recipients"]
    )
    return bool(
        settings["host"] and settings["username"] and settings["password"]
        and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", settings["sender"])
        and valid_recipients and settings["security"] in {"starttls", "tls"}
    )


def record_alert_status(**changes) -> None:
    def apply_changes(current: dict) -> None:
        current.update(changes)
        current["updated_at"] = utcnow()
    update_json(ALERTS_FILE, {}, apply_changes)


def send_email_message(subject: str, body: str) -> tuple[bool, str]:
    """Send through an SMTP transport independent of WAHA and its session."""
    settings = email_settings()
    configured = email_fallback_configured(settings)
    record_alert_status(email_fallback_configured=configured)
    if not configured:
        message = "Email fallback is not configured with TLS SMTP host credentials, sender, and recipient"
        record_alert_status(fallback_email_last_error=message)
        return False, message
    email = EmailMessage()
    email["Subject"] = subject[:180]
    email["From"] = settings["sender"]
    email["To"] = ", ".join(settings["recipients"])
    email.set_content(body)
    context = ssl.create_default_context()
    try:
        if settings["security"] == "tls":
            client = smtplib.SMTP_SSL(settings["host"], settings["port"], timeout=12, context=context)
        else:
            client = smtplib.SMTP(settings["host"], settings["port"], timeout=12)
        with client:
            if settings["security"] == "starttls":
                client.ehlo()
                client.starttls(context=context)
                client.ehlo()
            client.login(settings["username"], settings["password"])
            client.send_message(email)
        record_alert_status(fallback_email_last_success_at=utcnow(), fallback_email_last_error="")
        return True, "Fallback email delivery accepted by the SMTP server."
    except (OSError, ValueError, smtplib.SMTPException) as error:
        message = f"Email fallback failed: {type(error).__name__}"
        record_alert_status(fallback_email_last_error=message)
        return False, message


def send_waha_failure_email(event: str, alert_message: str, waha_error: str) -> tuple[bool, str]:
    """Send one deduplicated fallback email for a distinct failed WAHA message."""
    delivery_key = hashlib.sha256((event + "\0" + alert_message).encode("utf-8")).hexdigest()
    status = read_json(ALERTS_FILE, {})
    if status.get("fallback_email_delivery_key") == delivery_key:
        return True, "Fallback email was already delivered for this WAHA failure."
    delivered, detail = send_email_message(
        "[CYD Usage Monitor] WhatsApp alert delivery failed",
        "The CYD Usage Monitor detected an event, but WAHA could not deliver its WhatsApp notification.\n\n"
        f"WAHA result: {waha_error}\n\nOriginal monitor notification:\n\n{alert_message}\n",
    )
    if delivered:
        record_alert_status(fallback_email_delivery_key=delivery_key, fallback_email_last_event=event)
    return delivered, detail


def send_test_email() -> tuple[bool, str]:
    return send_email_message(
        "[CYD Usage Monitor] Fallback email test",
        "This confirms that the independent SMTP fallback for CYD Usage Monitor alerts is working.\n",
    )


def alert_title(profile: dict, snapshot: dict) -> str:
    error = snapshot.get("error", "")
    if re.search(r"not signed in|sign.?in|auth", error, re.I):
        return "CLI authentication needs attention"
    return "CLI quota collection failed"


def failure_explanation(profile: dict, snapshot: dict) -> str:
    """Explain the observed failure without claiming an unknowable root cause."""
    error = str(snapshot.get("error") or "Unknown collector error")
    facts = snapshot.get("diagnostics") if isinstance(snapshot.get("diagnostics"), dict) else {}
    if profile.get("provider") == "antigravity" and "account field" in error.lower():
        if facts.get("gemini_group_seen") or facts.get("claude_group_seen"):
            return "Antigravity returned a partial /usage screen: quota content appeared, but the Account row was missing."
        if facts.get("authentication_prompt_seen"):
            return "Antigravity showed an authentication prompt instead of a complete /usage screen."
        if not facts.get("capture_chars"):
            return "Antigravity produced no readable terminal output during the /usage capture."
        return "Antigravity's /usage screen never rendered its required Account row during this capture."
    if facts.get("provider_error_hint"):
        return facts["provider_error_hint"]
    return error


def whatsapp_value(value: object) -> str:
    """Prevent dynamic labels from accidentally changing WhatsApp formatting."""
    return re.sub(r"[*_~`]", "", str(value)).strip()


def display_time(value: str | None) -> str:
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(ALERT_TIMEZONE).strftime("%b %d, %Y at %I:%M:%S %p %Z")
    except (TypeError, ValueError):
        return "Unknown time"


def elapsed_text(start: str | None, end: str | None) -> str:
    try:
        first = dt.datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        last = dt.datetime.fromisoformat(str(end).replace("Z", "+00:00"))
        seconds = max(0, round((last - first).total_seconds()))
    except (TypeError, ValueError):
        return "unknown duration"
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def record_incident(profile: dict, previous: dict | None, snapshot: dict) -> None:
    """Keep a bounded structured history; raw CLI transcripts never enter it."""
    was_error = bool(previous and previous.get("status") == "error")
    is_error = snapshot.get("status") == "error"

    def update(history: dict) -> None:
        incidents = history.setdefault("incidents", [])
        if is_error and not was_error:
            incidents.append({
                "id": str(uuid.uuid4()), "profile_id": profile["id"], "provider": profile["provider"],
                "account": snapshot.get("account_name") or profile.get("label") or f"{profile['provider'].title()} account",
                "status": "open", "started_at": snapshot.get("collected_at"), "last_failure_at": snapshot.get("collected_at"),
                "failed_polls": 1, "error": snapshot.get("error", "Unknown collector error"),
                "explanation": failure_explanation(profile, snapshot), "diagnostics": snapshot.get("diagnostics", {}),
            })
        elif is_error and was_error:
            active = next((item for item in reversed(incidents) if item.get("profile_id") == profile["id"] and item.get("status") == "open"), None)
            if active:
                active["last_failure_at"] = snapshot.get("collected_at")
                active["failed_polls"] = int(active.get("failed_polls", 1)) + 1
                active["error"] = snapshot.get("error", active.get("error"))
                active["explanation"] = failure_explanation(profile, snapshot)
                active["diagnostics"] = snapshot.get("diagnostics", {})
        elif not is_error and was_error:
            active = next((item for item in reversed(incidents) if item.get("profile_id") == profile["id"] and item.get("status") == "open"), None)
            if active:
                active["status"] = "recovered"
                active["recovered_at"] = snapshot.get("collected_at")
                active["duration_seconds"] = max(0, round((
                    dt.datetime.fromisoformat(snapshot["collected_at"].replace("Z", "+00:00"))
                    - dt.datetime.fromisoformat(active["started_at"].replace("Z", "+00:00"))
                ).total_seconds()))
                active["resolution"] = "A later scheduled poll read a complete CLI quota panel; no credentials or profile settings were changed."
        history["incidents"] = incidents[-INCIDENT_HISTORY_LIMIT:]
        history["updated_at"] = utcnow()

    if is_error or was_error:
        update_json(INCIDENTS_FILE, {"incidents": []}, update)


def deliver_waha_message(event: str, message: str) -> tuple[bool, str]:
    """Deliver a dashboard/collector alert without exposing the WAHA key."""
    alert_message = message
    settings = waha_settings()
    configured = bool(settings["api_key"] and settings["chat_id"])
    record_alert_status(configured=configured, session=settings["session"], chat_id=settings["chat_id"] if configured else "")
    if not configured:
        error = "WAHA alerts are not configured: set WAHA_API_KEY and a chat ID"
        record_alert_status(last_event=event, last_error=error)
        _, fallback = send_waha_failure_email(event, alert_message, error)
        return False, error + " " + fallback
    payload = json.dumps({"session": settings["session"], "chatId": settings["chat_id"], "text": message}).encode("utf-8")
    request = urlrequest.Request(
        settings["url"] + "/api/sendText", data=payload, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json", "X-Api-Key": settings["api_key"]},
    )
    try:
        with urlrequest.urlopen(request, timeout=12) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"WAHA returned HTTP {response.status}")
        record_alert_status(last_event=event, last_success_at=utcnow(), last_error="")
        return True, "WhatsApp delivery accepted by WAHA."
    except urlerror.HTTPError as error:
        # WAHA's 422 response body names the invalid field (for example a
        # stopped session or malformed chat ID).  Keep that useful diagnosis
        # in the dashboard, while never including request headers/API keys.
        try:
            detail = error.read().decode("utf-8", "replace").strip()
        except OSError:
            detail = ""
        detail = re.sub(r"\s+", " ", detail)
        if settings["api_key"]:
            detail = detail.replace(settings["api_key"], "[redacted]")
        message = f"WAHA delivery failed: HTTP {error.code}"
        if detail:
            message += f": {detail[:600]}"
        record_alert_status(last_event=event, last_error=message)
        _, fallback = send_waha_failure_email(event, alert_message, message)
        return False, message + " " + fallback
    except (OSError, ValueError, RuntimeError, urlerror.URLError) as error:
        message = f"WAHA delivery failed: {error}"
        record_alert_status(last_event=event, last_error=message)
        _, fallback = send_waha_failure_email(event, alert_message, message)
        return False, message + " " + fallback


def send_test_alert() -> tuple[bool, str]:
    return deliver_waha_message(
        "test",
        "🧪 *CYD Usage Monitor · Test*\n\n"
        "✅ *WhatsApp delivery is working*\n"
        "This confirms that WAHA, the selected session, and the monitor's group routing are connected.\n\n"
        f"🕒 *Sent:* {display_time(utcnow())}",
    )


def notify_transition(profile: dict, previous: dict | None, snapshot: dict) -> bool | None:
    """Send at most one confirmed failure and one recovery notice per outage.

    The snapshot itself is the durable deduplication state: restarting the
    collector cannot turn one persistent provider outage into a message flood.
    Incomplete one-off CLI captures remain visible in incident history without
    generating a failure/recovery WhatsApp pair.
    """
    was_alerting = bool(
        previous and previous.get("status") == "error" and previous.get("alert_confirmed", True)
    )
    is_alerting = bool(snapshot.get("status") == "error" and snapshot.get("alert_confirmed", True))
    retry_pending_failure = bool(is_alerting and snapshot.get("alert_delivery_pending"))
    if is_alerting == was_alerting and not retry_pending_failure:
        return None
    if not is_alerting and previous and previous.get("alert_delivery_pending"):
        # Do not send a confusing recovery message when the corresponding
        # failure could not be delivered. The incident remains in history.
        return None
    name = snapshot.get("account_name") or profile.get("label") or profile["provider"].title() + " account"
    if is_alerting:
        event = "failure"
        facts = snapshot.get("diagnostics") if isinstance(snapshot.get("diagnostics"), dict) else {}
        evidence = f"{facts.get('nonempty_lines', 0)} non-empty terminal lines / {facts.get('capture_chars', 0)} characters captured"
        if facts.get("evidence_id"):
            evidence += f" (diagnostic ID {whatsapp_value(facts['evidence_id'])})"
        message = (
            "🚨 *CYD Usage Monitor · Alert*\n\n"
            f"❌ *{alert_title(profile, snapshot)}*\n"
            f"👤 *Account:* {whatsapp_value(name)}\n"
            f"🧩 *Provider:* {whatsapp_value(profile['provider'].title())}\n"
            f"🕒 *First detected:* {display_time(snapshot.get('failure_started_at') or snapshot.get('collected_at'))}\n"
            f"🧮 *Confirmed:* {snapshot.get('consecutive_failures', ALERT_FAILURE_THRESHOLD)} consecutive failed collections\n\n"
            f"❗ *Collector reason:* {whatsapp_value(snapshot.get('error', 'Unknown collector error'))}\n"
            f"*What happened*\n{whatsapp_value(failure_explanation(profile, snapshot))}\n\n"
            f"🔎 *Capture evidence:* {evidence}\n"
            f"🔁 *Automatic action:* retry on the next scheduled poll (every {snapshot.get('refresh_interval_seconds', POLL_SECONDS)} seconds for this account). No credentials were changed.\n\n"
            "🛠️ If it keeps failing, open the protected dashboard → Alerts to inspect the incident history."
        )
    else:
        event = "recovery"
        message = (
            "✅ *CYD Usage Monitor · Recovered*\n\n"
            "🎉 *CLI quota collection is healthy again*\n"
            f"👤 *Account:* {whatsapp_value(name)}\n"
            f"🧩 *Provider:* {whatsapp_value(profile['provider'].title())}\n"
            f"🕒 *Recovered:* {display_time(snapshot.get('collected_at'))}\n"
            f"⏱️ *Interruption:* {elapsed_text((previous.get('failure_started_at') or previous.get('collected_at')) if previous else None, snapshot.get('collected_at'))}\n\n"
            "🔧 *Resolution*\nA later scheduled poll returned a complete quota panel. The monitor recovered automatically; no reconnect or credential change was performed."
        )
    delivered, _ = deliver_waha_message(event, message)
    return delivered


def last_good_snapshot(previous: dict | None) -> dict | None:
    """Return the most recent healthy result carried by a stored snapshot."""
    if not isinstance(previous, dict):
        return None
    if previous.get("status") == "ok":
        return {key: value for key, value in previous.items() if key != "last_ok"}
    last_ok = previous.get("last_ok")
    return last_ok if isinstance(last_ok, dict) and last_ok.get("status") == "ok" else None


def persist_snapshot(profile: dict, snapshot: dict, interval_seconds: int | None = None) -> bool:
    """Persist a result only if its profile still exists after collection."""
    profile_id = profile["id"]
    interval_seconds = int(interval_seconds or POLL_SECONDS)
    with data_lock(DATA_DIR):
        config = read_json_unlocked(PROFILES_FILE, {"profiles": []})
        configured_profile = next((item for item in config.get("profiles", []) if item.get("id") == profile_id), None)
        if configured_profile is None:
            return False
        state = read_json_unlocked(STATE_FILE, {"profiles": {}})
        previous = state.setdefault("profiles", {}).get(profile_id)
        # The server keeps showing the last healthy values through short
        # failures, so a single missed capture never blanks the display.
        snapshot["refresh_interval_seconds"] = interval_seconds
        snapshot["stale_after_seconds"] = stale_after_seconds(interval_seconds)
        snapshot.pop("last_ok", None)
        if snapshot.get("status") == "error":
            last_ok = last_good_snapshot(previous)
            if last_ok:
                snapshot["last_ok"] = last_ok
        account_name = str(snapshot.get("account_name") or "").strip()[:160]
        if not account_name:
            account_name = str(configured_profile.get("last_account_name") or (previous or {}).get("account_name") or "").strip()[:160]
            if account_name:
                snapshot["account_name"] = account_name
        if account_name and configured_profile.get("last_account_name") != account_name:
            configured_profile["last_account_name"] = account_name
            configured_profile["account_recorded_at"] = snapshot.get("collected_at") or utcnow()
            write_json_unlocked(PROFILES_FILE, config)
        if snapshot.get("status") == "error":
            previous_is_error = bool(previous and previous.get("status") == "error")
            previous_confirmed = bool(previous_is_error and previous.get("alert_confirmed", True))
            previous_failures = int(previous.get("consecutive_failures", ALERT_FAILURE_THRESHOLD if previous_confirmed else 0)) if previous_is_error else 0
            snapshot["consecutive_failures"] = previous_failures + 1
            snapshot["failure_started_at"] = (
                previous.get("failure_started_at") or previous.get("collected_at")
                if previous_is_error else snapshot.get("collected_at")
            )
            snapshot["alert_confirmed"] = previous_confirmed or snapshot["consecutive_failures"] >= ALERT_FAILURE_THRESHOLD
            previous_pending = previous.get("alert_delivery_pending") if previous_is_error else False
            if previous_pending is None and previous_confirmed:
                previous_pending = bool(read_json(ALERTS_FILE, {}).get("last_error"))
            snapshot["alert_delivery_pending"] = bool(
                snapshot["alert_confirmed"] and (
                    previous_pending or not previous_confirmed
                )
            )
        state["profiles"][profile_id] = snapshot
        state["updated_at"] = utcnow()
        write_json_unlocked(STATE_FILE, state)
    try:
        record_incident(profile, previous, snapshot)
    except (OSError, ValueError, TypeError, KeyError) as incident_error:
        # Diagnostic persistence must never suppress the actual failure or
        # recovery alert. This credential-free line remains useful in Docker.
        print(json.dumps({
            "event": "incident_history_write_failed", "provider": profile.get("provider"),
            "error_type": type(incident_error).__name__, "at": utcnow(),
        }), flush=True)
    delivery_result = notify_transition(profile, previous, snapshot)
    if delivery_result is not None and snapshot.get("status") == "error":
        snapshot["alert_delivery_pending"] = not delivery_result
        with data_lock(DATA_DIR):
            state = read_json_unlocked(STATE_FILE, {"profiles": {}})
            current = state.setdefault("profiles", {}).get(profile_id)
            if current and current.get("collected_at") == snapshot.get("collected_at"):
                current["alert_delivery_pending"] = not delivery_result
                write_json_unlocked(STATE_FILE, state)
    return True


def collect_and_persist(profile: dict, interval_seconds: int | None = None) -> dict:
    """Collect one profile under its own lock and store the normalized result."""
    with profile_lock(profile["id"]):
        try:
            snapshot = collect_profile(profile)
        except Exception as error:
            snapshot = error_snapshot(profile, error)
        persist_snapshot(profile, snapshot, interval_seconds)
        return snapshot


def profile_interval(profile: dict, active_profile_id: str | None) -> int:
    return ACTIVE_POLL_SECONDS if profile.get("id") == active_profile_id else POLL_SECONDS


def collect_all(force_ids: set[str] | None = None) -> None:
    """Collect every enabled profile once, in parallel, then OpenRouter."""
    config = read_json(PROFILES_FILE, {"profiles": [], "active_profile_id": None})
    active_id = config.get("active_profile_id")
    pending = [
        profile for profile in config.get("profiles", [])
        if profile.get("enabled", True) and profile.get("id")
        and (force_ids is None or profile["id"] in force_ids)
    ]
    slots = threading.Semaphore(MAX_PARALLEL_COLLECTIONS)

    def run(profile: dict) -> None:
        with slots:
            collect_and_persist(profile, profile_interval(profile, active_id))

    workers = [threading.Thread(target=run, args=(profile,), name=f"collect-{profile['id']}", daemon=True) for profile in pending]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    if force_ids is None:
        collect_openrouter()


class CollectionScheduler:
    """Refresh each profile on its own cadence with bounded parallelism.

    The profile selected for the CYD is refreshed every ACTIVE_POLL_SECONDS;
    the rest wait POLL_SECONDS. A newly selected profile therefore becomes due
    immediately, and one slow or hung CLI never delays the other accounts.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic,
                 runner: Callable[[dict, int], object] = collect_and_persist,
                 openrouter_runner: Callable[[], object] = collect_openrouter):
        self.clock = clock
        self.runner = runner
        self.openrouter_runner = openrouter_runner
        self.threads: dict[str, threading.Thread] = {}
        self.last_started: dict[str, float] = {}
        self.openrouter_thread: threading.Thread | None = None
        self.openrouter_started: float | None = None

    def running_ids(self) -> set[str]:
        return {profile_id for profile_id, thread in self.threads.items() if thread.is_alive()}

    def due_profiles(self, config: dict) -> list[tuple[dict, int]]:
        """Return profiles that should start now, most overdue first."""
        now = self.clock()
        running = self.running_ids()
        active_id = config.get("active_profile_id")
        due: list[tuple[tuple[bool, float], dict, int]] = []
        for profile in config.get("profiles", []):
            profile_id = profile.get("id")
            if not profile_id or not profile.get("enabled", True) or profile_id in running:
                continue
            interval = profile_interval(profile, active_id)
            started = self.last_started.get(profile_id)
            overdue = float("inf") if started is None else now - started - interval
            if overdue >= 0:
                # The displayed account always wins a free slot; then most overdue.
                due.append(((profile_id == active_id, overdue), profile, interval))
        due.sort(key=lambda item: item[0], reverse=True)
        return [(profile, interval) for _, profile, interval in due]

    def tick(self, config: dict) -> None:
        # Forget profiles that were removed so their threads do not pin a slot.
        known = {profile.get("id") for profile in config.get("profiles", [])}
        for profile_id in list(self.last_started):
            if profile_id not in known and not (profile_id in self.threads and self.threads[profile_id].is_alive()):
                self.last_started.pop(profile_id, None)
                self.threads.pop(profile_id, None)
        free = MAX_PARALLEL_COLLECTIONS - len(self.running_ids())
        active_id = config.get("active_profile_id")
        for profile, interval in self.due_profiles(config):
            profile_id = profile["id"]
            # The displayed account never queues behind background captures;
            # it may briefly exceed the limit by one.
            if free <= 0 and profile_id != active_id:
                break
            free -= 1
            thread = threading.Thread(target=self.runner, args=(profile, interval), name=f"collect-{profile_id}", daemon=True)
            thread.start()
            self.threads[profile_id] = thread
            self.last_started[profile_id] = self.clock()
        openrouter_running = self.openrouter_thread is not None and self.openrouter_thread.is_alive()
        if not openrouter_running and (self.openrouter_started is None or self.clock() - self.openrouter_started >= POLL_SECONDS):
            self.openrouter_thread = threading.Thread(target=self.openrouter_runner, name="collect-openrouter", daemon=True)
            self.openrouter_thread.start()
            self.openrouter_started = self.clock()

    def schedule(self, config: dict) -> dict:
        """Describe the cadence for the dashboard countdown."""
        running = self.running_ids()
        active_id = config.get("active_profile_id")
        profiles = {}
        now = self.clock()
        for profile in config.get("profiles", []):
            profile_id = profile.get("id")
            if not profile_id or not profile.get("enabled", True):
                continue
            interval = profile_interval(profile, active_id)
            started = self.last_started.get(profile_id)
            # Recomputed from the current cadence so a newly selected account
            # shows its shorter countdown right away.
            profiles[profile_id] = {
                "interval_seconds": interval, "collection_running": profile_id in running,
                "next_poll_at": utc_after(max(0.0, started + interval - now)) if started is not None else None,
            }
        upcoming = sorted(entry["next_poll_at"] for entry in profiles.values() if entry["next_poll_at"])
        return {
            "interval_seconds": ACTIVE_POLL_SECONDS, "background_interval_seconds": POLL_SECONDS,
            "max_parallel": MAX_PARALLEL_COLLECTIONS, "collection_running": bool(running),
            "next_poll_at": upcoming[0] if upcoming else None, "profiles": profiles,
        }


def _panel_parses(parser: Callable[[str], dict], raw: str) -> bool:
    try:
        parser(raw)
        return True
    except (ValueError, KeyError, IndexError, AttributeError):
        return False


def collect_one_with_transcript(profile: dict, progress: Callable[[str], None] | None = None) -> tuple[dict, str]:
    """Collect one profile and persist both the normalized snapshot and raw CLI panel."""
    with profile_lock(profile["id"]):
        transcript = ""
        try:
            snapshot, transcript = collect_profile(profile, include_transcript=True, progress=progress)
        except CollectionError as error:
            snapshot, transcript = error_snapshot(profile, error), error.transcript
        except Exception as error:
            snapshot = error_snapshot(profile, error)
        active_id = read_json(PROFILES_FILE, {}).get("active_profile_id")
        persist_snapshot(profile, snapshot, profile_interval(profile, active_id))
        return snapshot, transcript


class LoginSession:
    """A live device/browser login owned by the host collector process."""
    def __init__(self, profile: dict):
        if pty is None:
            raise RuntimeError("CLI login requires a Linux/macOS pseudo-terminal host")
        self.profile = profile
        self.master, slave = open_terminal()
        provider = profile["provider"]
        executable = cli_executable(provider)
        if not executable:
            raise RuntimeError(f"{'codex' if provider == 'codex' else 'agy'} is not installed on the collector host")
        command = [executable, "login", "--device-auth"] if provider == "codex" else [executable]
        self.process = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave, env=profile_environment(profile), cwd=str(profile_workdir(profile)), close_fds=True)
        os.close(slave)
        self.output = bytearray()
        self.started = time.monotonic()
        self.last_input = ""
        self.events = [f"[collector] Started {provider} CLI sign-in session."]
        self.input_received = False
        self.login_confirmed = False
        self.auto_select_due = self.started + 1.0 if provider == "antigravity" else None
        self.auto_selected = False
        self.onboarding_entered = False
        self.onboarding_continue_due: float | None = None
        self.onboarding_finished = provider == "antigravity"
        self.terms_seen = False
        self.terms_finished = False
        self.workspace_trusted = True
        self.workspace_trust_due: float | None = None
        self.ready_since: float | None = None
        self.succeeded = False
        self.failure_reason = ""

    def note(self, message: str) -> None:
        entry = f"[collector] {message}"
        if not self.events or self.events[-1] != entry:
            self.events.append(entry)

    def transcript(self, output: str) -> str:
        events = "\n".join(self.events)
        return f"{events}\n\n--- provider CLI output ---\n{clean_terminal_transcript(output)}"[-16000:]

    def tick(self, user_input: str = "") -> tuple[str, bool]:
        if self.auto_select_due and not self.auto_selected and time.monotonic() >= self.auto_select_due:
            # Google OAuth is Antigravity's default first menu item. Selecting it
            # avoids exposing a meaningless “press Enter” step in the dashboard.
            os.write(self.master, b"\r")
            self.auto_selected = True
            self.note("Selected Google OAuth (the default Antigravity login method).")
        if user_input and user_input != self.last_input and user_input != "__accept_antigravity_terms__":
            os.write(self.master, (user_input + "\r").encode("utf-8"))
            self.last_input = user_input
            self.input_received = True
            self.note("Received the browser authorization code and forwarded it to Antigravity.")
        while True:
            readable, _, _ = select.select([self.master], [], [], 0)
            if not readable:
                break
            try:
                data = os.read(self.master, 65536)
            except OSError:
                break
            if not data:
                break
            self.output.extend(data)
        output = clean_terminal_transcript(self.output.decode("utf-8", errors="replace"))
        if self.profile["provider"] == "antigravity" and "Choose your color scheme:" in output and not self.onboarding_entered:
            # This is Antigravity's non-auth first-run wizard. Accept its
            # default so a background collector never waits on a decorative UI.
            os.write(self.master, b"\r")
            self.onboarding_entered = True
            self.onboarding_finished = False
            self.onboarding_continue_due = time.monotonic() + 0.8
            self.note("OAuth succeeded. Accepting Antigravity's default color scheme to finish first-run setup.")
        if self.onboarding_continue_due and not self.onboarding_finished and time.monotonic() >= self.onboarding_continue_due:
            os.write(self.master, b"\r")
            self.onboarding_finished = True
            self.note("Color scheme accepted. Checking Antigravity's required first-run notices.")
        if self.profile["provider"] == "antigravity" and "Terms of Service & Data Use" in output and not self.terms_seen:
            # This choice permits Google to collect interaction data. It is
            # deliberately surfaced to the dashboard for the account owner to
            # confirm instead of silently accepting it on their behalf.
            self.terms_seen = True
            self.note("Antigravity is showing its Terms/Data Use choice. Waiting for your explicit confirmation in the dashboard.")
        if user_input == "__accept_antigravity_terms__" and self.terms_seen and not self.terms_finished:
            os.write(self.master, b"\x1b[B\x1b[C\r")
            self.terms_finished = True
            self.ready_since = time.monotonic()
            self.note("First-run consent submitted. Waiting for Antigravity to persist the authenticated profile.")
        if self.profile["provider"] == "antigravity" and "Do you trust the contents of this project?" in output and self.workspace_trust_due is None:
            # The collector creates this isolated, empty workspace itself, so
            # trusting this exact directory does not grant access to user code.
            self.workspace_trusted = False
            self.workspace_trust_due = time.monotonic() + 0.5
            self.note("Antigravity is confirming its collector-owned workspace. Approving this isolated directory.")
        if self.workspace_trust_due and not self.workspace_trusted and time.monotonic() >= self.workspace_trust_due:
            os.write(self.master, b"\r")
            self.workspace_trusted = True
            self.ready_since = time.monotonic()
            self.note("Isolated workspace approved. Waiting for Antigravity to finish saving the profile.")
        if self.profile["provider"] == "codex" and re.search(r"Successfully logged in", output, re.I):
            self.login_confirmed = True
        if self.profile["provider"] == "antigravity" and "Welcome to Antigravity CLI!" in output:
            self.login_confirmed = True
            self.ready_since = self.ready_since or time.monotonic()
        antigravity_ready = self.profile["provider"] == "antigravity" and self.login_confirmed and self.onboarding_finished and (
            self.terms_finished or "Terms of Service & Data Use" not in output
        ) and self.workspace_trusted and self.ready_since is not None and time.monotonic() - self.ready_since >= 2.0
        self.succeeded = bool(self.login_confirmed and (self.profile["provider"] == "codex" or antigravity_ready))
        timed_out = time.monotonic() - self.started > 600
        process_ended = self.process.poll() is not None
        finished = process_ended or self.succeeded or timed_out
        if finished and not self.succeeded:
            self.failure_reason = "Provider sign-in timed out." if timed_out else "Provider CLI exited before sign-in completed."
        if finished and self.process.poll() is None:
            self.process.terminate()
        return output, finished

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        try:
            os.close(self.master)
        except OSError:
            pass


def append_terminal_event(record: dict, message: str, cli_output: str = "") -> str:
    current = record.get("terminal_output", "").rstrip()
    suffix = f"\n\n[collector] {message}"
    if cli_output:
        suffix += f"\n\n--- CLI status output ---\n{cli_output.rstrip()}"
    return (current + suffix)[-16000:]


def scrub_runtime_record(record: dict, *, status: str, phase: str, output: str) -> None:
    """Clear temporary authorization material as soon as a workflow stops."""
    for key in ("login_url", "device_code", "terminal_output", "needs_input", "needs_consent"):
        record.pop(key, None)
    record.update({"status": status, "phase": phase, "output": output, "updated_at": utcnow()})


def consume_login_input(request_id: str) -> str:
    path = LOGIN_INPUT_DIR / f"{request_id}.json"
    with data_lock(LOGIN_INPUT_DIR):
        payload = read_json_unlocked(path, {})
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    return str(payload.get("value", "")) if isinstance(payload, dict) else ""


def cleanup_login_inputs(max_age_seconds: int = 900) -> None:
    if not LOGIN_INPUT_DIR.exists():
        return
    cutoff = time.time() - max_age_seconds
    with data_lock(LOGIN_INPUT_DIR):
        for path in LOGIN_INPUT_DIR.glob("*.json"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except FileNotFoundError:
                continue


def remove_profile_directory(profile_id: str) -> None:
    if not re.fullmatch(r"(?:codex|antigravity)-[0-9a-f]{10}", profile_id):
        raise ValueError("invalid profile identifier")
    root = PROFILE_ROOT.resolve()
    target = (root / profile_id).resolve()
    if target.parent != root:
        raise ValueError("profile path escaped the configured profile root")
    if target.exists():
        shutil.rmtree(target)


def prune_runtime(runtime: dict, limit: int = 100) -> None:
    records = runtime.setdefault("requests", {})
    completed = sorted(
        ((request_id, record) for request_id, record in records.items() if record.get("status") != "running"),
        key=lambda item: str(item[1].get("updated_at", "")), reverse=True,
    )
    keep = {request_id for request_id, _ in completed[:limit]}
    for request_id in list(records):
        if records[request_id].get("status") != "running" and request_id not in keep:
            del records[request_id]


def process_requests(sessions: dict[str, LoginSession]) -> None:
    config = read_json(PROFILES_FILE, {"profiles": []})
    profiles = {profile.get("id"): profile for profile in config.get("profiles", [])}
    control = read_json(CONTROL_FILE, {"requests": []})
    runtime = read_json(RUNTIME_FILE, {"requests": {}})
    records = runtime.setdefault("requests", {})
    changed = False

    # Terminal processes cannot survive a collector restart. Expire every
    # orphaned login and remove any temporary authorization material.
    for request_id, record in records.items():
        if record.get("kind") == "login" and record.get("status") == "running" and request_id not in sessions:
            scrub_runtime_record(
                record, status="expired", phase="login_expired",
                output="Collector restarted. Start sign-in again to receive fresh authorization details.",
            )
            changed = True

    # Removing a profile stops its live terminal before deleting credentials.
    for request_id, session in list(sessions.items()):
        if session.profile.get("id") not in profiles:
            session.close()
            del sessions[request_id]
            record = records.setdefault(request_id, {"kind": "login", "profile_id": session.profile.get("id")})
            scrub_runtime_record(record, status="cancelled", phase="profile_removed", output="Profile was removed.")
            changed = True

    for request in control.get("requests", []):
        request_id = request.get("id")
        if not request_id or request_id in records:
            continue
        kind = request.get("kind")
        profile_id = request.get("profile_id")
        profile = profiles.get(profile_id)

        if kind == "remove_profile":
            record = {"kind": kind, "profile_id": profile_id}
            try:
                remove_profile_directory(str(profile_id))
                scrub_runtime_record(record, status="completed", phase="profile_removed", output="Profile credentials and monitor data were removed.")
            except Exception as error:
                scrub_runtime_record(record, status="error", phase="removal_failed", output=f"Profile credential deletion failed: {error}")
            records[request_id] = record
            changed = True
        elif kind == "collect_openrouter":
            records[request_id] = {
                "kind": kind, "status": "running", "phase": "collecting",
                "updated_at": utcnow(), "output": "Collecting normalized OpenRouter usage.",
            }
            write_json(RUNTIME_FILE, runtime)
            snapshot = collect_openrouter()
            if snapshot and snapshot.get("status") == "ok":
                scrub_runtime_record(records[request_id], status="completed", phase="ready", output="OpenRouter collection completed.")
            else:
                message = (snapshot or {}).get("error", "OpenRouter is not configured")
                scrub_runtime_record(records[request_id], status="error", phase="collection_failed", output=message)
            changed = True
        elif kind == "test_alert":
            delivered, message = send_test_alert()
            records[request_id] = {
                "kind": kind, "status": "completed" if delivered else "error",
                "phase": "alert_delivery", "updated_at": utcnow(), "output": message,
            }
            changed = True
        elif kind == "test_email":
            delivered, message = send_test_email()
            records[request_id] = {
                "kind": kind, "status": "completed" if delivered else "error",
                "phase": "email_delivery", "updated_at": utcnow(), "output": message,
            }
            changed = True
        elif not profile:
            records[request_id] = {
                "kind": kind, "profile_id": profile_id, "status": "error",
                "phase": "profile_missing", "updated_at": utcnow(), "output": "Profile no longer exists.",
            }
            changed = True
        elif kind == "collect":
            login_request_id = request.get("login_request_id")
            records[request_id] = {
                "kind": kind, "profile_id": profile_id, "status": "running",
                "phase": "collecting", "updated_at": utcnow(), "output": "Collecting usage from the provider CLI.",
            }
            if login_request_id and login_request_id in records:
                records[login_request_id].update({
                    "status": "running", "phase": "collecting",
                    "output": "Starting the authenticated CLI usage command.", "updated_at": utcnow(),
                })
            write_json(RUNTIME_FILE, runtime)

            def report_collection_progress(message: str) -> None:
                if login_request_id and login_request_id in records:
                    records[login_request_id].update({
                        "status": "running", "phase": "collecting", "output": message, "updated_at": utcnow(),
                    })
                    write_json(RUNTIME_FILE, runtime)

            try:
                snapshot, _ = collect_one_with_transcript(profile, progress=report_collection_progress)
                if snapshot.get("status") == "ok":
                    scrub_runtime_record(records[request_id], status="completed", phase="ready", output="Collection completed.")
                    if login_request_id and login_request_id in records:
                        records[login_request_id]["account_name"] = snapshot.get("account_name", "this account")
                        scrub_runtime_record(
                            records[login_request_id], status="completed", phase="ready",
                            output="Signed in successfully. Usage was collected and temporary authorization data was cleared.",
                        )
                else:
                    message = "Usage command could not be read: " + snapshot.get("error", "unknown collector error")
                    scrub_runtime_record(records[request_id], status="error", phase="collection_failed", output=message)
                    if login_request_id and login_request_id in records:
                        scrub_runtime_record(records[login_request_id], status="error", phase="collection_failed", output=message)
            except Exception as error:
                message = f"Usage collection failed: {error}"
                scrub_runtime_record(records[request_id], status="error", phase="collection_failed", output=message)
                if login_request_id and login_request_id in records:
                    scrub_runtime_record(records[login_request_id], status="error", phase="collection_failed", output=message)
            changed = True
        elif kind == "login":
            executable = "codex" if profile["provider"] == "codex" else "agy"
            if not cli_executable(profile["provider"]):
                records[request_id] = {
                    "kind": kind, "profile_id": profile_id, "status": "error", "phase": "login_failed",
                    "updated_at": utcnow(), "output": f"{executable} is not installed on the collector host.",
                }
            else:
                try:
                    sessions[request_id] = LoginSession(profile)
                    records[request_id] = {
                        "kind": kind, "status": "running", "phase": "starting", "updated_at": utcnow(),
                        "output": "Starting provider login…", "profile_id": profile_id,
                    }
                except Exception as error:
                    records[request_id] = {
                        "kind": kind, "profile_id": profile_id, "status": "error", "phase": "login_failed",
                        "updated_at": utcnow(), "output": f"Provider login could not start: {error}",
                    }
            changed = True

    for request_id, session in list(sessions.items()):
        user_input = consume_login_input(request_id)
        output, finished = session.tick(user_input)
        if finished:
            session.close()
            del sessions[request_id]
            record = records.setdefault(request_id, {"kind": "login", "profile_id": session.profile["id"]})
            if session.succeeded:
                scrub_runtime_record(
                    record, status="running", phase="collection_queued",
                    output="Sign-in succeeded. Temporary authorization data was cleared; usage collection is queued.",
                )
                collect_request = {
                    "id": str(uuid.uuid4()), "kind": "collect", "profile_id": session.profile["id"],
                    "login_request_id": request_id, "created_at": utcnow(), "status": "pending",
                }
                def queue_collect(latest: dict) -> None:
                    latest.pop("login_inputs", None)
                    latest.setdefault("requests", []).append(collect_request)
                    latest["requests"] = latest["requests"][-200:]
                update_json(CONTROL_FILE, {"requests": []}, queue_collect)
            else:
                scrub_runtime_record(
                    record, status="error", phase="login_failed",
                    output=session.failure_reason or "Provider sign-in did not complete.",
                )
        else:
            login_url = extract_login_url(output)
            code_match = re.search(r"(?:one-time|device) code[^\n]*\n\s*([A-Z0-9-]{4,})", output, re.I) if session.profile["provider"] == "codex" else None
            needs_input = session.profile["provider"] == "antigravity" and not session.input_received and not session.login_confirmed and bool(
                re.search(r"(?:paste|enter).{0,80}(?:authorization|auth).{0,40}code", output, re.I)
            )
            needs_consent = session.profile["provider"] == "antigravity" and session.terms_seen and not session.terms_finished
            records[request_id] = {
                "kind": "login", "status": "running",
                "phase": "terms_consent" if needs_consent else "awaiting_browser",
                "updated_at": utcnow(), "output": "Waiting for provider authorization…",
                "terminal_output": session.transcript(output or "Waiting for CLI login output…"),
                "login_url": login_url, "device_code": code_match.group(1) if code_match else "",
                "needs_input": needs_input, "needs_consent": needs_consent,
                "profile_id": session.profile["id"],
            }
        changed = True

    prune_runtime(runtime)
    if changed:
        write_json(RUNTIME_FILE, runtime)

    processed = set(records)
    if control.get("login_inputs") or any(request.get("id") in processed for request in control.get("requests", [])):
        def prune_control(latest: dict) -> None:
            latest.pop("login_inputs", None)
            latest["requests"] = [request for request in latest.get("requests", []) if request.get("id") not in processed][-200:]
        update_json(CONTROL_FILE, {"requests": []}, prune_control)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Collect each configured profile once and exit")
    args = parser.parse_args()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    record_alert_status(email_fallback_configured=email_fallback_configured())
    if args.once:
        collect_all()
        return
    sessions: dict[str, LoginSession] = {}
    scheduler = CollectionScheduler()
    published_schedule: dict | None = None
    next_input_cleanup = 0.0

    def publish_schedule(schedule: dict) -> None:
        """Expose scheduling state for the dashboard countdown."""
        nonlocal published_schedule
        if schedule == published_schedule:
            return
        payload = dict(schedule, updated_at=utcnow())
        update_json(RUNTIME_FILE, {"requests": {}}, lambda runtime: runtime.update({"schedule": payload}))
        published_schedule = schedule

    while True:
        process_requests(sessions)
        if time.monotonic() >= next_input_cleanup:
            cleanup_login_inputs()
            next_input_cleanup = time.monotonic() + 60
        # CLI panel reads take seconds each. Every profile runs on its own
        # worker thread so a dashboard test alert or account switch is picked
        # up on the next 0.5s tick, and the displayed account refreshes on its
        # faster cadence regardless of how many other accounts exist.
        config = read_json(PROFILES_FILE, {"profiles": [], "active_profile_id": None})
        scheduler.tick(config)
        publish_schedule(scheduler.schedule(config))
        time.sleep(0.5)


if __name__ == "__main__":
    main()
