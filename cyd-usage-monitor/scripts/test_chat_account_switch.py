import datetime as dt
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import struct
import sqlite3
import os
from contextlib import closing
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("chat_switch", Path(__file__).with_name("chat-account-switch.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
watch_spec = importlib.util.spec_from_file_location("watcher", Path(__file__).with_name("watch-antigravity-messages.py"))
watcher = importlib.util.module_from_spec(watch_spec)
watch_spec.loader.exec_module(watcher)
CODEX_A = "codex-aaaaaaaaaa"
CODEX_B = "codex-bbbbbbbbbb"
AG = "antigravity-aaaaaaaaaa"


class SwitchingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "state.sqlite"
        self.config = {"installed_at": time.time() - 10,
            "antigravity_roots": [str(self.root / "brain")], "antigravity_profile": AG,
            "codex_accounts": {m.identity_key("one@example.com"): [CODEX_A],
                               m.identity_key("two@example.com"): [CODEX_B]}}
        self.sent = []

    def event(self, turn="1"):
        return {"hook_event_name": "UserPromptSubmit", "session_id": "session", "turn_id": turn}

    def run_event(self, email, turn="1"):
        return m.run("codex", self.event(turn), self.config, self.state,
                     account_reader=lambda _: {"email": email}, sender=self.sent.append)

    def transcript(self, step=0, age=0, source="USER_EXPLICIT"):
        path = self.root / "brain" / "conversation" / "transcript.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf8") as f:
            f.write(json.dumps({"type": "USER_INPUT", "source": source, "step_index": step,
                "created_at": dt.datetime.fromtimestamp(time.time()-age, dt.timezone.utc).isoformat(),
                "content": "private message must never be stored"}) + "\n")
        return {"conversationId": "conversation", "transcriptPath": str(path)}

    def test_account_change_is_read_for_each_message(self):
        self.assertEqual(self.run_event(" ONE@EXAMPLE.COM "), "selected")
        self.assertEqual(self.run_event("two@example.com", "2"), "selected")
        self.assertEqual(self.sent, [CODEX_A, CODEX_B])

    def test_unknown_and_ambiguous_accounts_do_not_switch(self):
        self.assertEqual(self.run_event("unknown@example.com"), "unmapped")
        self.config["codex_accounts"][m.identity_key("one@example.com")].append(CODEX_B)
        self.assertEqual(self.run_event("one@example.com", "2"), "unmapped")
        self.assertEqual(self.sent, [])

    def test_steering_message_in_same_turn_selects_again(self):
        self.run_event("one@example.com")
        self.assertEqual(self.run_event("two@example.com"), "selected")
        self.assertEqual(self.sent, [CODEX_A, CODEX_B])

    def test_newer_message_supersedes_slow_identity_lookup(self):
        def slow_identity(_):
            self.run_event("two@example.com", "2")
            return {"email": "one@example.com"}
        self.assertEqual(m.run("codex", self.event(), self.config, self.state,
            account_reader=slow_identity, sender=self.sent.append), "superseded")
        self.assertEqual(self.sent, [CODEX_B])

    def test_antigravity_continuation_and_followup(self):
        event = self.transcript()
        self.assertEqual(m.run("antigravity", event, self.config, self.state, sender=self.sent.append), "selected")
        self.run_event("one@example.com")
        self.assertEqual(m.run("antigravity", event, self.config, self.state, sender=self.sent.append), "duplicate")
        event = self.transcript(step=5)
        self.assertEqual(m.run("antigravity", event, self.config, self.state, sender=self.sent.append), "selected")
        self.assertEqual(self.sent, [AG, CODEX_A, AG])
        self.assertNotIn(b"private message", self.state.read_bytes())

    def test_delayed_antigravity_record_cannot_override_newer_codex_message(self):
        event = self.transcript(age=2)
        self.run_event("one@example.com")
        self.assertEqual(m.run("antigravity", event, self.config, self.state,
                              sender=self.sent.append), "superseded")
        self.assertEqual(self.sent, [CODEX_A])

    def test_old_and_automated_antigravity_messages_ignored(self):
        self.assertIsNone(m.antigravity_marker(self.transcript(age=200), self.config))
        self.assertIsNone(m.antigravity_marker(self.transcript(source="SYSTEM"), self.config))

    def test_path_outside_configured_brain_is_rejected(self):
        event = self.transcript()
        event["transcriptPath"] = str(self.root / "other" / "transcript.jsonl")
        self.assertIsNone(m.antigravity_marker(event, self.config))

    def test_wrong_events_and_wrong_provider_profiles_ignored(self):
        event = self.event(); event["hook_event_name"] = "Stop"
        self.assertEqual(m.run("codex", event, self.config, self.state), "ignored")
        self.config["codex_accounts"][m.identity_key("one@example.com")] = [AG]
        self.assertEqual(self.run_event("one@example.com"), "unmapped")

    def test_only_explicit_private_http_endpoint_allowed(self):
        self.assertEqual(m.api_origin("http://192.168.1.2:8080/api/v1/next-account"), "http://192.168.1.2:8080")
        for host in ["127.0.0.1", "169.254.1.2", "8.8.8.8", "example.com", "user:pass@192.168.1.2"]:
            with self.assertRaises(ValueError):
                m.api_origin(f"http://{host}/api/v1/next-account")
        with self.assertRaises(ValueError):
            m.api_origin("http://192.168.1.2/api/v1/next-account?token=x")

    def test_selection_requires_matching_confirmation(self):
        with patch.object(m, "api_request", return_value={"status": "ok", "profile_id": CODEX_B}):
            with self.assertRaises(ValueError):m.select_account(CODEX_A)

    def test_codex_executable_rediscovered_after_desktop_update(self):
        configured = self.root / "old" / "codex.exe"
        older = self.root / "local" / "OpenAI" / "Codex" / "bin" / "older" / "codex.exe"
        current = self.root / "local" / "OpenAI" / "Codex" / "bin" / "current" / "codex.exe"
        older.parent.mkdir(parents=True)
        current.parent.mkdir(parents=True)
        older.touch()
        current.touch()
        os.utime(older, ns=(1, 1))
        os.utime(current, ns=(2, 2))
        with patch.dict(os.environ, {"LOCALAPPDATA": str(self.root / "local")}):
            self.assertEqual(m.codex_executable({"codex_executable": str(configured)}), current)

    def test_configured_codex_executable_remains_preferred(self):
        configured = self.root / "configured" / "codex.exe"
        configured.parent.mkdir(parents=True)
        configured.touch()
        with patch.dict(os.environ, {"LOCALAPPDATA": str(self.root / "missing")}):
            self.assertEqual(m.codex_executable({"codex_executable": str(configured)}), configured)

    def test_windows_notifications_filter_and_parse_multiple_records(self):
        def record(name, action, last=False):
            data = name.encode("utf-16-le")
            size = (12 + len(data) + 3) & ~3
            return struct.pack("<III", 0 if last else size, action, len(data)) + data + bytes(size-12-len(data))
        target = r"conversation\.system_generated\logs\transcript.jsonl"
        data = record("other.txt", 3) + record(target, 3) + record(target, 2, True)
        self.assertEqual(list(watcher.notifications(data)), [target])
        self.assertEqual(list(watcher.notifications(b"short")), [])
        self.assertEqual(list(watcher.notifications(struct.pack("<III", 0, 3, 500))), [])

    def test_history_records_source_order_and_never_prompt_or_identity(self):
        self.run_event("one@example.com")
        event = self.transcript()
        m.run("antigravity", event, self.config, self.state, sender=self.sent.append, source="antigravity-watch")
        with closing(sqlite3.connect(self.state)) as db:
            rows = db.execute("SELECT source,result,stage FROM history ORDER BY id").fetchall()
        self.assertEqual(rows, [("codex-hook", "selected", "selection"),
                                ("antigravity-watch", "selected", "selection")])
        for secret in (b"one@example.com", b"private message", CODEX_A.encode(), AG.encode(), b'"session"'):
            self.assertNotIn(secret, self.state.read_bytes())

    def test_failed_selection_is_distinguished_from_failed_identity(self):
        def fail(_): raise TimeoutError("private endpoint and secret must not be saved")
        for reader, sender, stage in ((fail, self.sent.append, "identity"),
              (lambda _: {"email": "one@example.com"}, fail, "selection")):
            with self.assertRaises(TimeoutError):
                m.run("codex", self.event(), self.config, self.state, account_reader=reader, sender=sender)
            with closing(sqlite3.connect(self.state)) as db:
                row = db.execute("SELECT result,stage,error FROM history ORDER BY id DESC LIMIT 1").fetchone()
            self.assertEqual(row, ("unavailable", stage, "timeout"))
        self.assertNotIn(b"private endpoint", self.state.read_bytes())

    def test_history_is_bounded_and_streaming_duplicates_are_throttled(self):
        with patch.object(m, "HISTORY_LIMIT", 5):
            for _ in range(9): m.diagnostic(self.state, "codex-hook", "selected")
        with closing(sqlite3.connect(self.state)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM history").fetchone()[0], 5)
        for _ in range(20): m.diagnostic(self.state, "antigravity-watch", "duplicate")
        with closing(sqlite3.connect(self.state)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM history WHERE result='duplicate'").fetchone()[0], 1)

    def test_diagnostics_failure_does_not_break_selection(self):
        with patch.object(m, "diagnostic", return_value=None):
            self.assertEqual(self.run_event("one@example.com"), "selected")
        m.diagnostic(self.root / "missing" / "bad.sqlite", "codex-hook", "selected")


if __name__ == "__main__":
    unittest.main()
