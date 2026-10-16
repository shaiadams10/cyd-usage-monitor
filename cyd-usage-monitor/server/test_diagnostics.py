import concurrent.futures
import contextlib
import io
import json
import os
import sqlite3
import tempfile
import time
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from . import diagnostics as diag, collector
except ImportError:
    import diagnostics as diag
    import collector


PANEL = """Account: sample-account
CLAUDE AND GPT MODELS
Weekly Limit Remaining
100.00% remaining
Quota available
Five Hour Limit Remaining
78.00% remaining
Refreshes in 2h 10m
Within each group, models share a weekly limit and a 5-hour limit.
esc Close
"""


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        paths = {name: self.root / value.relative_to(collector.DATA_DIR)
                 for name, value in vars(collector).items()
                 if isinstance(value, Path) and value.is_relative_to(collector.DATA_DIR)}
        patcher = patch.multiple(collector, **paths)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_timeline_redacts_and_does_not_accept_arbitrary_fields(self):
        private = 'user@example.com https://host.invalid/secret 192.0.2.9 C:\\Users\\operator\\private /home/operator/private token=short-secret'
        with contextlib.redirect_stdout(io.StringIO()) as console:
            diag.record_event(self.root, "collection_finished", profile={"id": "private-profile", "provider": "codex"},
                              outcome="error", error=private, terminal_output="must not be retained")
        result = diag.query_events(self.root)
        dumped = json.dumps(result) + console.getvalue()
        for secret in ('user@example.com', 'host.invalid', '192.0.2.9', 'operator', 'short-secret', 'must not be retained', 'private-profile'):
            self.assertNotIn(secret, dumped)
        self.assertEqual(result["events"][0]["outcome"], "error")

    def test_query_filters_literal_search_and_pagination(self):
        with contextlib.redirect_stdout(io.StringIO()):
            for i in range(4):
                diag.record_event(self.root, "collection_finished", profile={"provider": "codex" if i % 2 else "antigravity"},
                                  outcome="ok" if i % 2 else "error", category="confirmation")
        result = diag.query_events(self.root, provider="codex", outcome="ok", query="confirmation", limit=1)
        self.assertEqual(len(result["events"]), 1)
        older = diag.query_events(self.root, provider="codex", before=result["next_before"])
        self.assertEqual(len(older["events"]), 1)
        self.assertLess(older["events"][0]["sequence"], result["events"][0]["sequence"])
        self.assertEqual(diag.query_events(self.root, query="%' OR 1=1 --")["events"], [])

    def test_cli_version_survives_timeline_and_rejects_arbitrary_capture_text(self):
        for banner, expected in (("\x1b[32mAntigravity CLI 1.4.0\x1b[0m", "1.4.0"),
                                 ("OpenAI Codex (v0.147.0)", "0.147.0"),
                                 ("Antigravity CLI user@example.com", "")):
            with self.subTest(banner=banner):
                self.assertEqual(collector.cli_version_from_transcript(banner), expected)
        with contextlib.redirect_stdout(io.StringIO()):
            diag.record_event(self.root, "collection_finished", capture={"cli_version": "1.4.0", "raw": "private"})
            diag.record_event(self.root, "collection_finished", capture={"cli_version": "user@example.com"})
        events = diag.query_events(self.root)["events"]
        self.assertEqual(events[1]["capture"], {"cli_version": "1.4.0"})
        self.assertEqual(events[0]["capture"], {})

    def test_concurrent_writers_close_connections_and_keep_all_results(self):
        with contextlib.redirect_stdout(io.StringIO()), concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda i: diag.record_event(self.root, "test", outcome="ok", duration_ms=i), range(16)))
        self.assertEqual(len(diag.query_events(self.root)["events"]), 16)
        # Windows cleanup in tearDown additionally verifies no connection leaks.

    def test_retention_prunes_old_rows_and_bounds_count(self):
        with contextlib.redirect_stdout(io.StringIO()), patch.object(diag, "MAX_EVENTS", 10):
            for i in range(100):
                diag.record_event(self.root, "test")
        self.assertEqual(len(diag.query_events(self.root)["events"]), 10)

    def test_corrupt_or_unwritable_diagnostics_do_not_break_collection(self):
        (self.root / "collector-events.sqlite3").write_text("invalid sqlite", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as console:
            diag.record_event(self.root, "test")
        self.assertIn("diagnostic_storage_unavailable", console.getvalue())
        self.assertEqual(diag.query_events(self.root)["storage"], "unavailable")

    def test_auth_splash_does_not_override_a_signed_in_quota_panel(self):
        error = collector.CollectionError("missing quota", "You are currently not signed in. Signing in...\n" + PANEL)
        facts = collector.collection_diagnostics(error)
        self.assertFalse(facts["authentication_prompt_seen"])
        self.assertEqual(diag.failure_category("missing account", "Select login method:"), "authentication")
        self.assertEqual(diag.failure_category("confirmation incomplete", "Unrecognized command '/statusst'"), "cli_input")

    def test_current_antigravity_layout_preserves_both_groups_after_client_upgrade(self):
        # Public-safe fixture of the 1.4.0 layout, including a scrollable footer
        # and decimal bar values without a second "remaining" percentage line.
        panel = """Antigravity CLI 1.4.0
Account: sample-account
GEMINI MODELS
Models within this group: Gemini Flash, Gemini Pro
Weekly Limit Remaining
[bar] 61.25%
Refreshes in 101h 10m
Five Hour Limit Remaining
[bar] 83.75%
Refreshes in 1h 53m
CLAUDE AND GPT MODELS
Models within this group: Claude Opus, Claude Sonnet, GPT-OSS
Weekly Limit Remaining
[bar] 100.00%
Quota available
Five Hour Limit Remaining
[bar] 100.00%
Quota available
Within each group, models share a weekly limit and a 5-hour limit.
(1–27 of 30 lines)
↑/↓ Scroll · pgup/pgdown Page · ctrl+end Bottom · ctrl+home Top · esc Close
"""
        parsed = collector.parse_antigravity_usage(panel)
        self.assertEqual(parsed["missing_groups"], [])
        self.assertEqual(parsed["metrics"]["gemini"]["weekly"], {"remaining_pct": 61, "reset": "101h 10m"})
        self.assertEqual(parsed["metrics"]["gemini"]["five_hour"], {"remaining_pct": 84, "reset": "1h 53m"})
        self.assertEqual(parsed["metrics"]["claude"]["five_hour"]["remaining_pct"], 100)

    @unittest.skipIf(collector.pty is None, "requires a Unix PTY")
    def test_real_pty_records_completion_and_request_count(self):
        code = "import sys,time; input(); print(" + repr(PANEL) + ",flush=True); time.sleep(3)"
        result = collector.pty_command([sys.executable, "-u", "-c", code], dict(os.environ),
                                       [(0, "/usage\r", "usage")], timeout=2,
                                       complete=collector.PanelConfirmation(collector.parse_antigravity_usage, None))
        self.assertEqual(result.facts["stop_reason"], "complete")
        self.assertEqual(result.facts["requests_sent"], 1)

    def test_complete_single_group_panel_preserves_real_values(self):
        parsed = collector.parse_antigravity_usage(PANEL)
        self.assertEqual(parsed["missing_groups"], ["gemini"])
        self.assertFalse(parsed["metrics"]["gemini"]["available"])
        self.assertEqual(parsed["metrics"]["claude"]["five_hour"]["remaining_pct"], 78)

    def test_codex_capture_disables_burst_detection_and_preserves_confirmation(self):
        panel = "Account: sample (Plus)\n5h limit: 90% left (resets 05:00)\nWeekly limit: 70% left (resets Friday)\n"
        def capture(command, env, inputs, **kwargs):
            self.assertIn("disable_paste_burst=true", command)
            self.assertIn("features.apps=false", command)
            self.assertIn("check_for_update_on_startup=false", command)
            complete = kwargs["complete"]
            complete.begin_request(0)
            self.assertFalse(complete(panel))
            complete.begin_request(len(panel))
            self.assertTrue(complete(panel + panel))
            return collector.TerminalCapture(panel + panel, {"requests_sent": 2, "stop_reason": "complete"})
        with patch.object(collector, "cli_executable", return_value="codex"), \
                patch.object(collector, "profile_environment", return_value={}), \
                patch.object(collector, "profile_workdir", return_value=self.root), \
                patch.object(collector, "pty_command", side_effect=capture):
            snapshot = collector.collect_profile({"id": "test", "provider": "codex"})
        self.assertEqual(snapshot["capture"]["requests_sent"], 2)
        self.assertEqual(snapshot["capture"]["confirmation_requests"], 2)

    def test_truncated_or_empty_single_group_panel_is_rejected(self):
        for text in (PANEL.split("Within each group")[0],
                     PANEL.replace("Five Hour Limit Remaining", "Incomplete field"),
                     "Account: sample\nWithin each group, models share quota.\nesc Close\n"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                collector.parse_antigravity_usage(text)

    def test_open_incident_survives_history_limit_and_preserves_first_evidence(self):
        p = {"id": "antigravity-0123456789", "provider": "antigravity"}
        first = {"status": "error", "collected_at": "2026-10-01T00:00:00Z", "diagnostics": {"evidence_id": "first"}}
        collector.record_incident(p, None, first)
        history = collector.read_json(collector.INCIDENTS_FILE, {})
        history["incidents"] += [{"status": "recovered", "started_at": f"2026-10-02T00:00:{i:02}Z"} for i in range(60)]
        collector.write_json(collector.INCIDENTS_FILE, history)
        later = dict(first, collected_at="2026-10-16T00:00:00Z", diagnostics={"evidence_id": "latest"})
        collector.record_incident(p, first, later)
        history = collector.read_json(collector.INCIDENTS_FILE, {})["incidents"]
        self.assertEqual(len(history), 51)
        self.assertEqual(history[0]["first_evidence_id"], "first")
        self.assertEqual(history[0]["diagnostics"]["evidence_id"], "latest")

    def test_pruning_keeps_first_outage_transcript(self):
        p = {"id": "codex-0123456789", "provider": "codex"}
        collector.DEBUG_EVIDENCE_DIR.mkdir()
        for i in range(205):
            path = collector.DEBUG_EVIDENCE_DIR / f"e{i}.json"
            path.write_text("{}", encoding="utf-8")
            os.utime(path, (time.time() - 1000 + i, time.time() - 1000 + i))
        collector.write_json(collector.INCIDENTS_FILE, {"incidents": [{"status": "open", "first_evidence_id": "e0", "diagnostics": {}}]})
        collector.archive_failure_evidence(p, collector.CollectionError("failed", PANEL), {})
        self.assertTrue((collector.DEBUG_EVIDENCE_DIR / "e0.json").exists())
        self.assertFalse((collector.DEBUG_EVIDENCE_DIR / "e1.json").exists())

    def test_native_log_cleanup_only_removes_old_recognized_logs(self):
        p = {"id": "antigravity-0123456789", "provider": "antigravity"}
        root = self.root / "profiles"
        folder = root / p["id"] / "home" / ".gemini" / "antigravity-cli"
        folder.mkdir(parents=True)
        (folder / "log").mkdir()
        for name in ("cli-20260101_000000.log", "cli.log", "settings.json", "other.log"):
            path = folder / name
            path.write_text("private", encoding="utf-8")
            os.utime(path, (time.time() - 10 * 86400, time.time() - 10 * 86400))
        nested = folder / "log" / "cli-20260102_000000.log"
        nested.write_text("private", encoding="utf-8")
        os.utime(nested, (time.time() - 10 * 86400, time.time() - 10 * 86400))
        with patch.object(collector, "PROFILE_ROOT", root), contextlib.redirect_stdout(io.StringIO()):
            collector.maintain_cli_logs([p])
        self.assertFalse((folder / "cli-20260101_000000.log").exists())
        self.assertFalse(nested.exists())
        for name in ("cli.log", "settings.json", "other.log"):
            self.assertTrue((folder / name).exists())
