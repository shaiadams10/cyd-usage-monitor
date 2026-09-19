"""Windows message hooks. No provider credentials, prompts, or background service.

Private configuration lives in %USERPROFILE%/.cyd-usage-monitor/chat-switch.json.
Only the official Codex account/read interface is used for local identity.
"""
from __future__ import annotations

import datetime as dt
from contextlib import closing
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import queue
import re
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
import urllib.parse
import urllib.request
import urllib.error

PROFILE = re.compile(r"^(codex|antigravity)-[a-f0-9]{10}$")
MAX_INPUT = 8 * 1024 * 1024
MAX_TAIL = 256 * 1024
HISTORY_LIMIT = 1000
SOURCES = {"codex-hook", "antigravity-watch", "antigravity-hook", "antigravity-probe", "watcher"}


def diagnostic(path, source, result, *, stage="event", elapsed_ms=0, event_ns=0,
               context_ref="", account_ref="", error=""):
    """Bounded, best-effort metadata only. Never retain arbitrary exception text."""
    source = source if source in SOURCES else "watcher"
    allowed = {"selected", "ignored", "duplicate", "superseded", "unmapped", "unavailable",
               "sending", "ready", "watch_failed", "overflow", "heartbeat", "hook_called"}
    result = result if result in allowed else "unavailable"
    stage = stage if stage in {"event", "identity", "selection", "transcript", "startup", "watch"} else "event"
    error = error if error in {"timeout", "http", "network", "state", "format", "other"} else ""
    context_ref = context_ref if re.fullmatch(r"[a-f0-9]{12}", context_ref) else ""
    account_ref = account_ref if re.fullmatch(r"[a-f0-9]{12}", account_ref) else ""
    try:
        with closing(sqlite3.connect(path, timeout=0.05)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, time REAL, source TEXT, result TEXT, stage TEXT, elapsed_ms INTEGER, event_ns INTEGER, context_ref TEXT, error TEXT)")
            if "account_ref" not in {row[1] for row in db.execute("PRAGMA table_info(history)")}:
                db.execute("ALTER TABLE history ADD COLUMN account_ref TEXT DEFAULT ''")
            now = time.time()
            # Streaming writes and duplicate callbacks must not flood the journal.
            if result in {"ignored", "duplicate", "heartbeat", "hook_called"} and db.execute(
                "SELECT 1 FROM history WHERE source=? AND result=? AND time>? LIMIT 1",
                (source, result, now - 60)).fetchone():
                return
            db.execute("INSERT INTO history VALUES (NULL,?,?,?,?,?,?,?,?,?)",
                       (now, source, result, stage, max(0, int(elapsed_ms)), int(event_ns), context_ref, error, account_ref))
            db.execute("DELETE FROM history WHERE id <= (SELECT MAX(id) FROM history)-?", (HISTORY_LIMIT,))
    except Exception:
        pass  # Diagnostic failure never blocks chat or changes selection semantics.


def error_code(error):
    if isinstance(error, (TimeoutError, queue.Empty)): return "timeout"
    if isinstance(error, urllib.error.HTTPError): return "http"
    if isinstance(error, urllib.error.URLError): return "network"
    if isinstance(error, sqlite3.Error): return "state"
    if isinstance(error, (ValueError, KeyError, TypeError)): return "format"
    return "other"


def identity_key(email):
    return hashlib.sha256(email.strip().casefold().encode("utf-8")).hexdigest()


def private_dir():
    # MSIX redirects LocalAppData inside Codex. Windows logon tasks and other
    # desktop apps cannot see files written into that package's private cache.
    return Path.home() / ".cyd-usage-monitor"


def private_setting(name):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value = winreg.QueryValueEx(key, name)[0]
            if isinstance(value, str) and value.strip():
                return value
    except OSError:
        pass
    return os.environ.get(name, "")


