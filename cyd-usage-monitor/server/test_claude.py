"""Offline Claude subscription quota, profile isolation and login regressions."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

try:
    from . import collector
except ImportError:
    import collector


PANEL = """Settings  Status   Config   Usage   Stats
Session
Total cost: $0.0000
Usage: 0 input, 0 output, 0 cache read, 0 cache write
Current session
                                                   0% used

Current week (all models)
██████████████████████████████████████████████████ 100% used
Resets Nov 7, 11pm (America/New_York)

What's contributing to your usage?
Approximate · sessions on this machine only
97% Start fresh when you switch tasks · run /clear
11% Compact before you step away · run /compact
"""
PROFILE = {"provider": "claude", "id": "claude-0123456789", "label": "Example"}
IDENTITY = {"loggedIn": True, "authMethod": "claude.ai", "email": "demo@example.invalid", "subscriptionType": "max"}


class ClaudeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        paths = {name: root / value.relative_to(collector.DATA_DIR)
                 for name, value in vars(collector).items()
                 if isinstance(value, Path) and value.is_relative_to(collector.DATA_DIR)}
        paths["PROFILE_ROOT"] = root / "profiles"
        patcher = patch.multiple(collector, **paths)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_operator_panel_uses_only_subscription_bars(self):
        parsed = collector.parse_claude_usage(PANEL)
        self.assertEqual(parsed["provider"], "claude")
        self.assertEqual(parsed["metrics"]["five_hour"], {"remaining_pct": 100, "used_percentage": 0.0,
                         "reset_reported": False, "reset": "", "window_state": "idle"})
        self.assertEqual(parsed["metrics"]["weekly"], {"remaining_pct": 0, "used_percentage": 100.0,
                         "reset_reported": True, "reset": "Nov 7, 11pm (America/New_York)"})

    def test_official_auth_login_url_ends_before_code_prompt(self):
        url = "https://claude.ai/oauth/authorize?client_id=example&state=example"
        output = "Opening browser to sign in…\nIf the browser didn't open, visit: " + url + "\nPaste code here if prompted > "
        self.assertEqual(collector.extract_login_url(output), url)

    def test_linux_ink_horizontal_cursor_spacing_preserves_headings(self):
        rendered = PANEL.replace("Current session", "Current\x1b[10Gsession").replace("Current week (all models)", "Current\x1b[10Gweek\x1b[15G(all\x1b[20Gmodels)")
        self.assertEqual(collector.parse_claude_usage(rendered)["metrics"]["weekly"]["remaining_pct"], 0)
        responders = [(r"Choose\s+the\s+text\s+style", "\r", "Theme")]
        self.assertEqual(collector.matching_pty_responses("Choose\x1b[9Gthe\x1b[13Gtext\x1b[18Gstyle", responders, set()), [("\r", "Theme")])

    def test_native_cursor_movement_preserves_rows_without_newlines(self):
        rendered = ("Session\x1b[1BTotal cost: $0.0000\x1b[1B"
                    "Current\x1b[10Gsession\x1b[1B 0%\x1b[80Gused\x1b[2B"
                    "Current\x1b[10Gweek\x1b[15G(all\x1b[20Gmodels)\x1b[1E100% used"
                    "\x1b[12;1HResets Nov 7, 11pm (America/New_York)"
                    "\x1b[1BWhat's contributing to your usage?\x1b[1B97% run /clear")
        parsed = collector.parse_claude_usage(rendered)
        self.assertEqual(parsed["metrics"]["five_hour"]["remaining_pct"], 100)
        self.assertEqual(parsed["metrics"]["weekly"]["remaining_pct"], 0)
        self.assertEqual(parsed["metrics"]["weekly"]["reset"], "Nov 7, 11pm (America/New_York)")

    def test_lone_carriage_returns_preserve_row_boundaries(self):
        parsed = collector.parse_claude_usage(PANEL.replace("\n", "\r"))
        self.assertEqual(parsed["metrics"]["weekly"]["remaining_pct"], 0)

    def test_cursor_distance_does_not_allocate_numeric_amount(self):
        raw = "Current\x1b[999999999999999999Gsession\x1b[999999999999999B0% used"
        normalized = collector.normalize_claude_terminal(raw)
        self.assertEqual(normalized, "Current session\n0% used")
        self.assertLess(len(normalized), len(raw))

    def test_request_offsets_remain_raw_when_panels_use_cursor_moves(self):
        frame = PANEL.replace("\n", "\x1b[1B")
        check = collector.PanelConfirmation(collector.parse_claude_usage, None, require_repeat=True)
        check.begin_request(0)
        self.assertFalse(check(frame))
        check.begin_request(len(frame))
        self.assertTrue(check(frame + frame))
        partial = "Current\x1b[10Gsession\x1b[1B40% used"
        with self.assertRaises(ValueError):
            collector.parse_claude_usage(frame + partial)

    def test_native_safety_check_selects_yes_below_default_no(self):
        workdir = collector.profile_workdir(PROFILE)
        responders = collector.claude_collection_responders(PROFILE, workdir)
        for prompt in (
            "Quick safety check: folder\n❯ No, exit\nYes, I trust this folder\nEnter to confirm",
            "Quicksafetycheck:folder\n❯No,exit\nYes,Itrustthisfolder\nEntertoconfirm",
            "Quick\x1b[10Gsafety\x1b[20Gcheck: folder\n❯No,exit\nYes,I\x1b[20Gtrust\x1b[30Gthis\x1b[40Gfolder",
        ):
            handled = set()
            responses = collector.matching_pty_responses(prompt, responders, handled)
            self.assertEqual([value for value, _ in responses], ["\x1b[B\r"])
            self.assertEqual(collector.matching_pty_responses(prompt, responders, handled), [])

    def test_legacy_safety_check_only_enters_when_yes_is_selected(self):
        responders = collector.claude_collection_responders(PROFILE, collector.profile_workdir(PROFILE))
        prompt = "Do you trust the files in this folder?\n❯ 1. Yes, I trust this folder\n2. No, exit"
        self.assertEqual([value for value, _ in collector.matching_pty_responses(prompt, responders, set())], ["\r"])
        self.assertEqual(collector.matching_pty_responses("Do you trust the files in this folder?", responders, set()), [])

    def test_trust_responder_rejects_other_workspaces(self):
        collector.profile_workdir(PROFILE)
        with self.assertRaises(ValueError):
            collector.claude_collection_responders(PROFILE, collector.PROFILE_ROOT)
        with self.assertRaises(ValueError):
            collector.claude_collection_responders(dict(PROFILE, id="claude-../../"), collector.PROFILE_ROOT)

    def test_native_menu_selection_is_committed_before_enter(self):
        events = []
        with patch.object(collector.os, "write", side_effect=lambda fd, value: events.append(("write", fd, value))), \
                patch.object(collector.time, "sleep", side_effect=lambda delay: events.append(("wait", delay))):
            collector.send_pty_response(123, "\x1b[B\r")
        self.assertEqual(events, [("wait", 1.5), ("write", 123, b"\x1b[B"), ("wait", 1.5), ("write", 123, b"\r")])

    def test_trust_layout_family_cannot_confirm_twice_on_redraw(self):
        responders = collector.claude_collection_responders(PROFILE, collector.profile_workdir(PROFILE))
        handled = set()
        prompt = "Quick safety check\n❯ No, exit\nYes, I trust this folder"
        self.assertEqual(len(collector.matching_pty_responses(prompt, responders, handled)), 1)
        self.assertEqual(collector.matching_pty_responses(prompt + "\n❯ Yes, I trust this folder", responders, handled), [])

    def test_usage_commands_wait_for_onboarding_to_finish(self):
        check = collector.PanelConfirmation(collector.parse_claude_usage, None, onboarding_guard=True)
        trust = "Claude Code v2.1.311\nQuick safety check\n❯ No, exit\nYes, I trust this folder"
        self.assertFalse(check.allow_input("/usage\r", trust))
        self.assertFalse(check.allow_input("/usage\r", "Choose the text style"))
        self.assertTrue(check.allow_input("/usage\r", trust + "\nClaude Code v2.1.311\nClaude Pro"))

    def test_fractional_used_values_and_reset(self):
        parsed = collector.parse_claude_usage(PANEL.replace("0% used", "12.5% used", 1)
                                               .replace("Current week", "Resets 3:45pm (America/New_York)\nCurrent week", 1))
        self.assertEqual(parsed["metrics"]["five_hour"]["remaining_pct"], 88)
        self.assertEqual(parsed["metrics"]["five_hour"]["reset"], "3:45pm (America/New_York)")
        self.assertEqual(parsed["metrics"]["five_hour"]["used_percentage"], 12.5)
        self.assertTrue(parsed["metrics"]["five_hour"]["reset_reported"])
        self.assertEqual(parsed["metrics"]["five_hour"]["window_state"], "active")

    def test_fractional_consumption_never_becomes_idle_by_rounding(self):
        parsed = collector.parse_claude_usage(PANEL.replace("0% used", "0.4% used", 1))
        five_hour = parsed["metrics"]["five_hour"]
        self.assertEqual(five_hour["remaining_pct"], 100)
        self.assertEqual(five_hour["used_percentage"], 0.4)
        self.assertFalse(five_hour["reset_reported"])
        self.assertEqual(five_hour["window_state"], "active")

    def test_zero_used_with_reported_reset_stays_active(self):
        parsed = collector.parse_claude_usage(PANEL.replace("Current week", "Resets 3:45pm (America/New_York)\nCurrent week", 1))
        self.assertEqual(parsed["metrics"]["five_hour"]["used_percentage"], 0.0)
        self.assertTrue(parsed["metrics"]["five_hour"]["reset_reported"])
        self.assertEqual(parsed["metrics"]["five_hour"]["window_state"], "active")

    def test_idle_requires_two_independent_raw_zero_no_reset_panels(self):
        check = collector.PanelConfirmation(collector.parse_claude_usage, None, require_repeat=True)
        active = PANEL.replace("0% used", "0.4% used", 1)
        check.begin_request(0)
        self.assertFalse(check(active))
        check.begin_request(len(active))
        self.assertFalse(check(active + PANEL))  # Rounded percentages alone match.
        check.begin_request(len(active + PANEL))
        self.assertTrue(check(active + PANEL + PANEL))

    def test_model_specific_weekly_row_cannot_override_all_models(self):
        text = PANEL.replace("What's contributing", "Current week (Sonnet only)\n 75% used\nResets Friday\nWhat's contributing")
        self.assertEqual(collector.parse_claude_usage(text)["metrics"]["weekly"]["remaining_pct"], 0)
        with self.assertRaises(ValueError):
            collector.parse_claude_usage(PANEL.replace("(all models)", "(Sonnet only)"))

    def test_latest_partial_frame_cannot_borrow_old_weekly_quota(self):
        with self.assertRaises(ValueError):
            collector.parse_claude_usage(PANEL + "\nCurrent session\n 50% used\n")

    def test_cached_network_login_and_invalid_values_fail_closed(self):
        for suffix in ("Showing last-known usage from 2 minutes ago", "usage endpoint is rate limited", "Please log in"):
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                collector.parse_claude_usage(PANEL + suffix)
        for invalid in ("101", "-1", "200", "NaN"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                collector.parse_claude_usage(PANEL.replace("0% used", invalid + "% used", 1))

    def test_identity_reads_official_command_with_no_credential_files(self):
        result = Mock(returncode=0, stdout=json.dumps(IDENTITY))
        with patch.object(collector.subprocess, "run", return_value=result) as run:
            identity = collector.claude_account_status("claude", {"HOME": "isolated"}, Path("."))
        self.assertEqual(run.call_args.args[0], ["claude", "auth", "status"])
        self.assertEqual(identity, {"account_name": "demo@example.invalid", "plan_type": "max"})

    def test_identity_requires_subscription_and_unique_account(self):
        for status in ({}, dict(IDENTITY, loggedIn=False), dict(IDENTITY, authMethod="api_key"), dict(IDENTITY, email="")):
            with self.subTest(status=status), patch.object(collector.subprocess, "run", return_value=Mock(returncode=0, stdout=json.dumps(status))), self.assertRaises(RuntimeError):
                collector.claude_account_status("claude", {}, Path("."))

    def test_environment_is_private_and_does_not_inherit_api_keys(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "not-inherited", "CLAUDE_CONFIG_DIR": "not-inherited",
                                     "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "DISABLE_TELEMETRY": "1"}):
            env = collector.profile_environment(PROFILE)
        self.assertTrue(Path(env["CLAUDE_CONFIG_DIR"]).is_relative_to(collector.PROFILE_ROOT / PROFILE["id"]))
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertFalse((Path(env["HOME"]) / ".gemini").exists())
        self.assertEqual(env["DISABLE_AUTOUPDATER"], "1")
        self.assertEqual(env["DISABLE_ERROR_REPORTING"], "1")
        self.assertNotIn("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", env)
        self.assertNotIn("DISABLE_TELEMETRY", env)
        self.assertNotIn("CODEX_HOME", env)

    def test_unknown_providers_cannot_use_antigravity_fallback(self):
        with self.assertRaises(ValueError):
            collector.cli_executable("unknown")
        with self.assertRaises(ValueError):
            collector.profile_environment(dict(PROFILE, provider="unknown"))

    def test_collection_confirms_independent_panels_without_model_prompts(self):
        def capture(command, env, inputs, **kwargs):
            self.assertEqual(command, ["claude"])
            self.assertEqual({value for _, value, _ in inputs}, {"/usage\r", "\x1b"})
            check = kwargs["complete"]
            check.begin_request(0)
            self.assertFalse(check(PANEL))
            self.assertFalse(check(PANEL))  # A repaint is not confirmation.
            check.begin_request(len(PANEL))
            self.assertTrue(check(PANEL + PANEL))
            return PANEL + PANEL
        with patch.object(collector, "cli_executable", return_value="claude"), \
                patch.object(collector, "claude_account_status", return_value={"account_name": "demo@example.invalid", "plan_type": "max"}), \
                patch.object(collector, "pty_command", side_effect=capture):
            result = collector.collect_profile(PROFILE)
        self.assertEqual(result["account_name"], "demo@example.invalid")
        self.assertEqual(result["capture"]["confirmation_requests"], 2)

    def test_changed_identity_or_single_unconfirmed_capture_is_rejected(self):
        def capture(*args, **kwargs):
            check = kwargs["complete"]
            check.begin_request(0)
            check(PANEL)
            check.begin_request(len(PANEL))
            check(PANEL + PANEL)
            return PANEL + PANEL
        with patch.object(collector, "cli_executable", return_value="claude"), \
                patch.object(collector, "claude_account_status", side_effect=[{"account_name": "one"}, {"account_name": "two"}]), \
                patch.object(collector, "pty_command", side_effect=capture), self.assertRaises(collector.CollectionError):
            collector.collect_profile(PROFILE)
        with patch.object(collector, "cli_executable", return_value="claude"), \
                patch.object(collector, "claude_account_status", return_value={"account_name": "one"}), \
                patch.object(collector, "pty_command", return_value=PANEL), self.assertRaises(collector.CollectionError):
            collector.collect_profile(PROFILE)

    def test_profile_removal_accepts_claude_but_rejects_traversal(self):
        env = collector.profile_environment(PROFILE)
        self.assertTrue(Path(env["HOME"]).exists())
        collector.remove_profile_directory(PROFILE["id"])
        self.assertFalse(Path(env["HOME"]).exists())
        with self.assertRaises(ValueError):
            collector.remove_profile_directory("claude-../../")

    def test_cli_version_parses_claude_banner(self):
        self.assertEqual(collector.cli_version_from_transcript("Claude Code v2.1.100"), "2.1.100")

    def make_session(self):
        session = object.__new__(collector.LoginSession)
        session.profile = PROFILE
        session.master = 123
        session.process = Mock()
        session.process.poll.return_value = None
        session.started = collector.time.monotonic()
        session.output = bytearray()
        session.events = []
        session.last_input = ""
        session.input_received = session.login_confirmed = session.succeeded = False
        session.auto_select_due = session.onboarding_continue_due = session.workspace_trust_due = None
        session.auto_selected = session.onboarding_entered = session.onboarding_finished = False
        session.terms_seen = session.terms_finished = False
        session.workspace_trusted = True
        session.ready_since = None
        session.failure_reason = ""
        return session

    def test_login_accepts_success_and_never_echoes_submitted_code(self):
        session = self.make_session()
        session.output.extend(b"secret-code#state\nLogin successful")
        with patch.object(collector.select, "select", return_value=([], [], [])), patch.object(collector.os, "write") as write:
            output, finished = session.tick("secret-code#state")
        self.assertTrue(finished)
        self.assertTrue(session.succeeded)
        self.assertNotIn("secret-code#state", output)
        self.assertEqual(write.call_args.args[1], b"secret-code#state\r")

    def test_failed_login_cannot_be_marked_success(self):
        session = self.make_session()
        session.process.poll.return_value = 1
        session.output.extend(b"Failed to authenticate")
        with patch.object(collector.select, "select", return_value=([], [], [])):
            _, finished = session.tick()
        self.assertTrue(finished)
        self.assertFalse(session.succeeded)

    def test_wrapped_or_ansi_repainted_authorization_code_never_persists(self):
        session = self.make_session()
        session.output.extend(b"secret-\r\ncode\x1b[10G#state\nWaiting for authentication")
        with patch.object(collector.select, "select", return_value=([], [], [])), patch.object(collector.os, "write"):
            output, _ = session.tick("secret-code#state")
        self.assertNotIn("secret", output)
        self.assertNotIn("#state", output)
        transcript = session.transcript("secret-\ncode#state")
        self.assertNotIn("secret", transcript)
        self.assertNotIn("#state", transcript)


if __name__ == "__main__":
    unittest.main()
