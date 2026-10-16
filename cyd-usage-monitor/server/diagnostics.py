"""Bounded, private collection timeline. Never store raw terminal output here."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import traceback
import uuid
from contextlib import closing
from pathlib import Path

RETENTION_DAYS = 30
MAX_EVENTS = 100_000


def redact(value: object, limit: int = 500) -> str:
    text = str(value)
    text = re.sub(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|.)", "", text)
    text = re.sub(r"https?://\S+", "[url redacted]", text)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[account redacted]", text)
    text = re.sub(r"(?i)\b(?:bearer\s+|(?:token|secret|password|authorization|api[_-]?key)\s*[:=]\s*)[^\s,;]+", "[secret redacted]", text)
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[address redacted]", text)
    text = re.sub(r"(?i)\b[A-Z]:[\\/][^\s\"'<>]+|(?<!\w)/(?:[\w.-]+/)+[^\s\"'<>]*", "[path redacted]", text)
    text = re.sub(r"\b[A-Za-z0-9_-]{24,}\b", "[value redacted]", text)
    return text[:limit]


def failure_category(message: str, transcript: str = "") -> str:
    text = message + "\n" + transcript
    if re.search(r"unrecognized command|unknown command", text, re.I):
        return "cli_input"
    # The initial 'not signed in' splash is normal. Only a final login prompt
    # with no account panel is evidence that authentication blocked collection.
    if not re.search(r"Account:\s*\S", transcript, re.I) and re.search(
        r"Select login method|authorization code|please (?:sign|log) in|unauthenticated", text, re.I
    ):
        return "authentication"
    if re.search(r"TLS|certificate|network|timed?\s*out|timeout|ECONN|ENOTFOUND", text, re.I):
        return "network"
    if re.search(r"stabiliz|confirmation|matching /status", message, re.I):
        return "confirmation"
    if re.search(r"not installed|pseudo-terminal", message, re.I):
        return "configuration"
    if re.search(r"did not contain|render|quota.*invalid", message, re.I):
        return "panel_incomplete"
    return "unexpected"


def exception_frames(error: Exception) -> list[str]:
    return [f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}"
            for frame in traceback.extract_tb(error.__traceback__)[-8:]]


def _connect(data_dir: Path, *, readonly: bool = False) -> sqlite3.Connection:
    path = data_dir / "collector-events.sqlite3"
    if readonly:
        return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
    data_dir.mkdir(parents=True, exist_ok=True)
    # Precreate privately; never expose a permissive SQLite file, even briefly.
    fd = os.open(path, os.O_CREAT | os.O_WRONLY, 0o600)
    os.close(fd)
    connection = sqlite3.connect(path, timeout=2)
    try:
        connection.execute("PRAGMA auto_vacuum=INCREMENTAL")
        connection.execute("CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY, at TEXT NOT NULL, provider TEXT NOT NULL, profile_ref TEXT NOT NULL, outcome TEXT NOT NULL, payload TEXT NOT NULL)")
        connection.execute("CREATE INDEX IF NOT EXISTS events_filter ON events(provider, outcome, sequence)")
    except sqlite3.Error:
        connection.close()
        raise
    return connection


def record_event(data_dir: Path, event: str, *, profile: dict | None = None,
                 outcome: str = "info", **facts) -> str:
    """Best effort diagnostics cannot break collection or notification delivery."""
    profile = profile or {}
    event_id = uuid.uuid4().hex[:12]
    payload = {
        "id": event_id, "at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "event": event, "provider": profile.get("provider", "collector"),
        "profile_ref": hashlib.sha256(str(profile.get("id", "")).encode()).hexdigest()[:12] if profile.get("id") else "",
        "outcome": outcome,
    }
    allowed = {"attempt_id", "duration_ms", "category", "error", "error_type", "frames", "capture",
               "consecutive_failures", "evidence_id", "missing_groups", "stage", "native_error_hint", "removed_files"}
    for key, value in facts.items():
        if key not in allowed:
            continue
        if isinstance(value, str):
            value = redact(value)
        elif key == "frames":
            value = [redact(item, 120) for item in value[:8]]
        elif key == "capture":
            capture = {k: v for k, v in value.items() if k in {
                "stop_reason", "duration_ms", "requests_sent", "exit_code", "capture_chars", "confirmation_requests"}
                     and (v is None or isinstance(v, (int, float, bool)) or
                          isinstance(v, str) and v in {"complete", "timeout", "cli_exited", "read_closed", "capture_limit"})}
            version = value.get("cli_version")
            if isinstance(version, str) and re.fullmatch(r"\d{1,4}\.\d{1,4}\.\d{1,4}(?:[-+][A-Za-z0-9.-]{1,40})?", version):
                capture["cli_version"] = version
            value = capture
        payload[key] = value
    try:
        with closing(_connect(data_dir)) as connection, connection:
            connection.execute("INSERT INTO events(at, provider, profile_ref, outcome, payload) VALUES (?,?,?,?,?)",
                               (payload["at"], payload["provider"], payload["profile_ref"], outcome, json.dumps(payload)))
            sequence = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
            connection.execute("DELETE FROM events WHERE sequence <= ?", (sequence - MAX_EVENTS,))
            if sequence % 100 == 0:
                cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=RETENTION_DAYS)).isoformat().replace("+00:00", "Z")
                connection.execute("DELETE FROM events WHERE sequence <= ? OR at < ?", (sequence - MAX_EVENTS, cutoff))
                connection.execute("PRAGMA incremental_vacuum(100)")
    except (OSError, sqlite3.Error):
        print(json.dumps({"event": "diagnostic_storage_unavailable", "at": payload["at"]}), flush=True)
    print(json.dumps(payload), flush=True)
    return event_id


def query_events(data_dir: Path, *, provider: str = "", outcome: str = "", query: str = "",
                 before: int = 0, limit: int = 100) -> dict:
    result = {"events": [], "next_before": None, "retention_days": RETENTION_DAYS,
              "max_events": MAX_EVENTS, "storage": "ready"}
    if not (data_dir / "collector-events.sqlite3").exists():
        result["storage"] = "not_started"
        return result
    clauses, args = [], []
    for column, value in (("provider", provider), ("outcome", outcome)):
        if value:
            clauses.append(column + " = ?")
            args.append(value)
    if before:
        clauses.append("sequence < ?")
        args.append(before)
    if query:
        clauses.append("instr(lower(payload), lower(?)) > 0")
        args.append(query[:120])
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    try:
        with closing(_connect(data_dir, readonly=True)) as connection:
            rows = connection.execute("SELECT sequence, payload FROM events" + where + " ORDER BY sequence DESC LIMIT ?",
                                      args + [max(1, min(limit, 100))]).fetchall()
        result["events"] = [dict(json.loads(payload), sequence=sequence) for sequence, payload in rows]
        if rows:
            result["next_before"] = rows[-1][0]
    except (OSError, sqlite3.Error, ValueError):
        result["storage"] = "unavailable"
    return result
