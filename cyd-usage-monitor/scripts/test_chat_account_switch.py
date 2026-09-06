import datetime as dt
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import struct
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


if __name__ == "__main__":
    unittest.main()
