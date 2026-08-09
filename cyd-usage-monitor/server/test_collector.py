import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from . import collector
    from .collector import extract_login_url, notify_transition, parse_antigravity_usage, parse_codex_status, waha_settings
except ImportError:
    import collector
    from collector import extract_login_url, notify_transition, parse_antigravity_usage, parse_codex_status, waha_settings


class CollectorParserTests(unittest.TestCase):
    def test_parses_codex_status(self):
        snapshot = parse_codex_status("""
Account:              demo-account (Free)
Monthly limit:        [███████████████░░░░░] 73% left (resets 19:18 on 5 Sep)
Credits:              500 credits
""")
        self.assertEqual(snapshot["account_name"], "demo-account")
        self.assertEqual(snapshot["metrics"]["primary"]["remaining_pct"], 73)
        self.assertEqual(snapshot["credits"], "500 credits")

    def test_parses_unicode_codex_status_card(self):
        snapshot = parse_codex_status("""
│  Account:              demo-account (Free)                               │
│  Monthly limit:        [░░░░░░░░░░] 73% left (resets 19:18 on 5 Sep) │
│  Credits:              500 credits                                      │
""")
        self.assertEqual(snapshot["account_name"], "demo-account")
        self.assertEqual(snapshot["metrics"]["primary"]["remaining_pct"], 73)

    def test_parses_weekly_codex_limit(self):
        snapshot = parse_codex_status("""
Account: demo-account (Plus)
Weekly limit: [bar] 100% left (resets 20:04 on 15 Aug)
""")
        self.assertEqual(snapshot["limit_label"], "Weekly Limit")
        self.assertEqual(snapshot["metrics"]["primary"]["remaining_pct"], 100)

    def test_parses_antigravity_usage(self):
        snapshot = parse_antigravity_usage("""
Account: demo-account
GEMINI MODELS
Weekly Limit Remaining
  [bar] 24.12% remaining · Refreshes in 38h 54m
Five Hour Limit Remaining
  [bar] 21.88% remaining · Refreshes in 3h 8m
CLAUDE AND GPT MODELS
Weekly Limit Remaining
  [bar] 66.37% remaining · Refreshes in 57h 18m
Five Hour Limit Remaining
  [bar] 55.5% remaining · Refreshes in 1h 2m
""")
        self.assertEqual(snapshot["metrics"]["gemini"]["weekly"]["remaining_pct"], 24)
        self.assertEqual(snapshot["metrics"]["claude"]["five_hour"]["remaining_pct"], 56)

    def test_parses_antigravity_quota_available(self):
        snapshot = parse_antigravity_usage("""
Account: demo-account
GEMINI MODELS
Weekly Limit Remaining
  [bar] 24.12% remaining · Refreshes in 23h 24m
Five Hour Limit Remaining
  [bar] 100.00%
  Quota available
CLAUDE AND GPT MODELS
Weekly Limit Remaining
  [bar] 66.37% remaining · Refreshes in 41h 48m
Five Hour Limit Remaining
  [bar] 100.00%
  Quota available
""")
        self.assertEqual(snapshot["metrics"]["gemini"]["five_hour"], {"remaining_pct": 100, "reset": "Quota available"})
        self.assertEqual(snapshot["metrics"]["claude"]["five_hour"], {"remaining_pct": 100, "reset": "Quota available"})

    def test_reassembles_wrapped_oauth_url(self):
        transcript = """Open this URL:
https://accounts.google.com/o/oauth2/auth?client_id=abc
 .apps.googleusercontent.com&state=xyz

If you are not redirected, paste the authorization code below:
"""
        self.assertEqual(
            extract_login_url(transcript),
            "https://accounts.google.com/o/oauth2/auth?client_id=abc.apps.googleusercontent.com&state=xyz",
        )

    def test_alerts_are_deduplicated_when_waha_is_unconfigured(self):
        profile = {"id": "codex-test", "provider": "codex", "label": "Test account"}
        failed = {"status": "error", "error": "Codex is not signed in"}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"WAHA_API_KEY": "", "WAHA_ALERT_CHAT_ID": ""}):
            previous_file = collector.ALERTS_FILE
            previous_settings = collector.SETTINGS_FILE
            collector.ALERTS_FILE = Path(directory) / "alert-status.json"
            collector.SETTINGS_FILE = Path(directory) / "monitor-settings.json"
            try:
                notify_transition(profile, None, failed)
                first = json.loads(collector.ALERTS_FILE.read_text(encoding="utf-8"))
                notify_transition(profile, failed, failed)
                second = json.loads(collector.ALERTS_FILE.read_text(encoding="utf-8"))
            finally:
                collector.ALERTS_FILE = previous_file
                collector.SETTINGS_FILE = previous_settings
        self.assertFalse(first["configured"])
        self.assertEqual(first["last_event"], "failure")
        self.assertEqual(second["last_event"], "failure")

    def test_saved_dashboard_group_id_overrides_env_group_id(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"WAHA_ALERT_CHAT_ID": "from-env@g.us"}):
            previous_file = collector.SETTINGS_FILE
            collector.SETTINGS_FILE = Path(directory) / "monitor-settings.json"
            try:
                collector.write_json(collector.SETTINGS_FILE, {"waha_alert_chat_id": "from-dashboard@g.us"})
                self.assertEqual(waha_settings()["chat_id"], "from-dashboard@g.us")
            finally:
                collector.SETTINGS_FILE = previous_file

    def test_provider_environment_does_not_inherit_collector_secrets(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "WAHA_API_KEY": "must-not-reach-provider",
            "MONITOR_ADMIN_PASSWORD": "must-not-reach-provider",
            "CYD_API_TOKEN": "must-not-reach-provider",
        }, clear=False):
            previous_root = collector.PROFILE_ROOT
            collector.PROFILE_ROOT = Path(directory)
            try:
                env = collector.profile_environment({"id": "codex-0123456789", "provider": "codex"})
            finally:
                collector.PROFILE_ROOT = previous_root
        self.assertNotIn("WAHA_API_KEY", env)
        self.assertNotIn("MONITOR_ADMIN_PASSWORD", env)
        self.assertNotIn("CYD_API_TOKEN", env)
        self.assertIn("CODEX_HOME", env)

    def test_login_input_is_consumed_once_and_deleted(self):
        request_id = "00000000-0000-4000-8000-000000000001"
        with tempfile.TemporaryDirectory() as directory:
            previous_dir = collector.LOGIN_INPUT_DIR
            collector.LOGIN_INPUT_DIR = Path(directory)
            try:
                path = collector.LOGIN_INPUT_DIR / f"{request_id}.json"
                collector.write_json(path, {"value": "one-time-code"})
                self.assertEqual(collector.consume_login_input(request_id), "one-time-code")
                self.assertFalse(path.exists())
                self.assertEqual(collector.consume_login_input(request_id), "")
            finally:
                collector.LOGIN_INPUT_DIR = previous_dir

    def test_completed_runtime_record_is_scrubbed(self):
        record = {
            "login_url": "https://example.invalid/?state=secret",
            "device_code": "ABCD-EFGH",
            "terminal_output": "private account label",
            "needs_input": True,
        }
        collector.scrub_runtime_record(record, status="completed", phase="ready", output="Done")
        for key in ("login_url", "device_code", "terminal_output", "needs_input"):
            self.assertNotIn(key, record)
        self.assertEqual(record["status"], "completed")

    def test_profile_directory_removal_is_scoped_to_profile_root(self):
        with tempfile.TemporaryDirectory() as directory:
            previous_root = collector.PROFILE_ROOT
            collector.PROFILE_ROOT = Path(directory)
            target = collector.PROFILE_ROOT / "codex-0123456789"
            target.mkdir()
            (target / "credential.json").write_text("private", encoding="utf-8")
            try:
                collector.remove_profile_directory("codex-0123456789")
                self.assertFalse(target.exists())
                with self.assertRaises(ValueError):
                    collector.remove_profile_directory("../outside")
            finally:
                collector.PROFILE_ROOT = previous_root


if __name__ == "__main__":
    unittest.main()
