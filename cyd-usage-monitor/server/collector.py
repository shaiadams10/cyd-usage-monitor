#!/usr/bin/env python3
"""Host-side CLI collector for the CYD usage monitor.

Run this on the same host that owns the authenticated `codex` and `agy`
profiles.  It never reads browser auth caches or calls provider HTTP APIs.
It writes only normalized snapshots to the shared monitor data directory.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import select
import shutil
import subprocess
import struct
import threading
import time
import uuid
from pathlib import Path
from typing import Callable
from urllib import error as urlerror
from urllib import request as urlrequest

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
ALERTS_FILE = DATA_DIR / "alert-status.json"
SETTINGS_FILE = DATA_DIR / "monitor-settings.json"
LOGIN_INPUT_DIR = DATA_DIR / ".login-inputs"
PROFILE_ROOT = Path(os.environ.get("CYD_MONITOR_PROFILE_ROOT", "/profiles"))
COLLECTION_LOCK = threading.Lock()


def bounded_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as error:
        raise RuntimeError(f"{name} must be an integer") from error
    if not minimum <= value <= maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return value


POLL_SECONDS = bounded_int_env("CYD_MONITOR_POLL_SECONDS", 90, 60, 86400)


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def utc_after(seconds: float) -> str:
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


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
    limit = re.search(r"(?P<label>Monthly|Weekly) limit:\s*(?:\[[^\n]*\]\s*)?(?P<pct>\d+(?:\.\d+)?)%\s+left\s*\(resets\s+(?P<reset>[^)]*)\)", text, re.I)
    credits = re.search(r"^\s*(?:[│|]\s*)?Credits:\s*(.+?)\s*(?:[│|])?\s*$", text, re.MULTILINE | re.I)
    if not account or not limit:
        raise ValueError("Codex /status did not contain account and a monthly or weekly limit field")
    return {
        "provider": "codex",
        "account_name": account.group(1).strip(),
        "plan_type": account.group(2).strip() or "ChatGPT",
        "metrics": {
            "primary": {"remaining_pct": percentage(limit.group("pct")), "reset": limit.group("reset").strip()}
        },
        "limit_label": limit.group("label").title() + " Limit",
        "credits": credits.group(1).strip() if credits else "None",
    }


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
            # Antigravity has two valid layouts: a reset time for a partially
            # used quota, or a separate "Quota available" line at 100%.
            block_match = re.search(
                re.escape(heading) + r"(?P<block>.*?)(?=\n\s*(?:Weekly|Five Hour) Limit Remaining|\Z)",
                body, re.I | re.S,
            )
            if not block_match:
                raise ValueError(f"Antigravity /usage did not contain {key} {name} data")
            block = block_match.group("block")
            value = re.search(r"(\d+(?:\.\d+)?)%\s*(?:remaining)?", block, re.I)
            reset = re.search(r"Refreshes?\s+in\s+([^\n]+)", block, re.I)
            if not value:
                raise ValueError(f"Antigravity /usage did not contain {key} {name} data")
            reset_text = reset.group(1).strip() if reset else "Quota available" if re.search(r"Quota available", block, re.I) else "Reset time unavailable"
            group_metrics[name] = {"remaining_pct": percentage(value.group(1)), "reset": reset_text}
            continue
            item = re.search(
                heading + r".*?(\d+(?:\.\d+)?)%\s+remaining\s*[·.]\s*Refreshes?\s+in\s+([^\n]+)",
                body,
                re.I | re.S,
            )
            if not item:
                raise ValueError(f"Antigravity /usage did not contain {key} {name} data")
            group_metrics[name] = {"remaining_pct": percentage(item.group(1)), "reset": item.group(2).strip()}
        metrics[key] = group_metrics
    return {"provider": "antigravity", "account_name": account.group(1).strip(), "plan_type": "Antigravity", "metrics": metrics, "credits": "None"}


def open_terminal() -> tuple[int, int]:
    """Create a normal-sized terminal; zero-sized PTYs break modern TUIs."""
    if pty is None or fcntl is None or termios is None:
        raise RuntimeError("CLI collection requires a Linux/macOS pseudo-terminal host")
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
    return master, slave


def pty_command(
    command: list[str], env: dict[str, str], inputs: list[tuple[float, str, str]], timeout: float = 20.0,
    cwd: str | None = None, complete: Callable[[str], bool] | None = None,
    progress: Callable[[str], None] | None = None,
) -> str:
    """Run a TUI command, stream meaningful progress, and stop once a panel is complete."""
    master, slave = open_terminal()
    process = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave, env=env, cwd=cwd, close_fds=True)
    os.close(slave)
    transcript = bytearray()
    deadline = time.monotonic() + timeout
    next_input = 0
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
                if complete and complete(transcript.decode("utf-8", errors="replace")):
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
        raw = pty_command(
            [executable, "--no-alt-screen", "--sandbox", "read-only", "--ask-for-approval", "never"], env,
            [
                (18.0, "/status\r", "Codex started. Asking for the first /status panel…"),
                (36.0, "/status\r", "Codex is still warming up. Refreshing the /status panel…"),
                (52.0, "/status\r", "Waiting for final rate-limit values. Retrying /status…"),
            ],
            timeout=60, cwd=str(profile_workdir(profile)),
            complete=lambda text: _panel_parses(parse_codex_status, text), progress=progress,
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
    return {"profile_id": profile["id"], "label": profile.get("label", ""), "provider": profile["provider"], "status": "error", "error": str(error), "collected_at": utcnow(), "source": "CLI collector"}


def waha_settings() -> dict:
    """Read alert routing without ever persisting the WAHA API key."""
    saved = read_json(SETTINGS_FILE, {})
    return {
        "url": os.environ.get("WAHA_URL", "http://127.0.0.1:3000").rstrip("/"),
        "api_key": os.environ.get("WAHA_API_KEY", "").strip(),
        "session": os.environ.get("WAHA_SESSION", "default").strip() or "default",
        "chat_id": str(saved.get("waha_alert_chat_id") or os.environ.get("WAHA_ALERT_CHAT_ID", "")).strip(),
    }


def record_alert_status(**changes) -> None:
    def apply_changes(current: dict) -> None:
        current.update(changes)
        current["updated_at"] = utcnow()
    update_json(ALERTS_FILE, {}, apply_changes)


def alert_title(profile: dict, snapshot: dict) -> str:
    error = snapshot.get("error", "")
    if re.search(r"not signed in|sign.?in|auth", error, re.I):
        return "CLI authentication needs attention"
    return "CLI quota collection failed"


def deliver_waha_message(event: str, message: str) -> tuple[bool, str]:
    """Deliver a dashboard/collector alert without exposing the WAHA key."""
    settings = waha_settings()
    configured = bool(settings["api_key"] and settings["chat_id"])
    record_alert_status(configured=configured, session=settings["session"], chat_id=settings["chat_id"] if configured else "")
    if not configured:
        error = "WAHA alerts are not configured: set WAHA_API_KEY and a chat ID"
        record_alert_status(last_event=event, last_error=error)
        return False, error
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
        return False, message
    except (OSError, ValueError, RuntimeError, urlerror.URLError) as error:
        message = f"WAHA delivery failed: {error}"
        record_alert_status(last_event=event, last_error=message)
        return False, message


def send_test_alert() -> tuple[bool, str]:
    return deliver_waha_message(
        "test",
        "CYD usage monitor test alert\nThis confirms the WAHA routing configured in the monitor dashboard.",
    )


def notify_transition(profile: dict, previous: dict | None, snapshot: dict) -> None:
    """Send at most one failure and one recovery notice per outage.

    The snapshot itself is the durable deduplication state: restarting the
    collector cannot turn one persistent provider outage into a message flood.
    """
    was_error = bool(previous and previous.get("status") == "error")
    is_error = snapshot.get("status") == "error"
    if is_error == was_error:
        return
    name = snapshot.get("account_name") or profile.get("label") or profile["provider"].title() + " account"
    if is_error:
        event = "failure"
        message = (
            "CYD usage monitor alert\n"
            f"{alert_title(profile, snapshot)}\n"
            f"Account: {name}\nProvider: {profile['provider']}\n"
            f"Reason: {snapshot.get('error', 'unknown collector error')}\n"
            "Open the protected monitor dashboard to reconnect or inspect the CLI transcript."
        )
    else:
        event = "recovery"
        message = (
            "CYD usage monitor recovered\n"
            f"Account: {name}\nProvider: {profile['provider']}\n"
            "The authenticated CLI quota panel is readable again."
        )
    deliver_waha_message(event, message)


def persist_snapshot(profile: dict, snapshot: dict) -> bool:
    """Persist a result only if its profile still exists after collection."""
    profile_id = profile["id"]
    with data_lock(DATA_DIR):
        config = read_json_unlocked(PROFILES_FILE, {"profiles": []})
        if profile_id not in {item.get("id") for item in config.get("profiles", [])}:
            return False
        state = read_json_unlocked(STATE_FILE, {"profiles": {}})
        previous = state.setdefault("profiles", {}).get(profile_id)
        state["profiles"][profile_id] = snapshot
        state["updated_at"] = utcnow()
        write_json_unlocked(STATE_FILE, state)
    notify_transition(profile, previous, snapshot)
    return True


def collect_all(force_ids: set[str] | None = None) -> None:
    with COLLECTION_LOCK:
        config = read_json(PROFILES_FILE, {"profiles": [], "active_profile_id": None})
        for profile in config.get("profiles", []):
            if not profile.get("enabled", True):
                continue
            profile_id = profile.get("id")
            if not profile_id or (force_ids is not None and profile_id not in force_ids):
                continue
            try:
                snapshot = collect_profile(profile)
            except Exception as error:
                snapshot = error_snapshot(profile, error)
            persist_snapshot(profile, snapshot)


def _panel_parses(parser: Callable[[str], dict], raw: str) -> bool:
    try:
        parser(raw)
        return True
    except (ValueError, KeyError, IndexError, AttributeError):
        return False


def collect_one_with_transcript(profile: dict, progress: Callable[[str], None] | None = None) -> tuple[dict, str]:
    """Collect one profile and persist both the normalized snapshot and raw CLI panel."""
    with COLLECTION_LOCK:
        transcript = ""
        try:
            snapshot, transcript = collect_profile(profile, include_transcript=True, progress=progress)
        except CollectionError as error:
            snapshot, transcript = error_snapshot(profile, error), error.transcript
        except Exception as error:
            snapshot = error_snapshot(profile, error)
        persist_snapshot(profile, snapshot)
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
        elif kind == "test_alert":
            delivered, message = send_test_alert()
            records[request_id] = {
                "kind": kind, "status": "completed" if delivered else "error",
                "phase": "alert_delivery", "updated_at": utcnow(), "output": message,
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
    if args.once:
        collect_all()
        return
    sessions: dict[str, LoginSession] = {}
    last_collection = 0.0
    scheduled_collection: threading.Thread | None = None
    schedule_running: bool | None = None
    schedule_due: str | None = None
    next_input_cleanup = 0.0

    def publish_schedule(running: bool, due: str | None) -> None:
        """Expose scheduling state for the dashboard countdown."""
        nonlocal schedule_running, schedule_due
        if running == schedule_running and due == schedule_due:
            return
        schedule = {
            "interval_seconds": POLL_SECONDS, "collection_running": running,
            "next_poll_at": due, "updated_at": utcnow(),
        }
        update_json(RUNTIME_FILE, {"requests": {}}, lambda runtime: runtime.update({"schedule": schedule}))
        schedule_running, schedule_due = running, due

    while True:
        process_requests(sessions)
        if time.monotonic() >= next_input_cleanup:
            cleanup_login_inputs()
            next_input_cleanup = time.monotonic() + 60
        # Scheduled CLI panel reads can take tens of seconds across several
        # accounts.  Keep them off the event loop so a dashboard test alert is
        # picked up on the next 0.5s tick instead of waiting for every CLI.
        running = scheduled_collection is not None and scheduled_collection.is_alive()
        if not running and time.monotonic() - last_collection >= POLL_SECONDS:
            scheduled_collection = threading.Thread(target=collect_all, name="scheduled-cli-collection", daemon=True)
            scheduled_collection.start()
            last_collection = time.monotonic()
            schedule_due = utc_after(POLL_SECONDS)
            publish_schedule(True, schedule_due)
        elif running:
            publish_schedule(True, schedule_due)
        else:
            publish_schedule(False, schedule_due)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
