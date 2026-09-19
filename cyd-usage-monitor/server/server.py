#!/usr/bin/env python3
"""HTTP API and dashboard for normalized AI usage snapshots."""
from __future__ import annotations

import base64
import copy
import datetime as dt
import hmac
import html
import hashlib
import json
import os
import re
import secrets
import threading
import urllib.parse
import uuid
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from .storage import data_lock, read_json, read_json_unlocked, update_json, write_json, write_json_unlocked
except ImportError:  # Docker runs this file as a top-level script.
    from storage import data_lock, read_json, read_json_unlocked, update_json, write_json, write_json_unlocked


DATA_DIR = Path(os.environ.get("CYD_MONITOR_DATA_DIR", "/app/data"))
PROFILES_FILE = DATA_DIR / "cli-profiles.json"
CONTROL_FILE = DATA_DIR / "collector-control.json"
RUNTIME_FILE = DATA_DIR / "collector-runtime.json"
STATE_FILE = DATA_DIR / "telemetry.json"
OPENROUTER_SECRET_FILE = DATA_DIR / "openrouter-secret.json"
EMAIL_SECRET_FILE = DATA_DIR / "email-secret.json"
OPENROUTER_STATE_FILE = DATA_DIR / "openrouter-telemetry.json"
ALERTS_FILE = DATA_DIR / "alert-status.json"
INCIDENTS_FILE = DATA_DIR / "collector-incidents.json"
SETTINGS_FILE = DATA_DIR / "monitor-settings.json"
ADMIN_SECRET_FILE = DATA_DIR / ".monitor-admin-password"
LOGIN_INPUT_DIR = DATA_DIR / ".login-inputs"
DASHBOARD_FILE = Path(__file__).with_name("dashboard.html")
STATIC_DIR = Path(__file__).with_name("static")
PACKAGED_FLASHING_GUIDE = Path(__file__).with_name("flashing-guide.md")
REPOSITORY_FLASHING_GUIDE = Path(__file__).parents[1] / "instructions" / "FLASHING_GUIDE.md"
FLASHING_GUIDE_FILE = PACKAGED_FLASHING_GUIDE if PACKAGED_FLASHING_GUIDE.is_file() else REPOSITORY_FLASHING_GUIDE
DEVICE_TOKEN = os.environ.get("CYD_API_TOKEN", "").strip()
MAX_REQUEST_BYTES = 32 * 1024
DISPLAY_APPS = {"launcher", "usage", "openrouter"}
SELECTION_SOURCES = {"codex-hook", "antigravity-watch", "antigravity-hook", "stream-deck"}


def selection_history(settings: dict, *, source: str, action: str, app: str,
                      profile_id: str | None = None) -> None:
    """Bounded metadata in the existing atomic settings write; no polling I/O."""
    provider = next((p for p in ("codex", "antigravity")
                     if isinstance(profile_id, str) and profile_id.startswith(p + "-")), "none")
    entry = {"time": utcnow(), "source": source, "action": action, "app": app,
             "provider": provider,
             "account_ref": hashlib.sha256(profile_id.encode()).hexdigest()[:12] if profile_id else ""}
    history = settings.setdefault("selection_history", [])
    entry["sequence"] = history[-1].get("sequence", 0) + 1 if history else 1
    history.append(entry)
    settings["selection_history"] = history[-200:]


def bounded_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as error:
        raise RuntimeError(f"{name} must be an integer") from error
    if not minimum <= value <= maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return value


POLL_SECONDS = bounded_int_env("CYD_MONITOR_POLL_SECONDS", 90, 30, 86400)
if DEVICE_TOKEN and len(DEVICE_TOKEN) < 24:
    raise RuntimeError("CYD_API_TOKEN must contain at least 24 characters")


