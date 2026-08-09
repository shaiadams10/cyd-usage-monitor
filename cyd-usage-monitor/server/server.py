#!/usr/bin/env python3
"""HTTP API and dashboard for CLI-collected AI quota snapshots."""
from __future__ import annotations

import base64
import copy
import datetime as dt
import hmac
import json
import os
import re
import secrets
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
ALERTS_FILE = DATA_DIR / "alert-status.json"
SETTINGS_FILE = DATA_DIR / "monitor-settings.json"
ADMIN_SECRET_FILE = DATA_DIR / ".monitor-admin-password"
LOGIN_INPUT_DIR = DATA_DIR / ".login-inputs"
DASHBOARD_FILE = Path(__file__).with_name("dashboard.html")
STATIC_DIR = Path(__file__).with_name("static")
DEVICE_TOKEN = os.environ.get("CYD_API_TOKEN", "").strip()
MAX_REQUEST_BYTES = 32 * 1024


def bounded_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as error:
        raise RuntimeError(f"{name} must be an integer") from error
    if not minimum <= value <= maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return value


POLL_SECONDS = bounded_int_env("CYD_MONITOR_POLL_SECONDS", 90, 60, 86400)
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


def profile_by_id(profile_id: str | None):
    for profile in profiles_config().get("profiles", []):
        if profile.get("id") == profile_id:
            return profile
    return None


def is_stale(snapshot: dict) -> bool:
    try:
        collected = dt.datetime.fromisoformat(snapshot["collected_at"].replace("Z", "+00:00"))
        return (dt.datetime.now(dt.timezone.utc) - collected).total_seconds() > POLL_SECONDS * 2
    except (KeyError, ValueError, TypeError):
        return True


def unavailable(provider: str, message: str) -> dict:
    return {
        "provider": "error", "status": "error", "account_name": "Telemetry unavailable",
        "plan_type": provider.title(), "primary_val": "Unavailable", "primary_pct": 100,
        "primary_tag": "Collector Error", "primary_sub": message[:96], "extra_credits": "None",
        "status_ticker": "* " + message[:100], "collected_at": None,
    }


def cyd_payload() -> dict:
    config = profiles_config()
    profile_id = config.get("active_profile_id")
    profile = profile_by_id(profile_id)
    if not profile:
        return unavailable("collector", "No CLI profile is configured")
    snapshot = read_json(STATE_FILE, {"profiles": {}}).get("profiles", {}).get(profile_id)
    if not snapshot:
        return unavailable(profile.get("provider", "collector"), "Waiting for the CLI collector")
    if snapshot.get("status") != "ok":
        return unavailable(profile.get("provider", "collector"), snapshot.get("error", "CLI collection failed"))
    if is_stale(snapshot):
        return unavailable(profile.get("provider", "collector"), "Last CLI result is stale")

    if snapshot.get("provider") == "antigravity":
        metrics = snapshot["metrics"]
        def usage_sub(metric: dict) -> str:
            reset = metric["reset"]
            return reset if reset.lower().startswith("quota") else "Refresh in: " + reset
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

    primary = snapshot["metrics"].get("primary") or snapshot["metrics"]["monthly"]
    remaining = primary["remaining_pct"]
    return {
        "provider": "codex", "status": "ok", "account_name": snapshot["account_name"],
        "plan_type": snapshot.get("plan_type", "ChatGPT"), "primary_val": f"{remaining}% left",
        "primary_pct": 100 - remaining, "primary_tag": snapshot.get("limit_label", "Monthly Limit"),
        "primary_sub": "Resets " + primary["reset"], "extra_credits": snapshot.get("credits", "None"),
        "status_ticker": "* Codex CLI · " + snapshot["collected_at"], "collected_at": snapshot["collected_at"],
        "source": snapshot.get("source", "codex CLI"),
    }


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
        if path == "/api/v1/cyd-status":
            if not self.device_authorized():
                return self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return self.send_json(cyd_payload())
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
            update_json(PROFILES_FILE, {"profiles": [], "active_profile_id": None}, rotate)
            if not selected["id"]:
                return self.send_json({"error": "no profiles"}, HTTPStatus.NOT_FOUND)
            return self.send_json({"status": "ok", "active_profile_id": selected["id"]})
        if path == "/api/v1/collector-status":
            if not self.require_admin():
                return
            return self.send_json({
                "profiles": profiles_config(), "telemetry": read_json(STATE_FILE, {"profiles": {}}),
                "requests": public_control(),
                "runtime": public_runtime(), "workflow": active_workflow(),
                "alerts": read_json(ALERTS_FILE, {"configured": False, "last_event": None}),
                "alert_settings": alert_settings(),
            })
        if path == "/api/admin/cyd-status":
            if not self.require_admin():
                return
            return self.send_json(cyd_payload())
        if path == "/":
            if not self.require_admin():
                return
            return self.dashboard()
        return self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self):
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
        if path == "/api/admin/active-profile":
            profile_id = body.get("profile_id")
            if not isinstance(profile_id, str):
                return self.send_json({"error": "unknown profile"}, HTTPStatus.NOT_FOUND)
            found = {"value": False}
            def select_profile(config: dict) -> None:
                if profile_id in {profile.get("id") for profile in config.get("profiles", [])}:
                    config["active_profile_id"] = profile_id
                    found["value"] = True
            update_json(PROFILES_FILE, {"profiles": [], "active_profile_id": None}, select_profile)
            if not found["value"]:
                return self.send_json({"error": "unknown profile"}, HTTPStatus.NOT_FOUND)
            return self.send_json({"status": "ok"})
        if path == "/api/admin/alerts":
            chat_value = body.get("chat_id", "")
            if not isinstance(chat_value, str):
                return self.send_json({"error": "chat_id must be text"}, HTTPStatus.BAD_REQUEST)
            chat_id = chat_value.strip()
            if len(chat_id) > 128:
                return self.send_json({"error": "chat ID must be 128 characters or fewer"}, HTTPStatus.BAD_REQUEST)
            if not re.fullmatch(r"[^@\s]+@g\.us", chat_id):
                return self.send_json({"error": "Enter a WhatsApp group ID ending in @g.us"}, HTTPStatus.BAD_REQUEST)
            write_json(SETTINGS_FILE, {"waha_alert_chat_id": chat_id, "updated_at": utcnow()})
            return self.send_json({"status": "ok", "chat_id": chat_id})
        if path == "/api/admin/alerts/test":
            return self.send_json({"request_id": append_request("test_alert")}, HTTPStatus.ACCEPTED)
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


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", 8000), Handler)
    print("CYD CLI monitor server listening on :8000")
    server.serve_forever()


if __name__ == "__main__":
    main()
