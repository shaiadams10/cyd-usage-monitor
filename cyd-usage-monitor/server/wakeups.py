"""Durable wake-up scheduling and one-attempt guards; only the collector sends.

The ledger deliberately prefers a missed wake-up to a duplicate. A reserved
attempt whose outcome cannot be proved stays paused, including after a crash.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import math
import os
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PROMPT = "say OK"
LEGACY_PROMPT = "say okay"
MAX_PROMPT_LENGTH = 500
MIN_INTERVAL = 5 * 3600 + 120
DAILY_LIMIT = 5
FRESH_SECONDS = 120
SCHEDULE_GRACE = 120
BATCH_ACCOUNT_SECONDS = 180
MAX_BATCH_SECONDS = 15 * 60
PROVIDERS = {"codex", "antigravity", "claude"}


class WakeupError(ValueError):
    """A safe, operator-readable rejection."""


class WakeupHold(WakeupError):
    """Keep the guard while retaining the actual previous failure category."""
    def __init__(self, reason, state="unknown", failure_kind="", attempt_id=""):
        super().__init__(reason)
        self.details = {"state": state, "failure_kind": failure_kind, "blocked_by_attempt_id": attempt_id}


def usage_failure(reason: str) -> bool:
    return bool(re.search(r"usage or rate limit|usage limit|rate.?limit|quota.{0,20}exhausted|429", reason, re.I))


def validate_prompt(value: object) -> str:
    """A bounded plain-text prompt, passed as one CLI argument, never shell code."""
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_PROMPT_LENGTH:
        raise WakeupError("Enter a message between 1 and 500 characters.")
    if any(ord(char) < 32 and char not in "\n\t" or ord(char) == 127 for char in value):
        raise WakeupError("The message contains unsupported control characters.")
    if value.lstrip().startswith(("-", "/")):
        raise WakeupError("Start the message with plain text, rather than a CLI option or slash command.")
    return value


@dataclass(frozen=True)
class WakeupAdapter:
    model: str
    reasoning: str
    send: Callable[[dict, str, str], dict] | None = None
    preflight: Callable[[dict], dict] | None = None
    verified: bool = False
    unavailable_reason: str = "Single-request CLI safety has not been verified."
    catalogue: list[dict] = field(default_factory=list)
    select: Callable[[str, str], "WakeupAdapter"] | None = None
    execution_note: str = ""
    postflight: Callable[[dict], dict] | None = None

    def public(self) -> dict:
        ready = self.verified and callable(self.send) and callable(self.preflight)
        return {"available": ready, "model": self.model, "reasoning": self.reasoning,
                "reason": "" if ready else self.unavailable_reason, "models": self.catalogue,
                "execution_note": self.execution_note}


def _stamp(value: object) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return float(value)
    if isinstance(value, str):
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("A timezone is required")
        return parsed.timestamp()
    raise ValueError("Invalid timestamp")


def _iso(value: float | None) -> str | None:
    return dt.datetime.fromtimestamp(value, dt.timezone.utc).isoformat().replace("+00:00", "Z") if value is not None else None


def _ids(value: object) -> list[str]:
    if not isinstance(value, list) or not 1 <= len(value) <= 50:
        raise WakeupError("Select between one and 50 accounts.")
    if any(not isinstance(item, str) or not re.fullmatch(r"(?:codex|antigravity|claude)-[a-f0-9]{10}", item) for item in value):
        raise WakeupError("Invalid account selection.")
    return sorted(set(value))


def next_occurrence(schedule: dict, after: float) -> float | None:
    """Skip nonexistent DST times; choose the first occurrence of a repeated time."""
    if schedule["kind"] == "once":
        value = _stamp(schedule["run_at"])
        return value if value > after else None
    zone = ZoneInfo(schedule["timezone"])
    local = dt.datetime.fromtimestamp(after, zone)
    hour, minute = map(int, schedule["time"].split(":"))
    for offset in range(9):
        day = local.date() + dt.timedelta(days=offset)
        if day.weekday() not in schedule["weekdays"]:
            continue
        candidate = dt.datetime.combine(day, dt.time(hour, minute), zone).replace(fold=0)
        value = candidate.timestamp()
        # Roundtrip detects the skipped spring-forward hour.
        if dt.datetime.fromtimestamp(value, zone).replace(tzinfo=None) != candidate.replace(tzinfo=None):
            continue
        if value > after:
            return value
    return None


class WakeupStore:
    def __init__(self, data_dir: Path | str, clock: Callable[[], float] = time.time,
                 monotonic: Callable[[], float] = time.monotonic):
        self.directory = Path(data_dir)
        self.path = self.directory / "wakeups.sqlite3"
        self.clock = clock
        self.monotonic = monotonic
        self._last_wall = clock()
        self._last_monotonic = monotonic()

    @contextlib.contextmanager
    def _db(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        # Missing ledger after initialization must never silently clear guards.
        marker = self.directory / ".wakeups-initialized"
        if marker.exists() and not self.path.exists():
            raise WakeupError("Wake-up ledger is missing. Restore it before sending.")
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
        try:
            db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        except sqlite3.Error as error:
            raise WakeupError("Wake-up ledger is unavailable. Sending is stopped.") from error
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS schedules (id TEXT PRIMARY KEY, payload TEXT NOT NULL, next_due REAL, enabled INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL, profile_ids TEXT NOT NULL, source TEXT NOT NULL, created REAL NOT NULL, expires REAL NOT NULL, state TEXT NOT NULL, results TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY, account_ref TEXT NOT NULL, profile_id TEXT NOT NULL, job_id TEXT NOT NULL, created REAL NOT NULL, state TEXT NOT NULL, model TEXT NOT NULL, reason TEXT NOT NULL)")
            db.execute("CREATE INDEX IF NOT EXISTS attempts_account_time ON attempts(account_ref,created)")
            db.execute("CREATE TABLE IF NOT EXISTS pauses (account_ref TEXT PRIMARY KEY, reason TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS failure_notifications (id TEXT PRIMARY KEY, payload TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL)")
            columns = {row[1] for row in db.execute("PRAGMA table_info(jobs)")}
            if "provider_settings" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN provider_settings TEXT NOT NULL DEFAULT '{}'")
            if "prompt" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN prompt TEXT NOT NULL DEFAULT 'say okay'")
            if "run_context" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN run_context TEXT NOT NULL DEFAULT '{}'")
            columns = {row[1] for row in db.execute("PRAGMA table_info(attempts)")}
            if "reasoning" not in columns:
                db.execute("ALTER TABLE attempts ADD COLUMN reasoning TEXT NOT NULL DEFAULT ''")
            db.execute("INSERT OR IGNORE INTO meta VALUES ('enabled', 'false')")
            yield db
            db.commit()
            fd = os.open(marker, os.O_CREAT | os.O_WRONLY, 0o600)
            os.close(fd)
            self.path.chmod(0o600)
            marker.chmod(0o600)
        except sqlite3.Error as error:
            db.rollback()
            raise WakeupError("Wake-up ledger is unavailable. Sending is stopped.") from error
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _get(db, key: str, default=None):
        row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    @staticmethod
    def _set(db, key: str, value):
        db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, json.dumps(value)))

    def _clock_check(self, db, now: float, acknowledge: bool = False) -> bool:
        last = self._get(db, "last_clock", now)
        monotonic = self.monotonic()
        jump = abs((now - self._last_wall) - (monotonic - self._last_monotonic)) > 60
        self._last_wall, self._last_monotonic = now, monotonic
        if not math.isfinite(now) or now < last - 5 or jump:
            self._set(db, "clock_error", "Sending is on a safety hold because the server clock changed. Check the clock, then stop and enable wake-ups to resume. Your saved enabled setting has not changed.")
            return False
        self._set(db, "last_clock", max(now, last))
        return acknowledge or not self._get(db, "clock_error")

    def set_capabilities(self, adapters: dict[str, WakeupAdapter]) -> None:
        with self._db() as db:
            self._set(db, "capabilities", {key: value.public() for key, value in adapters.items() if key in PROVIDERS})
            self._set(db, "capabilities_at", self.clock())

    def set_enabled(self, enabled: bool) -> dict:
        if not isinstance(enabled, bool):
            raise WakeupError("Enabled must be true or false.")
        with self._db() as db:
            now = self.clock()
            if enabled and not self._clock_check(db, now, acknowledge=True):
                return {"enabled": self._get(db, "enabled", False), "error": self._get(db, "clock_error")}
            self._set(db, "enabled", enabled)
            if enabled:
                self._set(db, "clock_error", None)
            else:
                # Master stop cancels already queued manual and scheduled jobs.
                db.execute("UPDATE jobs SET state='cancelled' WHERE state IN ('queued','processing')")
        return {"enabled": enabled}

    def validate_settings(self, profile_ids: list[str], settings: object) -> dict:
        providers = {profile_id.split("-", 1)[0] for profile_id in profile_ids}
        return self._validate_provider_settings(providers, settings)

    def _validate_provider_settings(self, providers: set[str], settings: object) -> dict:
        if not isinstance(settings, dict) or set(settings) != providers:
            raise WakeupError("Choose a model and reasoning level for every selected provider.")
        with self._db() as db:
            capabilities = self._get(db, "capabilities", {})
            age = self.clock() - self._get(db, "capabilities_at", 0)
        if not 0 <= age <= 120:
            raise WakeupError("Model choices are stale. Wait for the collector and refresh.")
        selected = {}
        for provider in providers:
            choice = settings[provider]
            if not isinstance(choice, dict) or set(choice) != {"model", "reasoning"}:
                raise WakeupError("Choose a model and reasoning level for every selected provider.")
            model, reasoning = choice.get("model"), choice.get("reasoning")
            if not isinstance(model, str) or not isinstance(reasoning, str):
                raise WakeupError("Invalid model or reasoning selection.")
            option = next((item for item in capabilities.get(provider, {}).get("models", []) if item.get("id") == model), None)
            if not option or reasoning not in option.get("reasoning_levels", []):
                raise WakeupError(f"The selected {provider} model or reasoning level is unavailable. Refresh the model list.")
            selected[provider] = {"model": model, "reasoning": reasoning}
        return selected

    def save_defaults(self, settings: object) -> dict:
        if not isinstance(settings, dict) or not settings or not set(settings) <= PROVIDERS:
            raise WakeupError("Choose a supported provider and its default model and reasoning.")
        selected = self._validate_provider_settings(set(settings), settings)
        with self._db() as db:
            defaults = self._get(db, "provider_defaults", {})
            defaults.update(selected)
            self._set(db, "provider_defaults", defaults)
        return {"defaults": defaults}

    def clear_default(self, provider: str) -> dict:
        if not isinstance(provider, str) or provider not in PROVIDERS:
            raise WakeupError("Choose a supported provider.")
        with self._db() as db:
            defaults = self._get(db, "provider_defaults", {})
            defaults.pop(provider, None)
            self._set(db, "provider_defaults", defaults)
        return {"defaults": defaults}

    def save_schedule(self, payload: dict) -> dict:
        now = self.clock()
        kind = payload.get("kind")
        if kind not in {"once", "weekly"}:
            raise WakeupError("Choose one-time or repeating scheduling.")
        label = str(payload.get("label", "Wake-up")).strip()[:80] or "Wake-up"
        schedule = {"label": label, "profile_ids": _ids(payload.get("profile_ids")), "kind": kind}
        schedule["provider_settings"] = self.validate_settings(schedule["profile_ids"], payload.get("provider_settings"))
        schedule["prompt"] = validate_prompt(payload.get("prompt", PROMPT))
        zone = payload.get("timezone", "UTC")
        try:
            if not isinstance(zone, str) or len(zone) > 80:
                raise ValueError()
            ZoneInfo(zone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise WakeupError("Choose a valid IANA timezone, such as America/New_York.") from error
        schedule["timezone"] = zone
        if kind == "once":
            try:
                if payload.get("local_datetime"):
                    local = dt.datetime.fromisoformat(payload["local_datetime"])
                    if local.tzinfo is not None:
                        raise ValueError("Local time must not include an offset")
                    candidate = local.replace(tzinfo=ZoneInfo(zone), fold=0)
                    run_at = candidate.timestamp()
                    if dt.datetime.fromtimestamp(run_at, ZoneInfo(zone)).replace(tzinfo=None) != local:
                        raise ValueError("This time does not exist due to daylight saving")
                else:
                    run_at = _stamp(payload.get("run_at"))
            except (ValueError, TypeError, OverflowError) as error:
                raise WakeupError("Choose a date and time with a timezone.") from error
            if not now + 5 <= run_at <= now + 366 * 86400:
                raise WakeupError("Choose a time in the next year, at least five seconds from now.")
            schedule["run_at"] = _iso(run_at)
        else:
            wall_time = payload.get("time", "")
            weekdays = payload.get("weekdays", list(range(7)))
            if not isinstance(wall_time, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", wall_time):
                raise WakeupError("Choose a valid time.")
            if not isinstance(weekdays, list) or not weekdays or any(type(day) is not int or not 0 <= day <= 6 for day in weekdays):
                raise WakeupError("Select at least one day.")
            schedule.update(time=wall_time, weekdays=sorted(set(weekdays)))
        identifier = payload.get("id") or uuid.uuid4().hex
        if not isinstance(identifier, str) or not re.fullmatch(r"[a-f0-9]{32}", identifier):
            raise WakeupError("Invalid schedule.")
        enabled = payload.get("enabled", True)
        if type(enabled) is not bool:
            raise WakeupError("Enabled must be true or false.")
        next_due = next_occurrence(schedule, now)
        with self._db() as db:
            # Editing an armed schedule invalidates jobs created from its old
            # account/time selection, even while their preflight is running.
            db.execute("UPDATE jobs SET state='cancelled' WHERE source=? AND state IN ('queued','processing')", ("schedule:" + identifier,))
            db.execute("INSERT OR REPLACE INTO schedules VALUES (?,?,?,?)", (identifier, json.dumps(schedule), next_due, int(enabled)))
        return dict(schedule, id=identifier, enabled=enabled, next_due=_iso(next_due))

    def delete_schedule(self, identifier: str) -> dict:
        if not isinstance(identifier, str):
            raise WakeupError("Invalid schedule.")
        with self._db() as db:
            db.execute("DELETE FROM schedules WHERE id=?", (identifier,))
            db.execute("UPDATE jobs SET state='cancelled' WHERE source=? AND state IN ('queued','processing')", ("schedule:" + identifier,))
        return {"deleted": True}

    def toggle_schedule(self, identifier: str, enabled: bool) -> dict:
        if not isinstance(identifier, str) or type(enabled) is not bool:
            raise WakeupError("Invalid schedule.")
        with self._db() as db:
            row = db.execute("SELECT payload FROM schedules WHERE id=?", (identifier,)).fetchone()
            if not row:
                raise WakeupError("This schedule no longer exists.")
            if enabled and not json.loads(row[0]).get("provider_settings"):
                raise WakeupError("Edit this schedule and choose models and reasoning before resuming.")
            next_due = next_occurrence(json.loads(row[0]), self.clock())
            if enabled and next_due is None:
                raise WakeupError("This one-time schedule has already passed. Create a new schedule.")
            db.execute("UPDATE schedules SET enabled=?,next_due=? WHERE id=?", (int(enabled), next_due, identifier))
            if not enabled:
                db.execute("UPDATE jobs SET state='cancelled' WHERE source=? AND state IN ('queued','processing')", ("schedule:" + identifier,))
        return {"enabled": enabled}

    def enqueue_now(self, profile_ids: list[str], idempotency_key: str, provider_settings: dict | None = None, prompt: str = PROMPT) -> dict:
        ids = _ids(profile_ids)
        prompt = validate_prompt(prompt)
        if not isinstance(idempotency_key, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{16,100}", idempotency_key):
            raise WakeupError("A valid request ID is required. Refresh and try again.")
        # An accepted idempotent request remains readable even if discovery is
        # temporarily down. It must never create a different model selection.
        with self._db() as db:
            existing = db.execute("SELECT * FROM jobs WHERE request_key=?", ("manual:" + idempotency_key,)).fetchone()
            if existing:
                if json.loads(existing["profile_ids"]) != ids or json.loads(existing["provider_settings"]) != provider_settings or existing["prompt"] != prompt:
                    raise WakeupError("This request ID was already used for a different selection.")
                return {"job_id": existing["id"], "state": existing["state"], "duplicate": True}
        settings = self.validate_settings(ids, provider_settings)
        now = self.clock()
        with self._db() as db:
            if not self._get(db, "enabled", False):
                raise WakeupError("Wake-ups are stopped. Enable them first.")
            existing = db.execute("SELECT * FROM jobs WHERE request_key=?", ("manual:" + idempotency_key,)).fetchone()
            if existing:
                if json.loads(existing["profile_ids"]) != ids or json.loads(existing["provider_settings"]) != settings or existing["prompt"] != prompt:
                    raise WakeupError("This request ID was already used for a different selection.")
                return {"job_id": existing["id"], "state": existing["state"], "duplicate": True}
            identifier = uuid.uuid4().hex
            db.execute("INSERT INTO jobs (id,request_key,profile_ids,source,created,expires,state,results,provider_settings,prompt) VALUES (?,?,?,?,?,?,?,?,?,?)", (identifier, "manual:" + idempotency_key, json.dumps(ids), "manual", now, now + SCHEDULE_GRACE, "queued", "[]", json.dumps(settings), prompt))
        return {"job_id": identifier, "state": "queued", "duplicate": False}

    def resume_account(self, account_ref: str) -> dict:
        """Acknowledge uncertainty only after the minimum interval has passed."""
        now = self.clock()
        with self._db() as db:
            latest = db.execute("SELECT MAX(created) FROM attempts WHERE account_ref=?", (account_ref,)).fetchone()[0]
            if latest is None or now < latest + MIN_INTERVAL:
                raise WakeupError("Wait until the account's safety interval ends before resolving an uncertain attempt.")
            db.execute("DELETE FROM pauses WHERE account_ref=?", (account_ref,))
            db.execute("UPDATE attempts SET state='acknowledged' WHERE account_ref=? AND state IN ('reserved','unknown','failed')", (account_ref,))
        return {"resumed": True}

    def apply_action(self, payload: dict, profiles: list[dict]) -> dict:
        action = payload.get("action")
        if action in {"now", "save_schedule"}:
            ids = _ids(payload.get("profile_ids"))
            known = {profile["id"] for profile in profiles if profile.get("enabled", True)}
            if not set(ids) <= known:
                raise WakeupError("One of the selected accounts is unavailable. Refresh the list.")
        if action == "enabled":
            return self.set_enabled(payload.get("enabled"))
        if action == "save_defaults":
            return self.save_defaults(payload.get("provider_settings"))
        if action == "clear_default":
            return self.clear_default(payload.get("provider"))
        if action == "now":
            return self.enqueue_now(payload["profile_ids"], payload.get("idempotency_key"), payload.get("provider_settings"), payload.get("prompt", PROMPT))
        if action == "save_schedule":
            return self.save_schedule(payload)
        if action == "delete_schedule":
            return self.delete_schedule(payload.get("id"))
        if action == "toggle_schedule":
            return self.toggle_schedule(payload.get("id"), payload.get("enabled"))
        if action == "resume_account":
            return self.resume_account(payload.get("account_ref"))
        raise WakeupError("Unknown wake-up action.")

    @staticmethod
    def _reading(reading: dict, provider: str, now: float, *, require_weekly: bool = True) -> tuple[str, str]:
        identity = reading.get("account_identity")
        if reading.get("identity_verified") is not True or not isinstance(identity, str) or not identity.strip():
            raise WakeupError("Account identity could not be verified. Reconnect this account.")
        age = now - _stamp(reading.get("collected_at"))
        if not 0 <= age <= FRESH_SECONDS:
            raise WakeupError("Usage is stale. Refresh the account before sending.")
        if require_weekly:
            if reading.get("quota_valid") is not True:
                raise WakeupError("Fresh quota data is unavailable. Scheduled sending was skipped.")
            quota_age = now - _stamp(reading.get("quota_collected_at", reading.get("collected_at")))
            if not 0 <= quota_age <= FRESH_SECONDS:
                raise WakeupError("Usage is stale. Refresh the account before sending.")
            weekly = reading.get("weekly_remaining_pct")
            if type(weekly) not in (int, float) or not math.isfinite(weekly) or not 0 < weekly <= 100:
                raise WakeupError("Weekly quota is exhausted." if type(weekly) in (int, float) and weekly == 0 else "Weekly quota is unavailable. Scheduled sending was skipped.")
        reference = hashlib.sha256((provider + ":" + identity.strip().casefold()).encode()).hexdigest()[:32]
        return reference, ""

    def _reserve(self, profile: dict, adapter: WakeupAdapter, reading: dict, job_id: str) -> str:
        now = self.clock()
        identifier = uuid.uuid4().hex
        with self._db() as db:
            if not self._clock_check(db, now):
                return ""
            if not self._get(db, "enabled", False):
                raise WakeupError("Wake-ups were stopped.")
            job = db.execute("SELECT state,source,expires FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not job or job["state"] != "processing" or now > job["expires"]:
                raise WakeupError("This request was cancelled or expired.")
            # Manual Send now is an explicit request for one prompt, regardless
            # of quota-window state. All durable account/identity guards remain.
            reference, _ = self._reading(reading, profile["provider"], now, require_weekly=job["source"] != "manual")
            if job["source"].startswith("schedule:"):
                schedule = db.execute("SELECT enabled FROM schedules WHERE id=?", (job["source"].removeprefix("schedule:"),)).fetchone()
                if not schedule:
                    raise WakeupError("This schedule was deleted.")
                if not schedule["enabled"]:
                    raise WakeupError("This schedule was paused.")
            if db.execute("SELECT 1 FROM pauses WHERE account_ref=?", (reference,)).fetchone():
                previous = db.execute("SELECT id,state,reason FROM attempts WHERE account_ref=? AND state IN ('reserved','unknown','failed') ORDER BY CASE WHEN state IN ('reserved','unknown') THEN 0 ELSE 1 END,created DESC LIMIT 1", (reference,)).fetchone()
                if previous and previous["state"] == "failed":
                    limited = usage_failure(previous["reason"])
                    reason = "Not sent: a previous request was rejected for usage or rate limits. Account remains paused for review." if limited else "Not sent: account paused after a confirmed failure. Previous failure: " + previous["reason"][:300]
                    raise WakeupHold(reason, "failed", "usage_limit" if limited else "previous_failure", previous["id"])
                raise WakeupHold("Not sent: account paused after an unconfirmed attempt. Review history before resuming.", attempt_id=previous["id"] if previous else "")
            if db.execute("SELECT 1 FROM attempts WHERE account_ref=? AND state IN ('reserved','unknown')", (reference,)).fetchone():
                raise WakeupError("An earlier attempt has an uncertain outcome. Review history before resuming.")
            latest = db.execute("SELECT MAX(created) FROM attempts WHERE account_ref=?", (reference,)).fetchone()[0]
            if latest is not None and now < latest + MIN_INTERVAL:
                raise WakeupError("Already attempted within the five-hour safety interval.")
            count = db.execute("SELECT COUNT(*) FROM attempts WHERE account_ref=? AND created>?", (reference, now - 86400)).fetchone()[0]
            if count >= DAILY_LIMIT:
                raise WakeupError("The daily limit of five attempts has been reached.")
            db.execute("INSERT INTO attempts (id,account_ref,profile_id,job_id,created,state,model,reason,reasoning) VALUES (?,?,?,?,?,?,?,?,?)", (identifier, reference, profile["id"], job_id, now, "reserved", adapter.model, "Reserved before CLI launch", adapter.reasoning))
        return identifier

    def _finish(self, identifier: str, state: str, reason: str):
        with self._db() as db:
            row = db.execute("SELECT account_ref FROM attempts WHERE id=?", (identifier,)).fetchone()
            db.execute("UPDATE attempts SET state=?,reason=? WHERE id=?", (state, reason, identifier))
            if state in {"unknown", "failed"}:
                db.execute("INSERT OR REPLACE INTO pauses VALUES (?,?)", (row[0], reason))

    def claim_notifications(self, limit: int = 20) -> list[dict]:
        """Durably claim before external delivery; uncertain notifications never resend."""
        with self._db() as db:
            rows = db.execute("SELECT * FROM failure_notifications WHERE state='pending' ORDER BY created LIMIT ?", (max(1, min(limit, 100)),)).fetchall()
            for row in rows:
                db.execute("UPDATE failure_notifications SET state='claimed' WHERE id=?", (row["id"],))
            return [dict(json.loads(row["payload"]), notification_id=row["id"]) for row in rows]

    def finish_notification(self, identifier: str, delivered: bool) -> None:
        with self._db() as db:
            db.execute("UPDATE failure_notifications SET state=? WHERE id=? AND state='claimed'", ("delivered" if delivered else "delivery_failed", identifier))

    @staticmethod
    def _notify_summary(db, job_id: str, results: list[dict], profiles: list[dict], now: float):
        """One durable run receipt; never include the operator's prompt."""
        identifier = hashlib.sha256(("run:" + job_id).encode()).hexdigest()[:32]
        job = db.execute("SELECT source,provider_settings,run_context,created FROM jobs WHERE id=?", (job_id,)).fetchone()
        lookup = {profile["id"]: profile for profile in profiles}
        settings = json.loads(job["provider_settings"])
        accounts = []
        for result in results:
            profile = lookup.get(result["profile_id"], {})
            provider = profile.get("provider") or result["profile_id"].split("-", 1)[0]
            choice = settings.get(provider, {})
            accounts.append(dict(result, provider=provider,
                label=result.get("label") or profile.get("label") or profile.get("last_account_name") or result["profile_id"],
                model=result.get("model") or choice.get("model", ""), reasoning=result.get("reasoning") or choice.get("reasoning", "")))
        payload = {"kind": "run_summary", "job_id": job_id, "source": job["source"],
                   "created_at": _iso(now), "requested_at": _iso(job["created"]),
                   "run_context": json.loads(job["run_context"]), "results": accounts}
        db.execute("INSERT OR IGNORE INTO failure_notifications VALUES (?,?,?,?)", (identifier, json.dumps(payload), "pending", now))

    def _close_interrupted_jobs(self, db, profiles: list[dict], now: float):
        """Close expired work from a crashed worker without ever reclaiming it."""
        rows = db.execute("SELECT * FROM jobs WHERE (state='queued' AND expires<?) OR (state IN ('processing','cancelled') AND expires<?)", (now, now - 60)).fetchall()
        for job in rows:
            identifier = hashlib.sha256(("run:" + job["id"]).encode()).hexdigest()[:32]
            if db.execute("SELECT 1 FROM failure_notifications WHERE id=?", (identifier,)).fetchone():
                continue
            results = {result["profile_id"]: result for result in json.loads(job["results"])}
            for profile_id in json.loads(job["profile_ids"]):
                if profile_id in results:
                    continue
                attempt = db.execute("SELECT * FROM attempts WHERE job_id=? AND profile_id=? ORDER BY created DESC LIMIT 1", (job["id"], profile_id)).fetchone()
                if attempt:
                    state = attempt["state"] if attempt["state"] in {"sent", "failed"} else "unknown"
                    reason = attempt["reason"] if state != "unknown" else "The collector stopped before confirming the outcome. No prompt will be retried."
                    if state == "unknown":
                        db.execute("UPDATE attempts SET state='unknown',reason=? WHERE id=?", (reason, attempt["id"]))
                        db.execute("INSERT OR REPLACE INTO pauses VALUES (?,?)", (attempt["account_ref"], reason))
                    results[profile_id] = {"profile_id": profile_id, "state": state, "reason": reason,
                        "attempt_id": attempt["id"], "model": attempt["model"], "reasoning": attempt["reasoning"]}
                else:
                    results[profile_id] = {"profile_id": profile_id, "state": "skipped",
                        "reason": "The request was cancelled or expired before this account was sent a prompt. No late send will be made."}
            result_list = list(results.values())
            for result in result_list:
                for field in ("reset_status", "quota_status"):
                    if result.get(field) == "checking": result[field] = "unavailable"
            state = "expired" if job["state"] == "queued" else "interrupted"
            db.execute("UPDATE jobs SET state=?,results=? WHERE id=?", (state, json.dumps(result_list), job["id"]))
            if job["source"].startswith("schedule:") and any(result["state"] in {"failed", "unknown"} for result in result_list):
                db.execute("UPDATE schedules SET enabled=0 WHERE id=?", (job["source"].removeprefix("schedule:"),))
            self._notify_summary(db, job["id"], result_list, profiles, now)

    def _reset_after_send(self, adapter, profile, reading, deadline):
        """Read-only verification; its failure must never change a send outcome."""
        try:
            if self.clock() + 65 >= deadline:
                return {"reset_status": "unavailable"}
            after = adapter.postflight(profile)
            age = self.clock() - _stamp(after.get("collected_at"))
            text = str(after.get("window_reset_text") or "")
            usable_text = bool(re.search(r"\b\d{1,2}:\d{2}\b|\b\d{1,2}\s*[ap]m\b", text, re.I)) and not any(word in text.casefold() for word in ("unavailable", "not reported", "quota available", "limit reached"))
            reset_at = after.get("window_reset_at")
            usable_epoch = isinstance(reset_at, (int, float)) and not isinstance(reset_at, bool) and math.isfinite(reset_at) and reset_at > self.clock()
            if (after.get("identity_verified") is True and after.get("quota_valid") is not False and after.get("window_state") in {"active", "unknown"} and 0 <= age <= FRESH_SECONDS
                    and after.get("account_identity", "").strip().casefold() == reading["account_identity"].strip().casefold()
                    and (usable_epoch or usable_text)):
                source = "confirmed" if after.get("window_state") == "active" else "reported"
                return {"reset_at": reset_at if usable_epoch else None, "reset_text": text,
                        "reset_timezone": after.get("window_reset_timezone", "UTC"), "reset_estimated": False,
                        "reset_source": source, "reset_status": source}
        except Exception:
            pass  # No inference retry, and no false send failure on a quota-read error.
        return {"reset_status": "unavailable"}

    def _save_progress(self, job_id, results):
        with self._db() as db:
            db.execute("UPDATE jobs SET results=? WHERE id=? AND state IN ('processing','cancelled')", (json.dumps(results), job_id))

    def _quota_after_failure(self, adapter, profile, reading, deadline):
        """Attribute an exhausted window with fresh panels, never by reset-time guesses."""
        reset = {}
        def details(value):
            if (value.get("quota_valid") is not True or value.get("identity_verified") is not True
                    or value.get("account_identity", "").strip().casefold() != reading["account_identity"].strip().casefold()):
                return []
            try: age = self.clock() - _stamp(value.get("quota_collected_at", value.get("collected_at")))
            except (ValueError, TypeError): return []
            if not 0 <= age <= FRESH_SECONDS: return []
            text = str(value.get("window_reset_text") or "")
            epoch = value.get("window_reset_at")
            usable_epoch = type(epoch) in (int, float) and math.isfinite(epoch) and epoch > self.clock()
            usable_text = re.search(r"\b\d{1,2}:\d{2}\b|\b\d{1,2}\s*[ap]m\b", text, re.I) and not re.search(r"unavailable|not reported|quota available|limit reached", text, re.I)
            if usable_epoch or usable_text:
                reset.update(reset_at=epoch if usable_epoch else None, reset_text=text,
                             reset_timezone=value.get("window_reset_timezone", "UTC"), reset_source="reported", reset_estimated=False)
            return [dict(item, reset_timezone=value.get("window_reset_timezone", "UTC"), reset_source="reported")
                    for item in value.get("quota_windows", []) if item.get("window") in {"five_hour", "weekly"}
                    and type(item.get("remaining_pct")) in (int, float) and item["remaining_pct"] == 0]
        try:
            limits = details(reading)
            if not limits and callable(adapter.postflight) and self.clock() + 65 < deadline:
                limits = details(adapter.postflight(profile))
            return dict(reset, quota_limits=limits, quota_status="confirmed" if limits else "unavailable")
        except Exception:
            return dict(reset, quota_limits=[], quota_status="unavailable")

    def process_due(self, profiles: list[dict], adapters: dict[str, WakeupAdapter]) -> list[dict]:
        """Call on a dedicated collector thread. Never call from HTTP handlers."""
        self.set_capabilities(adapters)
        now = self.clock()
        with self._db() as db:
            if not self._clock_check(db, now):
                return []
            self._close_interrupted_jobs(db, profiles, now)
            if not self._get(db, "enabled", False):
                return []
            for row in db.execute("SELECT * FROM schedules WHERE enabled=1", ()).fetchall():
                schedule = json.loads(row["payload"])
                due = row["next_due"]
                if not schedule.get("provider_settings"):
                    schedule["settings_error"] = "Choose models and reasoning before resuming this schedule."
                    db.execute("UPDATE schedules SET enabled=0,payload=? WHERE id=?", (json.dumps(schedule), row["id"]))
                    continue
                if due is None or due > now:
                    continue
                if now - due <= SCHEDULE_GRACE:
                    context = {"schedule_label": schedule["label"], "timezone": schedule["timezone"], "scheduled_for": _iso(due)}
                    db.execute("INSERT OR IGNORE INTO jobs (id,request_key,profile_ids,source,created,expires,state,results,provider_settings,prompt,run_context) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (uuid.uuid4().hex, f"schedule:{row['id']}:{due}", json.dumps(schedule["profile_ids"]), "schedule:" + row["id"], now, due + SCHEDULE_GRACE, "queued", "[]", json.dumps(schedule["provider_settings"]), validate_prompt(schedule.get("prompt", LEGACY_PROMPT)), json.dumps(context)))
                # Move directly to the next future occurrence. No catch-up sends.
                next_due = next_occurrence(schedule, now)
                db.execute("UPDATE schedules SET next_due=? WHERE id=?", (next_due, row["id"]))
            db.execute("UPDATE jobs SET state='expired' WHERE state='queued' AND expires<?", (now,))
            # Claim only work we can begin now. Keep the two-minute queued
            # deadline for missed runs, then allow a bounded serial batch to
            # finish fresh checks for every selected account.
            jobs = db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created LIMIT 1").fetchall()
            claimed = []
            for row in jobs:
                duration = min(MAX_BATCH_SECONDS, max(SCHEDULE_GRACE,
                    len(json.loads(row["profile_ids"])) * BATCH_ACCOUNT_SECONDS))
                deadline = now + duration
                db.execute("UPDATE jobs SET state='processing',expires=? WHERE id=?", (deadline, row["id"]))
                claimed.append(dict(row, expires=deadline))
            jobs = claimed
        available = {profile["id"]: profile for profile in profiles if profile.get("enabled", True)}
        completed = []
        for job in jobs:
            results = []
            pending_resets = {}
            # Only quota reads overlap. Prompt submission remains serial and guarded.
            with ThreadPoolExecutor(max_workers=3, thread_name_prefix="wakeup-reset") as reset_pool:
                for profile_id in json.loads(job["profile_ids"]):
                    self.set_capabilities(adapters)
                    profile = available.get(profile_id)
                    adapter = adapters.get(profile.get("provider")) if profile else None
                    result = {"profile_id": profile_id, "state": "failed", "reason": "Account is unavailable."}
                    if profile:
                        result["label"] = profile.get("label") or profile.get("last_account_name") or profile_id
                    attempt = ""
                    reading = None
                    try:
                        if not profile:
                            raise WakeupError(result["reason"])
                        if not adapter or not adapter.public()["available"]:
                            result["state"] = "failed"
                            raise WakeupError(adapter.unavailable_reason if adapter else "Single-request CLI safety has not been verified.")
                        choices = json.loads(job["provider_settings"])
                        choice = choices.get(profile["provider"], {})
                        option = next((item for item in adapter.catalogue if item.get("id") == choice.get("model")), None)
                        if not option or choice.get("reasoning") not in option.get("reasoning_levels", []):
                            result["state"] = "failed"
                            raise WakeupError("The requested model or reasoning is unavailable. No fallback or retry was used.")
                        if callable(adapter.select):
                            adapter = adapter.select(choice["model"], choice["reasoning"])
                        elif (adapter.model, adapter.reasoning) != (choice["model"], choice["reasoning"]):
                            result["state"] = "failed"
                            raise WakeupError("This CLI cannot apply the requested model and reasoning. No prompt was sent.")
                        if (adapter.model, adapter.reasoning) != (choice["model"], choice["reasoning"]) or not adapter.public()["available"]:
                            result["state"] = "failed"
                            raise WakeupError("The requested model settings could not be applied. No fallback was used.")
                        profile = dict(profile, wakeup_model=choice["model"], wakeup_reasoning=choice["reasoning"], wakeup_source=job["source"])
                        result.update(model=choice["model"], reasoning=choice["reasoning"])
                        if self.clock() > job["expires"]:
                            result["state"] = "skipped"
                            raise WakeupError("The request expired before this account could be checked.")
                        reading = adapter.preflight(profile)
                        # Keep the bounded normalized facts behind each decision,
                        # without raw panels, credentials or account identities.
                        result["eligibility"] = {key: reading.get(key) for key in (
                            "collected_at", "quota_collected_at", "quota_valid",
                            "weekly_remaining_pct", "five_hour_remaining_pct", "window_state")}
                        # Configuration/model/auth failures above are actionable.
                        # Normal quota eligibility and explicit cancellation below
                        # remain visible skips rather than repeated failure alerts.
                        result["state"] = "skipped"
                        # A lengthy refresh must not turn a stale queued job into a send.
                        if self.clock() > job["expires"]:
                            raise WakeupError("The request expired during the usage refresh.")
                        attempt = self._reserve(profile, adapter, reading, job["id"])
                        if not attempt:
                            raise WakeupError("Clock changed. Wake-ups have been stopped.")
                        outcome = adapter.send(dict(profile, wakeup_account_identity=reading["account_identity"]), validate_prompt(job["prompt"]), attempt)
                        sent_at = self.clock()
                        state = outcome.get("state") if isinstance(outcome, dict) and outcome.get("state") in {"sent", "failed"} else "unknown"
                        reason = "One prompt completed." if state == "sent" else "The CLI outcome is uncertain. No automatic retry will be made."
                        if state == "sent" and reading.get("window_state") != "idle":
                            reason = "One prompt completed as requested. A new five-hour window was not assumed."
                        if state != "sent" and isinstance(outcome, dict):
                            reason = str(outcome.get("reason") or ("The CLI rejected the prompt. No automatic retry will be made." if state == "failed" else reason))[:500]
                        self._finish(attempt, state, reason)
                        result.update(state=state, reason=reason, attempt_id=attempt)
                        if state == "failed" and usage_failure(reason):
                            result.update(failure_kind="usage_limit", quota_status="checking")
                        if state == "sent":
                            # A separate read-only quota check, never another prompt.
                            if reading.get("window_state") == "idle":
                                result.update(reset_at=sent_at + 5 * 3600, reset_estimated=True)
                            elif reading.get("window_state") == "active":
                                result.update(reset_at=reading.get("window_reset_at"), reset_text=reading.get("window_reset_text", ""),
                                              reset_timezone=reading.get("window_reset_timezone", "UTC"), reset_estimated=False)
                            if callable(adapter.postflight) and self.clock() + 65 < job["expires"]:
                                result["reset_status"] = "checking"
                    except WakeupError as error:
                        if attempt:
                            self._finish(attempt, "unknown", "The CLI outcome is uncertain. No automatic retry will be made.")
                            result.update(state="unknown", reason="The CLI outcome is uncertain. No automatic retry will be made.", attempt_id=attempt)
                        else:
                            result["reason"] = str(error)
                            if isinstance(error, WakeupHold):
                                result.update(error.details)
                                if result.get("failure_kind") == "usage_limit": result["quota_status"] = "checking"
                            if result["state"] == "skipped" and any(token in str(error).casefold() for token in ("identity", "stale", "invalid", "reconnect")):
                                result["state"] = "failed"
                    except Exception:
                        # Raw subprocess errors may contain private paths or terminal content.
                        if attempt:
                            self._finish(attempt, "unknown", "The CLI outcome is uncertain. No automatic retry will be made.")
                            result.update(state="unknown", reason="The CLI outcome is uncertain. No automatic retry will be made.", attempt_id=attempt)
                        else:
                            result.update(state="failed", reason="The fresh usage check failed. No prompt was sent.")
                    results.append(result)
                    if result["state"] == "skipped" and isinstance(reading, dict):
                        # Eligibility skips deserve the same exhausted-window
                        # explanation as rejections. Reuse this panel only.
                        result.update(self._quota_after_failure(adapter, profile, reading, 0))
                    self._save_progress(job["id"], results)
                    if result.get("reset_status") == "checking":
                        pending_resets[reset_pool.submit(self._reset_after_send, adapter, profile, reading, job["expires"])] = result
                    elif result.get("quota_status") == "checking":
                        pending_resets[reset_pool.submit(self._quota_after_failure, adapter, profile, reading, job["expires"])] = result
                    for future, saved in list(pending_resets.items()):
                        if future.done():
                            saved.update(future.result())
                            del pending_resets[future]
                            self._save_progress(job["id"], results)
                for future in as_completed(pending_resets):
                    pending_resets[future].update(future.result())
                    self._save_progress(job["id"], results)
            with self._db() as db:
                updated = db.execute("UPDATE jobs SET state='complete',results=? WHERE id=? AND state IN ('processing','cancelled')", (json.dumps(results), job["id"]))
                if not updated.rowcount:
                    continue
                self._notify_summary(db, job["id"], results, profiles, self.clock())
                if job["source"].startswith("schedule:"):
                    db.execute("UPDATE schedules SET enabled=0 WHERE id=? AND next_due IS NULL", (job["source"].removeprefix("schedule:"),))
                    if any(result["state"] in {"failed", "unknown"} for result in results):
                        identifier = job["source"].removeprefix("schedule:")
                        row = db.execute("SELECT payload FROM schedules WHERE id=?", (identifier,)).fetchone()
                        if row:
                            payload = json.loads(row[0])
                            payload["last_error"] = "Paused after a failed or uncertain account result. Review activity before resuming."
                            db.execute("UPDATE schedules SET enabled=0,payload=? WHERE id=?", (json.dumps(payload), identifier))
            completed.append({"job_id": job["id"], "results": results})
        return completed

    def status(self, profiles: list[dict], snapshots: dict | None = None) -> dict:
        with self._db() as db:
            now = self.clock()
            capabilities = self._get(db, "capabilities", {})
            if now - self._get(db, "capabilities_at", 0) > 120:
                capabilities = {key: dict(value, available=False, reason="Collector capabilities are stale. Wait for the collector.") for key, value in capabilities.items()}
            schedules = [dict(json.loads(row["payload"]), id=row["id"], enabled=bool(row["enabled"]), next_due=_iso(row["next_due"])) for row in db.execute("SELECT * FROM schedules ORDER BY next_due IS NULL,next_due")]
            attempts = [dict(row) for row in db.execute("SELECT * FROM attempts ORDER BY created DESC LIMIT 100")]
            pauses = {row["account_ref"]: row["reason"] for row in db.execute("SELECT * FROM pauses")}
            processing = {row["id"] for row in db.execute("SELECT id FROM jobs WHERE state IN ('processing','cancelled') AND expires>=?", (now,))}
            for attempt in attempts:
                attempt["created_at"] = _iso(attempt.pop("created"))
                attempt["next_eligible_at"] = _iso(_stamp(attempt["created_at"]) + MIN_INTERVAL)
                attempt["in_progress"] = attempt["state"] == "reserved" and attempt["job_id"] in processing
                attempt["paused"] = attempt["account_ref"] in pauses or attempt["state"] in {"unknown", "failed"} or (attempt["state"] == "reserved" and not attempt["in_progress"])
            jobs = [dict(row) for row in db.execute("SELECT id,source,created,state,results,provider_settings,prompt,profile_ids FROM jobs ORDER BY created DESC LIMIT 50")]
            notifications = [dict(json.loads(row["payload"]), notification_id=row["id"], delivery_state=row["state"]) for row in db.execute("SELECT * FROM failure_notifications ORDER BY created DESC LIMIT 50")]
            for job in jobs:
                job["created_at"] = _iso(job.pop("created"))
                job["results"] = json.loads(job["results"])
                job["provider_settings"] = json.loads(job["provider_settings"])
                job["profile_ids"] = json.loads(job["profile_ids"])
            account_list = []
            for profile in profiles:
                if profile.get("provider") not in PROVIDERS:
                    continue
                cap = capabilities.get(profile["provider"], {"available": False, "reason": "Waiting for collector capability checks.", "model": "Not verified", "reasoning": "Not verified"})
                snapshot = (snapshots or {}).get(profile["id"], {})
                account_list.append({"id": profile["id"], "label": profile.get("label") or profile.get("last_account_name") or snapshot.get("account_name") or profile["id"], "provider": profile["provider"], "enabled": profile.get("enabled", True), "capability": cap})
            return {"enabled": self._get(db, "enabled", False), "clock_error": self._get(db, "clock_error"), "prompt": PROMPT,
                    "defaults": self._get(db, "provider_defaults", {}),
                    "accounts": account_list, "schedules": schedules, "attempts": attempts, "jobs": jobs, "notifications": notifications,
                    "limits": {"minimum_interval_seconds": MIN_INTERVAL, "maximum_attempts_per_day": DAILY_LIMIT}, "server_time": _iso(now)}