def admin_password() -> str:
    configured = os.environ.get("MONITOR_ADMIN_PASSWORD", "").strip()
    if configured:
        if len(configured) < 16:
            raise RuntimeError("MONITOR_ADMIN_PASSWORD must contain at least 16 characters")
        return configured
    with data_lock(DATA_DIR):
        try:
            saved = ADMIN_SECRET_FILE.read_text(encoding="utf-8").strip()
            if saved:
                return saved
        except OSError:
            pass
        generated = secrets.token_urlsafe(32)
        fd = os.open(ADMIN_SECRET_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(generated + "\n")
        print(f"Created dashboard credential at {ADMIN_SECRET_FILE}; read it on the trusted host.")
        return generated


ADMIN_PASSWORD = admin_password()


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def profiles_config() -> dict:
    return read_json(PROFILES_FILE, {"profiles": [], "active_profile_id": None})


def alert_settings() -> dict:
    saved = read_json(SETTINGS_FILE, {})
    return {"chat_id": str(saved.get("waha_alert_chat_id", "")).strip()}


def display_settings() -> dict:
    saved = read_json(SETTINGS_FILE, {})
    return {"rotation": 180 if saved.get("display_rotation") == 180 else 0}


def set_display_control(
    settings: dict, app: str, *, profile_id: str | None = None,
    source: str = "dashboard", observed_rotation: int | None = None,
    audit_source: str | None = None, action: str = "display-command",
) -> None:
    """Persist the desired route and the latest known physical display state."""
    rotation = 180 if settings.get("display_rotation") == 180 else 0
    if app == "usage" and not profile_id:
        profile_id = profiles_config().get("active_profile_id")
    command = {"id": uuid.uuid4().hex, "app": app, "created_at": utcnow()}
    if isinstance(profile_id, str) and profile_id:
        command["profile_id"] = profile_id[:80]
    settings["display_command"] = command
    settings["display_state"] = {
        "app": app,
        "profile_id": command.get("profile_id", ""),
        "rotation": observed_rotation if observed_rotation in {0, 180} else rotation,
        "source": source,
        "updated_at": utcnow(),
    }
    selection_history(settings, source=audit_source or source, action=action, app=app,
                      profile_id=command.get("profile_id"))


def display_state() -> dict:
    settings = read_json(SETTINGS_FILE, {})
    state = settings.get("display_state")
    command = settings.get("display_command")
    if not isinstance(state, dict):
        state = {}
    app = state.get("app")
    if app not in DISPLAY_APPS and isinstance(command, dict):
        app = command.get("app")
    if app not in DISPLAY_APPS:
        app = "launcher"
    profile_id = state.get("profile_id")
    if app == "usage" and not profile_id:
        profile_id = profiles_config().get("active_profile_id")
    return {
        "app": app,
        "profile_id": str(profile_id or "")[:80],
        "rotation": 180 if state.get("rotation", settings.get("display_rotation")) == 180 else 0,
        "source": str(state.get("source", "saved"))[:24],
        "updated_at": str(state.get("updated_at", ""))[:40],
    }


def email_public_config() -> dict:
    """Expose setup state without returning SMTP credentials or usernames."""
    saved = read_json(EMAIL_SECRET_FILE, {})
    env_configured = bool(os.environ.get("CYD_MONITOR_SMTP_HOST", "").strip())
    if env_configured:
        recipients = [item.strip() for item in os.environ.get("CYD_MONITOR_ALERT_EMAIL_TO", "").split(",") if item.strip()]
        return {
            "configured": True, "managed_by": "environment", "provider": "environment",
            "sender": os.environ.get("CYD_MONITOR_SMTP_FROM", "").strip(), "recipients": recipients[:5],
        }
    return {
        "configured": EMAIL_SECRET_FILE.is_file() and bool(saved.get("host") and saved.get("password")),
        "managed_by": "dashboard" if EMAIL_SECRET_FILE.is_file() else "dashboard",
        "provider": str(saved.get("provider", "gmail"))[:24],
        "sender": str(saved.get("sender", ""))[:254],
        "recipients": [str(item)[:254] for item in saved.get("recipients", [])[:5]],
        "host": str(saved.get("host", ""))[:253], "port": saved.get("port", 587),
        "security": str(saved.get("security", "starttls"))[:12],
    }


def profile_by_id(profile_id: str | None):
    for profile in profiles_config().get("profiles", []):
        if profile.get("id") == profile_id:
            return profile
    return None


def snapshot_age_seconds(snapshot: dict) -> float | None:
    try:
        collected = dt.datetime.fromisoformat(snapshot["collected_at"].replace("Z", "+00:00"))
        return (dt.datetime.now(dt.timezone.utc) - collected).total_seconds()
    except (KeyError, ValueError, TypeError, AttributeError):
        return None


def stale_budget(snapshot: dict) -> float:
    # The collector stamps each result with its own refresh cadence; a result
    # without one (older collector, OpenRouter) falls back to two poll periods.
    budget = snapshot.get("stale_after_seconds")
    if isinstance(budget, (int, float)) and not isinstance(budget, bool) and budget > 0:
        return float(budget)
    return float(POLL_SECONDS * 2)


def is_stale(snapshot: dict, budget: float | None = None) -> bool:
    age = snapshot_age_seconds(snapshot)
    return age is None or age > (budget if budget is not None else stale_budget(snapshot))


def displayable_snapshot(snapshot: dict) -> tuple[dict | None, str]:
    """Pick the values the CYD should render and why.

    A single failed capture keeps the previous healthy values on screen. The
    error card appears only once the collector confirms the outage (the alert
    threshold) or the last healthy result exceeds the profile's stale budget.
    """
    if snapshot.get("status") == "ok":
        return (None, "stale") if is_stale(snapshot) else (snapshot, "ok")
    last_ok = snapshot.get("last_ok")
    if not isinstance(last_ok, dict) or last_ok.get("status") != "ok":
        return None, "error"
    if snapshot.get("alert_confirmed", True):
        return None, "error"
    if is_stale(last_ok, stale_budget(snapshot)):
        return None, "stale"
    return last_ok, "degraded"


def unavailable(provider: str, message: str, account_name: str = "Telemetry unavailable") -> dict:
    return {
        "provider": "error", "status": "error", "account_name": account_name[:160] or "Telemetry unavailable",
        "plan_type": provider.title(), "primary_val": "Unavailable", "primary_pct": 100,
        "primary_tag": "Collector Error", "primary_sub": message[:96], "extra_credits": "None",
        "status_ticker": "* " + message[:100], "collected_at": None,
    }


def openrouter_public_status() -> dict:
    configured = OPENROUTER_SECRET_FILE.is_file()
    snapshot = read_json(OPENROUTER_STATE_FILE, {})
    if not configured:
        return {"provider": "openrouter", "status": "unconfigured", "account_label": "OpenRouter", "configured": False}
    if not snapshot:
        return {"provider": "openrouter", "status": "error", "account_label": "OpenRouter", "configured": True, "error": "Waiting for the collector"}
    result = copy.deepcopy(snapshot)
    result["configured"] = True
    if result.get("status") == "ok" and is_stale(result):
        result = {
            "provider": "openrouter", "status": "error", "configured": True,
            "account_label": result.get("account_label", "OpenRouter"),
            "error": "Last OpenRouter result is stale", "collected_at": result.get("collected_at"),
        }
    if result.get("status") != "ok":
        result["error"] = str(result.get("error", "OpenRouter telemetry unavailable"))[:120]
    return result


def cyd_payload(profile_id: str | None = None) -> dict:
    if profile_id is None:
        profile_id = profiles_config().get("active_profile_id")
    profile = profile_by_id(profile_id)
    if not profile:
        return unavailable("collector", "No CLI profile is configured")
    snapshot = read_json(STATE_FILE, {"profiles": {}}).get("profiles", {}).get(profile_id)
    if not snapshot:
        return unavailable(
            profile.get("provider", "collector"), "Waiting for the CLI collector",
            profile.get("last_account_name") or profile.get("label") or "Telemetry unavailable",
        )
    shown, reason = displayable_snapshot(snapshot)
    if shown is None:
        return unavailable(
            profile.get("provider", "collector"),
            "Last CLI result is stale" if reason == "stale" else snapshot.get("error", "CLI collection failed"),
            snapshot.get("account_name") or profile.get("last_account_name") or profile.get("label") or "Telemetry unavailable",
        )
    payload = render_snapshot(shown)
    if reason == "degraded":
        # Tell the operator the values are carried over while the collector retries.
        payload["degraded"] = True
        payload["degraded_error"] = str(snapshot.get("error", "CLI collection failed"))[:120]
        payload["status_ticker"] += " · retrying"
    return payload


def render_snapshot(snapshot: dict) -> dict:
    if snapshot.get("provider") == "antigravity":
        metrics = snapshot["metrics"]
        def usage_sub(metric: dict) -> str:
            reset = str(metric.get("reset") or "").strip()
            if not reset:
                return "Reset unavailable"
            lower = reset.lower()
            if lower.startswith(("quota", "weekly", "limit", "disabled", "reset", "refresh")):
                return reset
            return "Refresh in: " + reset
        return {
            "provider": "antigravity", "status": "ok", "account_name": snapshot["account_name"],
            "plan_type": snapshot.get("plan_type", "Antigravity"),
            "gemini_5h_pct": metrics["gemini"]["five_hour"]["remaining_pct"],
            "gemini_5h_sub": usage_sub(metrics["gemini"]["five_hour"]),
            "gemini_weekly_pct": metrics["gemini"]["weekly"]["remaining_pct"],
            "gemini_weekly_sub": usage_sub(metrics["gemini"]["weekly"]),
            "claude_5h_pct": metrics["claude"]["five_hour"]["remaining_pct"],
            "claude_5h_sub": usage_sub(metrics["claude"]["five_hour"]),
            "claude_weekly_pct": metrics["claude"]["weekly"]["remaining_pct"],
            "claude_weekly_sub": usage_sub(metrics["claude"]["weekly"]),
            "extra_credits": snapshot.get("credits", "None"), "collected_at": snapshot["collected_at"],
            "status_ticker": "* Antigravity CLI · " + snapshot["collected_at"],
            "source": snapshot.get("source", "agy CLI"),
        }

    metrics = snapshot["metrics"]
    primary = metrics.get("five_hour") or metrics.get("primary") or metrics.get("weekly") or metrics["monthly"]
    weekly = metrics.get("weekly") or metrics.get("monthly") or primary
    remaining = primary["remaining_pct"]
    return {
        "provider": "codex", "status": "ok", "account_name": snapshot["account_name"],
        "plan_type": snapshot.get("plan_type", "ChatGPT"), "primary_val": f"{remaining}% left",
        "primary_pct": 100 - remaining, "primary_tag": "5-Hour Limit" if metrics.get("five_hour") else snapshot.get("limit_label", "Usage Limit"),
        "primary_sub": "Resets " + primary["reset"], "extra_credits": snapshot.get("credits", "None"),
        "codex_5h_pct": primary["remaining_pct"], "codex_5h_sub": "Resets " + primary["reset"],
        "codex_weekly_pct": weekly["remaining_pct"], "codex_weekly_sub": "Resets " + weekly["reset"],
        "status_ticker": "* Codex CLI · " + snapshot["collected_at"], "collected_at": snapshot["collected_at"],
        "source": snapshot.get("source", "codex CLI"),
    }


def display_command() -> dict:
    settings = read_json(SETTINGS_FILE, {})
    command = settings.get("display_command")
    rotation = 180 if settings.get("display_rotation") == 180 else 0
    if not isinstance(command, dict):
        return {"id": "", "app": "", "rotation": rotation}
    app = command.get("app") if command.get("app") in DISPLAY_APPS else ""
    return {
        "id": str(command.get("id", ""))[:64], "app": app, "rotation": rotation,
        "profile_id": str(command.get("profile_id", ""))[:80],
    }


def display_command_response(after: str | None = None) -> dict:
    # Read command and its profile snapshot under the same storage lock.
    with data_lock(DATA_DIR):
        command = display_command()
        if after is not None and command["id"] and command["id"] != after:
            if command["app"] == "usage":
                command["telemetry"] = cyd_payload(command.get("profile_id") or None)
        return command


def append_request(kind: str, profile_id: str | None = None) -> str:
    request_id = str(uuid.uuid4())
    def append(control: dict) -> None:
        control.pop("login_inputs", None)  # Remove sensitive data from pre-hardening versions.
        control.setdefault("requests", []).append({
            "id": request_id, "kind": kind, "profile_id": profile_id,
            "created_at": utcnow(), "status": "pending",
        })
        control["requests"] = control["requests"][-200:]
    update_json(CONTROL_FILE, {"requests": []}, append)
    return request_id


def public_control() -> dict:
    control = read_json(CONTROL_FILE, {"requests": []})
    allowed = {"id", "kind", "profile_id", "created_at", "status"}
    return {"requests": [
        {key: value for key, value in request.items() if key in allowed}
        for request in control.get("requests", [])[-200:]
    ]}


def public_runtime() -> dict:
    """Return workflow details while ensuring completed secrets never reach the browser."""
    runtime = copy.deepcopy(read_json(RUNTIME_FILE, {"requests": {}}))
    for record in runtime.get("requests", {}).values():
        if record.get("status") != "running":
            for key in ("login_url", "device_code", "terminal_output"):
                record.pop(key, None)
    return runtime


def valid_request_id(value: str) -> bool:
    try:
        return str(uuid.UUID(value)) == value
    except (ValueError, AttributeError, TypeError):
        return False


def active_workflow() -> dict | None:
    """Return the one exclusive CLI workflow, including a request still queued for the collector."""
    profiles = {profile.get("id") for profile in profiles_config().get("profiles", [])}
    runtime = read_json(RUNTIME_FILE, {"requests": {}}).get("requests", {})
    for request_id, record in runtime.items():
        if record.get("status") == "running" and record.get("profile_id") in profiles:
            return {"request_id": request_id, "profile_id": record["profile_id"], "phase": record.get("phase", "running"), "state": "running"}
    for request in read_json(CONTROL_FILE, {"requests": []}).get("requests", []):
        request_id = request.get("id")
        if request_id in runtime or request.get("profile_id") not in profiles:
            continue
        if request.get("kind") in {"login", "collect"}:
            return {"request_id": request_id, "profile_id": request["profile_id"], "phase": "queued", "state": "queued"}
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = "CYD-CLI-Monitor/4"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def is_device_surface(self) -> bool:
        return getattr(self.server, "surface", "dashboard") == "device"

    def log_message(self, format, *args):
        print("%s - %s" % (self.address_string(), format % args))

    def security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        )

    def send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.security_headers()
        self.end_headers()
        self.wfile.write(body)

    def read_body(self) -> dict:
        if "application/json" not in self.headers.get("Content-Type", "").lower():
            raise TypeError("JSON content type is required")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("invalid content length") from error
        if length < 0 or length > MAX_REQUEST_BYTES:
            raise OverflowError("request body is too large")
        raw = self.rfile.read(length).decode("utf-8")
        parsed = json.loads(raw or "{}")
        if not isinstance(parsed, dict):
            raise ValueError("JSON object is required")
        return parsed

    def device_authorized(self) -> bool:
        # The device API exposes usage data and can select the active display.
        # Require a shared token even on private networks so an accidentally
        # exposed port does not become an unauthenticated control surface.
        if not DEVICE_TOKEN:
            return False
        header = self.headers.get("Authorization", "")
        return header.startswith("Bearer ") and hmac.compare_digest(header[7:], DEVICE_TOKEN)

    def admin_authorized(self) -> bool:
        if not ADMIN_PASSWORD:
            return True
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            username, password = base64.b64decode(header[6:], validate=True).decode("utf-8").split(":", 1)
        except Exception:
            return False
        return username == "admin" and hmac.compare_digest(password, ADMIN_PASSWORD)

    def require_admin(self) -> bool:
        if self.admin_authorized():
            return True
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("WWW-Authenticate", 'Basic realm="CYD Monitor"')
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.security_headers()
        self.end_headers()
        return False

    def do_OPTIONS(self):
        return self.send_json({"error": "cross-origin requests are not allowed"}, HTTPStatus.METHOD_NOT_ALLOWED)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if self.is_device_surface():
            if path == "/api/v1/selection-history":
                if not self.device_authorized():
                    return self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                return self.send_json({"events": read_json(SETTINGS_FILE, {}).get("selection_history", [])})
            if path == "/api/v1/accounts":
                if not self.device_authorized():
                    return self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                config = profiles_config()
                snapshots = read_json(STATE_FILE, {"profiles": {}}).get("profiles", {})
                return self.send_json({"accounts": [
                    {"id": profile["id"], "provider": profile.get("provider"),
                     "label": (profile.get("label") or profile.get("last_account_name")
                               or snapshots.get(profile["id"], {}).get("account_name")
                               or profile.get("provider")),
                     "enabled": profile.get("enabled", True),
                     "active": profile["id"] == config.get("active_profile_id")}
                    for profile in config.get("profiles", [])
                ]})
            if path == "/api/v1/cyd-status":
                if not self.device_authorized():
                    return self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                return self.send_json(cyd_payload())
            if path == "/api/v1/openrouter-status":
                if not self.device_authorized():
                    return self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                return self.send_json(openrouter_public_status())
            if path == "/api/v1/display-command":
                if not self.device_authorized():
                    return self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query, keep_blank_values=True)
                after = query.get("after", [None])[0]
                return self.send_json(display_command_response(after))
            if path == "/api/v1/next-account":
                if not self.device_authorized():
                    return self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                selected: dict[str, str | None] = {"id": None}
                def rotate(config: dict) -> None:
                    enabled = [profile for profile in config.get("profiles", []) if profile.get("enabled", True)]
                    if not enabled:
                        return
                    ids = [profile["id"] for profile in enabled]
                    current = config.get("active_profile_id")
                    config["active_profile_id"] = ids[(ids.index(current) + 1) % len(ids)] if current in ids else ids[0]
                    selected["id"] = config["active_profile_id"]
                with data_lock(DATA_DIR):
                    update_json(PROFILES_FILE, {"profiles": [], "active_profile_id": None}, rotate)
                    if not selected["id"]:
                        return self.send_json({"error": "no profiles"}, HTTPStatus.NOT_FOUND)
                    update_json(SETTINGS_FILE, {}, lambda settings: set_display_control(
                        settings, "usage", profile_id=selected["id"], source="device",
                        audit_source=self.selection_source(), action="cycle-account",
                    ))
                return self.send_json(cyd_payload())
            return self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        if path.startswith("/static/"):
            relative = Path(path.removeprefix("/static/"))
            target = (STATIC_DIR / relative).resolve()
            if STATIC_DIR.resolve() not in target.parents or not target.is_file():
                return self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            body = target.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            # The LVGL JavaScript and WASM exports change together.  Caching
            # either for a day can leave a browser running an old ABI after a
            # deployment and silently preserve an obsolete screen layout.
            self.send_header("Cache-Control", "no-store")
            self.security_headers()
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/favicon.ico":
            target = (STATIC_DIR / "favicon.ico").resolve()
            if not target.is_file():
                return self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            body = target.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/x-icon")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.security_headers()
            self.end_headers()
            self.wfile.write(body)
            return
        if path in {"/api/v1/cyd-status", "/api/v1/next-account", "/api/v1/openrouter-status", "/api/v1/display-command", "/api/v1/selection-history"}:
            return self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        if path == "/api/v1/collector-status":
            if not self.require_admin():
                return
            return self.send_json({
                "profiles": profiles_config(), "telemetry": read_json(STATE_FILE, {"profiles": {}}),
                "requests": public_control(),
                "runtime": public_runtime(), "workflow": active_workflow(),
                "alerts": read_json(ALERTS_FILE, {"configured": False, "last_event": None}),
                "incidents": read_json(INCIDENTS_FILE, {"incidents": []}),
                "alert_settings": alert_settings(),
                "display_settings": display_settings(),
                "display_state": display_state(),
                "email_config": email_public_config(),
                "openrouter": openrouter_public_status(),
            })
        if path == "/api/admin/cyd-status":
            if not self.require_admin():
                return
            return self.send_json(cyd_payload())
        if path == "/api/admin/openrouter-status":
            if not self.require_admin():
                return
            return self.send_json(openrouter_public_status())
        if path == "/":
            if not self.require_admin():
                return
            return self.dashboard()
        if path == "/docs/flashing-guide":
            if not self.require_admin():
                return
            return self.flashing_guide()
        return self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def selection_source(self):
        # Attribution is a client claim, not an authentication boundary.
        value = self.headers.get("X-CYD-Source", "")
        return value if value in SELECTION_SOURCES else "device-api"

    def do_POST(self):
        if self.is_device_surface():
            path = urllib.parse.urlparse(self.path).path
            if path not in {"/api/v1/display-state", "/api/v1/select-account"}:
                return self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            if not self.device_authorized():
                return self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            try:
                body = self.read_body()
            except TypeError:
                return self.send_json({"error": "application/json is required"}, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
            except OverflowError:
                return self.send_json({"error": "request body is too large"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
                return self.send_json({"error": "invalid request"}, HTTPStatus.BAD_REQUEST)
            if path == "/api/v1/select-account":
                profile_id = body.get("profile_id")
                if not isinstance(profile_id, str) or not profile_id:
                    return self.send_json({"error": "profile_id is required"}, HTTPStatus.BAD_REQUEST)
                selected = {"ok": False}
                def select_enabled(config: dict) -> None:
                    for profile in config.get("profiles", []):
                        if profile.get("id") == profile_id and profile.get("enabled", True):
                            config["active_profile_id"] = profile_id
                            selected["ok"] = True
                            return
                with data_lock(DATA_DIR):
                    update_json(PROFILES_FILE, {"profiles": [], "active_profile_id": None}, select_enabled)
                    if not selected["ok"]:
                        return self.send_json({"error": "unknown or disabled profile"}, HTTPStatus.NOT_FOUND)
                    update_json(SETTINGS_FILE, {}, lambda settings: set_display_control(
                        settings, "usage", profile_id=profile_id, source="device",
                        audit_source=self.selection_source(), action="select-account",
                    ))
                return self.send_json({"status": "ok", "profile_id": profile_id})
            app = body.get("app")
            rotation = body.get("rotation")
            if app not in DISPLAY_APPS:
                return self.send_json({"error": "app must be launcher, usage, or openrouter"}, HTTPStatus.BAD_REQUEST)
            if isinstance(rotation, bool) or rotation not in {0, 180}:
                return self.send_json({"error": "rotation must be 0 or 180"}, HTTPStatus.BAD_REQUEST)
            update_json(SETTINGS_FILE, {}, lambda settings: set_display_control(
                settings, app, source="device", observed_rotation=rotation,
                audit_source="device-report", action="reported-route",
            ))
            return self.send_json({"status": "ok", "display_state": display_state()})
        if not self.require_admin():
            return
        if self.headers.get("X-CYD-CSRF") != "1":
            return self.send_json({"error": "missing request verification header"}, HTTPStatus.FORBIDDEN)
        try:
            body = self.read_body()
        except TypeError:
            return self.send_json({"error": "application/json is required"}, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        except OverflowError:
            return self.send_json({"error": "request body is too large"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            return self.send_json({"error": "invalid request"}, HTTPStatus.BAD_REQUEST)
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/admin/profiles":
            provider_value = body.get("provider", "")
            label_value = body.get("label", "")
            if not isinstance(provider_value, str) or not isinstance(label_value, str):
                return self.send_json({"error": "provider and label must be text"}, HTTPStatus.BAD_REQUEST)
            provider = provider_value.lower()
            label = label_value.strip()
            if provider not in {"codex", "antigravity"}:
                return self.send_json({"error": "provider is required"}, HTTPStatus.BAD_REQUEST)
            if len(label) > 80:
                return self.send_json({"error": "label must be 80 characters or fewer"}, HTTPStatus.BAD_REQUEST)
            profile = {
                "id": f"{provider}-{uuid.uuid4().hex[:10]}", "provider": provider, "label": label,
                "enabled": True, "created_at": utcnow(),
            }
            def add_profile(config: dict) -> None:
                config.setdefault("profiles", []).append(profile)
                if not config.get("active_profile_id"):
                    config["active_profile_id"] = profile["id"]
            update_json(PROFILES_FILE, {"profiles": [], "active_profile_id": None}, add_profile)
            return self.send_json(profile, HTTPStatus.CREATED)
        if path == "/api/admin/openrouter-config":
            key_value = body.get("key", "")
            label_value = body.get("label", "")
            if not isinstance(key_value, str) or not isinstance(label_value, str):
                return self.send_json({"error": "key and label must be text"}, HTTPStatus.BAD_REQUEST)
            key, label = key_value.strip(), label_value.strip() or "OpenRouter"
            if not key or len(key) > 512:
                return self.send_json({"error": "a valid OpenRouter management key is required"}, HTTPStatus.BAD_REQUEST)
            if len(label) > 80:
                return self.send_json({"error": "label must be 80 characters or fewer"}, HTTPStatus.BAD_REQUEST)
            write_json(OPENROUTER_SECRET_FILE, {"key": key, "label": label, "updated_at": utcnow()})
            request_id = append_request("collect_openrouter")
            return self.send_json({"status": "accepted", "configured": True, "request_id": request_id}, HTTPStatus.ACCEPTED)
        if path == "/api/admin/remove-openrouter-config":
            with data_lock(DATA_DIR):
                for target in (OPENROUTER_SECRET_FILE, OPENROUTER_STATE_FILE):
                    try:
                        target.unlink()
                    except FileNotFoundError:
                        pass
            return self.send_json({"status": "ok", "configured": False})
        if path == "/api/admin/active-profile":
            profile_id = body.get("profile_id")
            if not isinstance(profile_id, str):
                return self.send_json({"error": "unknown profile"}, HTTPStatus.NOT_FOUND)
            found = {"value": False}
            def select_profile(config: dict) -> None:
                if profile_id in {profile.get("id") for profile in config.get("profiles", [])}:
                    config["active_profile_id"] = profile_id
                    found["value"] = True
            with data_lock(DATA_DIR):
                update_json(PROFILES_FILE, {"profiles": [], "active_profile_id": None}, select_profile)
                if not found["value"]:
                    return self.send_json({"error": "unknown profile"}, HTTPStatus.NOT_FOUND)
                update_json(SETTINGS_FILE, {}, lambda settings: set_display_control(
                    settings, "usage", profile_id=profile_id,
                    action="select-account",
                ))
            return self.send_json({"status": "ok"})
        if path == "/api/admin/display-app":
            app = body.get("app")
            if app not in DISPLAY_APPS:
                return self.send_json({"error": "app must be launcher, usage, or openrouter"}, HTTPStatus.BAD_REQUEST)
            if app == "openrouter" and not OPENROUTER_SECRET_FILE.is_file():
                return self.send_json({"error": "OpenRouter is not configured"}, HTTPStatus.CONFLICT)
            update_json(SETTINGS_FILE, {}, lambda settings: set_display_control(settings, app))
            return self.send_json({"status": "ok", "app": app})
        if path == "/api/admin/display-orientation":
            rotation = body.get("rotation")
            if isinstance(rotation, bool) or rotation not in {0, 180}:
                return self.send_json({"error": "rotation must be 0 or 180"}, HTTPStatus.BAD_REQUEST)
            def set_orientation(settings: dict) -> None:
                command = settings.get("display_command")
                if not isinstance(command, dict):
                    command = {}
                state = settings.get("display_state")
                if not isinstance(state, dict):
                    state = {}
                settings["display_rotation"] = rotation
                app = command.get("app")
                if app not in DISPLAY_APPS:
                    app = state.get("app") if state.get("app") in DISPLAY_APPS else "launcher"
                set_display_control(settings, app, profile_id=command.get("profile_id"))
            update_json(SETTINGS_FILE, {}, set_orientation)
            return self.send_json({"status": "ok", "rotation": rotation})
        if path == "/api/admin/alerts":
            chat_value = body.get("chat_id", "")
            if not isinstance(chat_value, str):
                return self.send_json({"error": "chat_id must be text"}, HTTPStatus.BAD_REQUEST)
            chat_id = chat_value.strip()
            if len(chat_id) > 128:
                return self.send_json({"error": "chat ID must be 128 characters or fewer"}, HTTPStatus.BAD_REQUEST)
            if not re.fullmatch(r"[^@\s]+@g\.us", chat_id):
                return self.send_json({"error": "Enter a WhatsApp group ID ending in @g.us"}, HTTPStatus.BAD_REQUEST)
            update_json(SETTINGS_FILE, {}, lambda settings: settings.update({"waha_alert_chat_id": chat_id, "updated_at": utcnow()}))
            return self.send_json({"status": "ok", "chat_id": chat_id})
        if path == "/api/admin/alerts/test":
            return self.send_json({"request_id": append_request("test_alert")}, HTTPStatus.ACCEPTED)
        if path == "/api/admin/alerts/test-email":
            return self.send_json({"request_id": append_request("test_email")}, HTTPStatus.ACCEPTED)
        if path == "/api/admin/email-config":
            if os.environ.get("CYD_MONITOR_SMTP_HOST", "").strip():
                return self.send_json({"error": "Email is managed by the host environment"}, HTTPStatus.CONFLICT)
            provider = body.get("provider", "gmail")
            sender = body.get("sender", "")
            recipient = body.get("recipient", "")
            username = body.get("username", "")
            password = body.get("password", "")
            host = body.get("host", "")
            security = body.get("security", "starttls")
            port = body.get("port", 587)
            if not all(isinstance(value, str) for value in (provider, sender, recipient, username, password, host, security)):
                return self.send_json({"error": "Email settings must be text"}, HTTPStatus.BAD_REQUEST)
            provider, sender, recipient = provider.strip().lower(), sender.strip(), recipient.strip()
            username, password, host, security = username.strip(), password.strip(), host.strip(), security.strip().lower()
            if provider not in {"gmail", "custom"}:
                return self.send_json({"error": "Choose Gmail or custom SMTP"}, HTTPStatus.BAD_REQUEST)
            email_pattern = r"[^@\s]+@[^@\s]+\.[^@\s]+"
            if not re.fullmatch(email_pattern, sender) or not re.fullmatch(email_pattern, recipient):
                return self.send_json({"error": "Enter valid sender and recipient email addresses"}, HTTPStatus.BAD_REQUEST)
            if provider == "gmail":
                host, port, security = "smtp.gmail.com", 587, "starttls"
                username = username or sender
                password = re.sub(r"\s+", "", password)
            else:
                try:
                    port = int(port)
                except (TypeError, ValueError):
                    return self.send_json({"error": "SMTP port must be a number"}, HTTPStatus.BAD_REQUEST)
            if not host or len(host) > 253 or not re.fullmatch(r"[A-Za-z0-9.-]+", host):
                return self.send_json({"error": "Enter a valid SMTP hostname"}, HTTPStatus.BAD_REQUEST)
            if not 1 <= int(port) <= 65535 or security not in {"starttls", "tls"}:
                return self.send_json({"error": "Use a valid port and STARTTLS or TLS"}, HTTPStatus.BAD_REQUEST)
            if not username or len(username) > 254 or not password or len(password) > 1024:
                return self.send_json({"error": "SMTP username and app password/API credential are required"}, HTTPStatus.BAD_REQUEST)
            write_json(EMAIL_SECRET_FILE, {
                "provider": provider, "host": host, "port": int(port), "security": security,
                "username": username, "password": password, "sender": sender,
                "recipients": [recipient], "updated_at": utcnow(),
            })
            return self.send_json({"status": "ok", "configured": True, "email_config": email_public_config()})
        if path == "/api/admin/remove-email-config":
            if os.environ.get("CYD_MONITOR_SMTP_HOST", "").strip():
                return self.send_json({"error": "Email is managed by the host environment"}, HTTPStatus.CONFLICT)
            try:
                EMAIL_SECRET_FILE.unlink()
            except FileNotFoundError:
                pass
            update_json(ALERTS_FILE, {}, lambda alerts: alerts.update({
                "email_fallback_configured": False, "fallback_email_last_error": "",
            }))
            return self.send_json({"status": "ok", "configured": False})
        if path == "/api/admin/collect":
            profile_id = body.get("profile_id")
            with data_lock(DATA_DIR):
                if not isinstance(profile_id, str) or not profile_by_id(profile_id):
                    return self.send_json({"error": "unknown profile"}, HTTPStatus.NOT_FOUND)
                workflow = active_workflow()
                if workflow:
                    return self.send_json({"error": "Another connection workflow is active. Wait for it to finish before refreshing quota.", "workflow": workflow}, HTTPStatus.CONFLICT)
                request_id = append_request("collect", profile_id)
            return self.send_json({"request_id": request_id}, HTTPStatus.ACCEPTED)
        if path == "/api/admin/login":
            profile_id = body.get("profile_id")
            with data_lock(DATA_DIR):
                if not isinstance(profile_id, str) or not profile_by_id(profile_id):
                    return self.send_json({"error": "unknown profile"}, HTTPStatus.NOT_FOUND)
                workflow = active_workflow()
                if workflow:
                    if workflow["profile_id"] == profile_id:
                        return self.send_json({"request_id": workflow["request_id"], "existing": True}, HTTPStatus.ACCEPTED)
                    return self.send_json({"error": "Another account connection is in progress. Finish it before starting a new one.", "workflow": workflow}, HTTPStatus.CONFLICT)
                request_id = append_request("login", profile_id)
            return self.send_json({"request_id": request_id}, HTTPStatus.ACCEPTED)
        if path == "/api/admin/login-input":
            request_id = body.get("request_id", "")
            input_value = body.get("value", "")
            if not isinstance(request_id, str) or not isinstance(input_value, str):
                return self.send_json({"error": "request_id and value must be text"}, HTTPStatus.BAD_REQUEST)
            value = input_value.strip()
            if not valid_request_id(request_id) or not value:
                return self.send_json({"error": "request_id and value are required"}, HTTPStatus.BAD_REQUEST)
            if len(value) > 4096:
                return self.send_json({"error": "authorization input is too long"}, HTTPStatus.BAD_REQUEST)
            runtime = read_json(RUNTIME_FILE, {"requests": {}}).get("requests", {}).get(request_id, {})
            if runtime.get("kind") != "login":
                return self.send_json({"error": "unknown request"}, HTTPStatus.NOT_FOUND)
            if runtime.get("status") != "running" or runtime.get("phase") not in {"awaiting_browser", "terms_consent"}:
                return self.send_json({"error": "login request is no longer active"}, HTTPStatus.CONFLICT)
            LOGIN_INPUT_DIR.mkdir(parents=True, exist_ok=True)
            os.chmod(LOGIN_INPUT_DIR, 0o700)
            write_json(LOGIN_INPUT_DIR / f"{request_id}.json", {"value": value, "created_at": utcnow()})
            return self.send_json({"status": "ok"})
        if path == "/api/admin/remove-profile":
            profile_id = body.get("profile_id")
            if not isinstance(profile_id, str) or not re.fullmatch(r"(?:codex|antigravity)-[0-9a-f]{10}", profile_id):
                return self.send_json({"error": "unknown profile"}, HTTPStatus.NOT_FOUND)
            request_id = str(uuid.uuid4())
            with data_lock(DATA_DIR):
                config = read_json_unlocked(PROFILES_FILE, {"profiles": [], "active_profile_id": None})
                profiles = config.get("profiles", [])
                remaining = [profile for profile in profiles if profile.get("id") != profile_id]
                if len(remaining) == len(profiles):
                    return self.send_json({"error": "unknown profile"}, HTTPStatus.NOT_FOUND)
                config["profiles"] = remaining
                if config.get("active_profile_id") == profile_id:
                    config["active_profile_id"] = remaining[0]["id"] if remaining else None
                    update_json(SETTINGS_FILE, {}, lambda settings: selection_history(
                        settings, source="dashboard", action="remove-active-profile", app="usage",
                        profile_id=config["active_profile_id"]))
                state = read_json_unlocked(STATE_FILE, {"profiles": {}})
                state.get("profiles", {}).pop(profile_id, None)
                control = read_json_unlocked(CONTROL_FILE, {"requests": []})
                control.pop("login_inputs", None)
                control.setdefault("requests", []).append({
                    "id": request_id, "kind": "remove_profile", "profile_id": profile_id,
                    "created_at": utcnow(), "status": "pending",
                })
                control["requests"] = control["requests"][-200:]
                write_json_unlocked(PROFILES_FILE, config)
                write_json_unlocked(STATE_FILE, state)
                write_json_unlocked(CONTROL_FILE, control)
            return self.send_json({"status": "accepted", "request_id": request_id}, HTTPStatus.ACCEPTED)
        return self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def dashboard(self):
        try:
            body = DASHBOARD_FILE.read_bytes()
        except OSError:
            body = b"Dashboard asset is unavailable."
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.security_headers()
        self.end_headers()
        self.wfile.write(body)

    def flashing_guide(self):
        try:
            source = FLASHING_GUIDE_FILE.read_text(encoding="utf-8")
        except OSError:
            return self.send_json({"error": "flashing guide is unavailable"}, HTTPStatus.NOT_FOUND)
        body = (
            "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Flash a CYD · CYD Monitor</title><style>"
            "body{margin:0;background:#0d1013;color:#f1f5f2;font:15px/1.6 system-ui,sans-serif}"
            "main{max-width:920px;margin:auto;padding:32px 22px 64px}a{color:#4ee0b4}"
            "pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.65 Consolas,monospace;"
            "background:#151a1f;border:1px solid #2b343b;padding:22px}"
            "</style></head><body><main><a href=\"/\">← Back to dashboard</a>"
            f"<pre>{html.escape(source)}</pre></main></body></html>"
        ).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.security_headers()
        self.end_headers()
        self.wfile.write(body)


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    dashboard_server = ThreadingHTTPServer(("0.0.0.0", 8000), Handler)
    dashboard_server.surface = "dashboard"
    device_server = ThreadingHTTPServer(("0.0.0.0", 8001), Handler)
    device_server.surface = "device"
    dashboard_thread = threading.Thread(target=dashboard_server.serve_forever, daemon=True)
    dashboard_thread.start()
    print("CYD dashboard listening on :8000; private device API listening on :8001")
    try:
        device_server.serve_forever()
    finally:
        dashboard_server.shutdown()
        dashboard_server.server_close()
        device_server.server_close()


if __name__ == "__main__":
    main()