def api_origin(endpoint):
    u = urllib.parse.urlsplit(endpoint)
    address = ipaddress.IPv4Address(u.hostname or "")
    allowed = any(address in ipaddress.IPv4Network(n) for n in
                  ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
    if (u.scheme != "http" or not allowed or u.username or u.password
            or u.path != "/api/v1/next-account" or u.query or u.fragment):
        raise ValueError("Invalid private endpoint")
    if u.port is not None and not 1 <= u.port <= 65535:
        raise ValueError("Invalid port")
    return f"http://{u.netloc}"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def api_request(path, body=None, *, source=None):
    origin = api_origin(private_setting("CYD_USAGE_MONITOR_NEXT_ACCOUNT_URL"))
    token = private_setting("CYD_API_TOKEN")
    if not token or "\n" in token or "\r" in token:
        raise ValueError("Missing private token")
    request = urllib.request.Request(origin + path,
        data=None if body is None else json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    if source in SOURCES:
        request.add_header("X-CYD-Source", source)
    # Never forward the device token through a configured proxy or redirect.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=0.8) as response:
        return json.loads(response.read(128 * 1024))


def select_account(profile, *, source=None):
    if not PROFILE.fullmatch(profile):
        raise ValueError("Invalid profile")
    result = api_request("/api/v1/select-account", {"profile_id": profile}, source=source)
    if result.get("status") != "ok" or result.get("profile_id") != profile:
        raise ValueError("Selection not confirmed")


def codex_executable(config):
    """Use the configured desktop CLI, rediscovering it after app updates."""
    configured = Path(config["codex_executable"])
    if configured.is_file():
        return configured
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise ValueError("Desktop Codex installation was not found")
    root = Path(local_app_data) / "OpenAI" / "Codex" / "bin"
    candidates = [path for path in root.glob("*/codex.exe") if path.is_file()]
    if not candidates:
        raise ValueError("Desktop Codex installation was not found")
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def codex_account(config):
    """Fresh short-lived official client; never read auth.json or refresh tokens.

    Use the desktop's configured home and executable, not an unrelated PATH CLI.
    No thread is created and no model call is made.
    """
    env = dict(os.environ, CODEX_HOME=config["codex_home"])
    proc = subprocess.Popen([str(codex_executable(config)), "app-server"],
        cwd=config["codex_home"], env=env, stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    messages = queue.Queue()

    def read():
        try:
            for line in proc.stdout:
                if len(line) <= 128 * 1024:
                    messages.put(json.loads(line))
        except (ValueError, OSError):
            pass
        finally:
            messages.put(None)

    worker = threading.Thread(target=read, daemon=True)
    worker.start()
    deadline = time.monotonic() + 1.8

    def send(message):
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    def receive(request_id):
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Identity timeout")
            message = messages.get(timeout=remaining)
            if message is None:
                raise ValueError("Identity client closed")
            if message.get("id") == request_id:
                if "error" in message:
                    raise ValueError("Identity unavailable")
                return message["result"]

    try:
        send({"id": 1, "method": "initialize", "params": {
            "clientInfo": {"name": "cyd_account_switch", "version": "1.0"}}})
        receive(1)
        send({"method": "initialized"})
        send({"id": 2, "method": "account/read", "params": {"refreshToken": False}})
        account = receive(2).get("account") or {}
        if account.get("type") != "chatgpt" or not account.get("email"):
            raise ValueError("No ChatGPT identity")
        return account
    finally:
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=0.3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=0.3)
        worker.join(timeout=0.1)
        proc.stdin.close()
        proc.stdout.close()


def profile_for_account(config, account):
    # Deliberately reject ambiguity rather than fall back to a platform default.
    matches = config.get("codex_accounts", {}).get(identity_key(account["email"]), [])
    matches = [p for p in matches if isinstance(p, str) and
               PROFILE.fullmatch(p) and p.startswith("codex-")]
    return matches[0] if len(matches) == 1 else None


def antigravity_marker(event, config, *, with_timestamp=False):
    """Read only a bounded tail; retain metadata, never message text.

    PreInvocation also runs on continuations. USER_EXPLICIT markers ensure a
    continuation or autonomous task cannot reclaim the screen. Unrecognized
    transcript formats fail closed.
    """
    path = Path(event.get("transcriptPath", "")).resolve()
    roots = [Path(p).resolve() for p in config["antigravity_roots"]]
    if path.name != "transcript.jsonl" or not any(path.is_relative_to(r) for r in roots):
        return None
    with path.open("rb") as stream:
        size = stream.seek(0, 2)
        start = max(0, size - MAX_TAIL)
        stream.seek(start)
        if start:
            stream.readline()  # discard potentially incomplete first record
        data = stream.read(MAX_TAIL)
    latest = None
    for line in data.splitlines():
        try:
            item = json.loads(line)
        except (ValueError, UnicodeError):
            continue
        if item.get("type") == "USER_INPUT" and item.get("source") == "USER_EXPLICIT":
            latest = item
    if latest is None or not isinstance(latest.get("step_index"), int):
        return None
    stamp = dt.datetime.fromisoformat(latest["created_at"].replace("Z", "+00:00")).timestamp()
    if stamp < config["installed_at"] or not -5 <= time.time() - stamp <= 120:
        return None
    conversation = event.get("conversationId")
    if not isinstance(conversation, str) or not conversation:
        return None
    marker = identity_key(conversation + ":" + str(latest["step_index"]) + ":" + latest["created_at"])
    return (marker, int(stamp * 10**9)) if with_timestamp else marker


def connect_state(path):
    db = sqlite3.connect(path, timeout=0.15)
    db.execute("CREATE TABLE IF NOT EXISTS events (marker TEXT PRIMARY KEY, started INTEGER)")
    db.execute("CREATE TABLE IF NOT EXISTS latest (id INTEGER PRIMARY KEY, started INTEGER)")
    db.commit()
    return db


def reserve(db, marker, started):
    with db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM events WHERE marker=?", (marker,)).fetchone():
            return False
        db.execute("INSERT INTO events VALUES (?, ?)", (marker, started))
        db.execute("INSERT INTO latest VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET started=MAX(started, excluded.started)", (started,))
        db.execute("DELETE FROM events WHERE started < ?", (started - 86400 * 10**9,))
    return True


def run(provider, event, config, state_path, *, account_reader=codex_account, sender=None, source=None):
    source = source or ("codex-hook" if provider == "codex" else "antigravity-hook")
    begun = time.monotonic()
    observation = {"stage": "event", "event_ns": 0, "account_ref": ""}
    context = event.get("session_id") if provider == "codex" else event.get("conversationId")
    context_ref = identity_key(context)[:12] if isinstance(context, str) and context else ""
    def send(profile):
        observation["stage"] = "selection"
        (sender(profile) if sender else select_account(profile, source=source))
    try:
        outcome = _run(provider, event, config, state_path, account_reader=account_reader,
                       sender=send, observation=observation)
    except Exception as error:
        diagnostic(state_path, source, "unavailable", elapsed_ms=(time.monotonic()-begun)*1000,
                   context_ref=context_ref, error=error_code(error), **observation)
        raise
    diagnostic(state_path, source, outcome, elapsed_ms=(time.monotonic()-begun)*1000,
               context_ref=context_ref, **observation)
    return outcome


def _run(provider, event, config, state_path, *, account_reader, sender, observation):
    started = time.time_ns()
    if provider == "codex":
        if event.get("hook_event_name") != "UserPromptSubmit" or not event.get("turn_id"):
            return "ignored"
        # A steering message reuses the running turn_id. Each hook invocation
        # is a submission and must select again, even with identical text.
        marker = uuid.uuid4().hex
    elif provider == "antigravity":
        observation["stage"] = "transcript"
        message = antigravity_marker(event, config, with_timestamp=True)
        if message is None:
            return "ignored"
        marker, started = message
        # Use message time, not transcript flush/detection time. Delayed writes
        # must not steal the display from a newer Codex submission.
    else:
        return "ignored"
    observation["event_ns"] = started
    with closing(connect_state(state_path)) as db:
        if not reserve(db, marker, started):
            return "duplicate"
        observation["stage"] = "identity"
        profile = (profile_for_account(config, account_reader(config)) if provider == "codex"
                   else config.get("antigravity_profile"))
        if not profile or not PROFILE.fullmatch(profile) or not profile.startswith(provider + "-"):
            return "unmapped"
        observation["account_ref"] = identity_key(profile)[:12]
        # Serialize sends and suppress older, slower identity queries. Never retry.
        with db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT started FROM latest WHERE id=1").fetchone()[0] != started:
                return "superseded"
            sender(profile)
        return "selected"


def main():
    outcome = "ignored"
    dispatched = False
    try:
        provider = sys.argv[1]
        event = json.loads(sys.stdin.buffer.read(MAX_INPUT + 1))
        config = json.loads((private_dir() / "chat-switch.json").read_text(encoding="utf-8"))
        if provider == "antigravity-probe":
            # Native-hook discovery probe: no API request, no transcript/text retained.
            diagnostic(private_dir() / "chat-switch.sqlite", provider, "hook_called")
            print("{}")
            return
        desktop = os.environ.get("CODEX_INTERNAL_ORIGINATOR_OVERRIDE") == "Codex Desktop"
        if isinstance(event, dict) and config.get("enabled") and (provider != "codex" or desktop):
            dispatched = True
            outcome = run(provider, event, config, private_dir() / "chat-switch.sqlite")
        else:
            diagnostic(private_dir() / "chat-switch.sqlite", provider + "-hook", "ignored")
    except Exception as error:
        outcome = "unavailable"
        # run() logs detailed phase failures; this also catches config/input failures.
        if not dispatched:
            diagnostic(private_dir() / "chat-switch.sqlite", "codex-hook" if sys.argv[1:2] == ["codex"] else "antigravity-hook",
                       outcome, error=error_code(error))
    # Fixed result codes only: no identity, IDs, credentials, paths, or prompts.
    try:
        provider = sys.argv[1] if sys.argv[1] in ("codex", "antigravity") else "unknown"
        result = json.dumps({"time": time.time(), "provider": provider, "result": outcome})
        for name in ("chat-switch-last-result.json", f"chat-switch-{provider}-last-result.json"):
            (private_dir() / name).write_text(result, encoding="utf-8")
    except Exception:
        pass
    # Both hook contracts accept success with an empty JSON object. Fail open for chat.
    print("{}")


if __name__ == "__main__":
    if "--diagnose" in sys.argv:
        try:
            status = json.loads((private_dir() / "antigravity-watcher-status.json").read_text())
            matches = False
            if sys.platform == "win32" and isinstance(status.get("pid"), int):
                code = "$p=Get-CimInstance Win32_Process -Filter 'ProcessId = " + str(status["pid"]) + "'; "
                code += "[bool]($p.Name -eq 'pythonw.exe' -and $p.CommandLine -match [regex]::Escape($env:CYD_DIAG_WATCHER_PATH))"
                try:
                    check = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", code],
                        env=dict(os.environ, CYD_DIAG_WATCHER_PATH=str(private_dir() / "watch-antigravity-messages.py")),
                        capture_output=True, text=True, timeout=4, creationflags=subprocess.CREATE_NO_WINDOW)
                    matches = check.returncode == 0 and check.stdout.strip() == "True"
                except (OSError, subprocess.TimeoutExpired):
                    pass
            print(json.dumps({"watcher_status": status.get("status"),
                "heartbeat_age_seconds": round(time.time() - status["time"]), "pid": status.get("pid"),
                "process_matches": matches,
                "healthy": matches and status.get("status") == "ready" and 0 <= time.time()-status["time"] < 120}))
        except (OSError, ValueError, KeyError):
            print("Watcher status unavailable.")
        path = private_dir() / "chat-switch.sqlite"
        if path.exists():
            try:
                with closing(sqlite3.connect(path)) as db:
                    db.row_factory = sqlite3.Row
                    rows = db.execute("SELECT * FROM history ORDER BY id DESC LIMIT 40").fetchall()
                    for row in reversed(rows):
                        item = dict(row)
                        item["time"] = dt.datetime.fromtimestamp(item["time"]).astimezone().isoformat(timespec="seconds")
                        print(json.dumps(item))
            except sqlite3.Error:
                print("No local history yet.")
        try:
            print(json.dumps({"server": {"events": api_request("/api/v1/selection-history").get("events", [])[-40:]}}))
        except Exception as error:
            print(json.dumps({"server_history": "unavailable", "error": error_code(error)}))
    else:
        main()
