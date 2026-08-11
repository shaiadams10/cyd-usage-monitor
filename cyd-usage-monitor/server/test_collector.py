import json
import os
import tempfile
import unittest
import datetime as dt
from pathlib import Path
from unittest.mock import patch

try:
    from . import collector
    from .collector import extract_login_url, notify_transition, parse_antigravity_usage, parse_codex_status, waha_settings
except ImportError:
    import collector
    from collector import extract_login_url, notify_transition, parse_antigravity_usage, parse_codex_status, waha_settings


class CollectorParserTests(unittest.TestCase):
    def test_normalizes_openrouter_account_usage_and_completed_days(self):
        now = dt.datetime(2026, 8, 9, 12, tzinfo=dt.timezone.utc)
        snapshot = collector.normalize_openrouter(
            {"data": {"total_credits": 100.5, "total_usage": 25.75}},
            [
                {"usage_daily": 1.25, "usage_weekly": 4, "usage_monthly": 12},
                {"usage_daily": 0.75, "usage_weekly": 2, "usage_monthly": 3},
            ],
            {"data": [
                {"date": "2026-08-08", "model": "openai/gpt-5", "usage": 1.5},
                {"date": "2026-08-08", "model": "anthropic/claude", "usage": 0.5},
                {"date": "2026-08-03", "model": "openai/gpt-5", "usage": 2.0},
                {"date": "2026-08-09", "model": "ignored/current-day", "usage": 99},
            ]},
            "Personal", now,
        )
        self.assertEqual(snapshot["remaining_credits"], 74.75)
        self.assertEqual(snapshot["usage_today"], 2)
        self.assertEqual(snapshot["usage_week"], 6)
        self.assertEqual(snapshot["usage_month"], 15)
        self.assertEqual(len(snapshot["daily_usage"]), 7)
        self.assertEqual(snapshot["daily_usage"][0], {"date": "2026-08-02", "usage": 0.0})
        self.assertEqual(snapshot["top_model"], {"name": "openai/gpt-5", "usage": 3.5})

    def test_normalizes_openrouter_zero_and_overdrawn_balances(self):
        now = dt.datetime(2026, 8, 9, tzinfo=dt.timezone.utc)
        zero = collector.normalize_openrouter(
            {"data": {"total_credits": 0, "total_usage": 0}}, [], {"data": []}, "Zero", now,
        )
        overdrawn = collector.normalize_openrouter(
            {"data": {"total_credits": 10, "total_usage": 12}}, [], {"data": []}, "Over", now,
        )
        self.assertEqual(zero["remaining_pct"], 0)
        self.assertEqual(overdrawn["remaining_credits"], 0)
        self.assertEqual(overdrawn["top_model"]["name"], "No completed usage")

    def test_openrouter_rejects_malformed_and_oversized_data(self):
        with self.assertRaises(collector.OpenRouterError):
            collector.normalize_openrouter({"data": {}}, [], {"data": []}, "Bad")

    def test_openrouter_collection_paginates_and_sanitizes_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            secret_file = Path(directory) / "secret.json"
            state_file = Path(directory) / "state.json"
            collector.write_json(secret_file, {"key": "never-return-this", "label": "Router"})
            first_page = [{"usage_daily": 0, "usage_weekly": 0, "usage_monthly": 0}] * 100
            responses = [
                {"data": {"total_credits": 10, "total_usage": 2}},
                {"data": first_page}, {"data": []}, {"data": []},
            ]
            with patch.object(collector, "OPENROUTER_SECRET_FILE", secret_file), patch.object(collector, "OPENROUTER_STATE_FILE", state_file), patch.object(collector, "openrouter_json", side_effect=responses) as request:
                snapshot = collector.collect_openrouter()
            self.assertEqual(snapshot["status"], "ok")
            self.assertEqual(request.call_args_list[2].args[0], "/keys?include_disabled=true&offset=100")
            self.assertNotIn("never-return-this", state_file.read_text(encoding="utf-8"))

            with patch.object(collector, "OPENROUTER_SECRET_FILE", secret_file), patch.object(collector, "OPENROUTER_STATE_FILE", state_file), patch.object(collector, "openrouter_json", side_effect=collector.OpenRouterError("OpenRouter rejected the management key")):
                failed = collector.collect_openrouter()
            self.assertEqual(failed["status"], "error")
            self.assertNotIn("never-return-this", json.dumps(failed))

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

    def test_unconfirmed_failure_recovers_without_whatsapp_noise(self):
        profile = {"id": "antigravity-test", "provider": "antigravity", "label": "Antigravity account"}
        failed = {"status": "error", "alert_confirmed": False, "consecutive_failures": 1}
        recovered = {"status": "ok", "account_name": "Recovered account", "collected_at": collector.utcnow()}
        with patch.object(collector, "deliver_waha_message", return_value=(True, "ok")) as delivery:
            collector.notify_transition(profile, None, failed)
            collector.notify_transition(profile, failed, recovered)
            delivery.assert_not_called()

    def test_whatsapp_waits_for_configured_consecutive_failures(self):
        profile = {"id": "antigravity-test", "provider": "antigravity", "label": "Antigravity account"}
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            paths = {
                "DATA_DIR": data_dir,
                "PROFILES_FILE": data_dir / "cli-profiles.json",
                "STATE_FILE": data_dir / "telemetry.json",
                "INCIDENTS_FILE": data_dir / "collector-incidents.json",
            }
            with patch.multiple(collector, **paths), patch.object(collector, "ALERT_FAILURE_THRESHOLD", 3):
                collector.write_json(collector.PROFILES_FILE, {"profiles": [profile]})
                first_failure = {
                    "profile_id": profile["id"], "provider": "antigravity", "status": "error",
                    "error": "temporary incomplete panel", "collected_at": "2026-08-11T15:00:00Z",
                    "diagnostics": {"nonempty_lines": 7, "capture_chars": 146},
                }
                with patch.object(collector, "deliver_waha_message", return_value=(True, "ok")) as delivery:
                    collector.persist_snapshot(profile, first_failure)
                    delivery.assert_not_called()
                self.assertEqual(first_failure["consecutive_failures"], 1)
                self.assertFalse(first_failure["alert_confirmed"])

                second_failure = {
                    "profile_id": profile["id"], "provider": "antigravity", "status": "error",
                    "error": "temporary incomplete panel", "collected_at": "2026-08-11T15:01:30Z",
                    "diagnostics": {"nonempty_lines": 8, "capture_chars": 180},
                }
                with patch.object(collector, "deliver_waha_message", return_value=(True, "ok")) as delivery:
                    collector.persist_snapshot(profile, second_failure)
                    delivery.assert_not_called()
                self.assertFalse(second_failure["alert_confirmed"])

                third_failure = {
                    "profile_id": profile["id"], "provider": "antigravity", "status": "error",
                    "error": "temporary incomplete panel", "collected_at": "2026-08-11T15:03:00Z",
                    "diagnostics": {"nonempty_lines": 8, "capture_chars": 180},
                }
                with patch.object(collector, "deliver_waha_message", return_value=(True, "ok")) as delivery:
                    collector.persist_snapshot(profile, third_failure)
                    self.assertEqual(delivery.call_args.args[0], "failure")
                    self.assertIn("3 consecutive failed collections", delivery.call_args.args[1])
                self.assertTrue(third_failure["alert_confirmed"])
                self.assertEqual(third_failure["failure_started_at"], first_failure["collected_at"])

                recovered = {
                    "profile_id": profile["id"], "provider": "antigravity", "status": "ok",
                    "account_name": "Recovered account", "collected_at": "2026-08-11T15:04:30Z",
                }
                with patch.object(collector, "deliver_waha_message", return_value=(True, "ok")) as delivery:
                    collector.persist_snapshot(profile, recovered)
                    self.assertEqual(delivery.call_args.args[0], "recovery")
                    self.assertIn("4m 30s", delivery.call_args.args[1])

            history = json.loads((data_dir / "collector-incidents.json").read_text(encoding="utf-8"))["incidents"]
            self.assertEqual(history[0]["failed_polls"], 3)
            self.assertEqual(history[0]["status"], "recovered")

    def test_incident_history_and_whatsapp_explain_transient_recovery(self):
        profile = {"id": "antigravity-test", "provider": "antigravity", "label": "Antigravity account"}
        error = collector.CollectionError(
            "Antigravity /usage did not contain an account field",
            "user@example.com\nhttps://example.invalid/private\nGEMINI MODELS\nWeekly Limit Remaining\nCLAUDE AND GPT MODELS\n",
        )
        with tempfile.TemporaryDirectory() as directory:
            incidents = Path(directory) / "collector-incidents.json"
            debug_dir = Path(directory) / ".collector-debug"
            with patch.object(collector, "INCIDENTS_FILE", incidents), patch.object(collector, "DEBUG_EVIDENCE_DIR", debug_dir):
                failed = collector.error_snapshot(profile, error)
                collector.record_incident(profile, None, failed)
                with patch.object(collector, "deliver_waha_message", return_value=(True, "ok")) as delivery:
                    notify_transition(profile, None, failed)
                failure_message = delivery.call_args.args[1]
                self.assertIn("🚨 *CYD Usage Monitor · Alert*", failure_message)
                self.assertIn("partial /usage screen", failure_message)
                self.assertIn("No credentials were changed", failure_message)
                self.assertIn("diagnostic ID", failure_message)

                evidence = next(debug_dir.glob("*.json")).read_text(encoding="utf-8")
                self.assertNotIn("user@example.com", evidence)
                self.assertNotIn("https://example.invalid/private", evidence)
                self.assertIn("[account redacted]", evidence)

                recovered = {
                    "profile_id": profile["id"], "provider": "antigravity", "status": "ok",
                    "account_name": "Recovered account", "collected_at": collector.utcnow(),
                }
                collector.record_incident(profile, failed, recovered)
                with patch.object(collector, "deliver_waha_message", return_value=(True, "ok")) as delivery:
                    notify_transition(profile, failed, recovered)
                recovery_message = delivery.call_args.args[1]
                self.assertIn("✅ *CYD Usage Monitor · Recovered*", recovery_message)
                self.assertIn("no reconnect or credential change", recovery_message)

            history = json.loads(incidents.read_text(encoding="utf-8"))["incidents"]
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["status"], "recovered")
            self.assertIn("later scheduled poll", history[0]["resolution"])

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
