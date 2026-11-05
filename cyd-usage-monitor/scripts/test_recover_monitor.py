import contextlib
import datetime as dt
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("recover_monitor", Path(__file__).with_name("recover-monitor.py"))
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class RecoveryTests(unittest.TestCase):
    def info(self, status="running", health="healthy", networks=None):
        return {"state": {"Status": status, "Health": {"Status": health},
                          "StartedAt": "2026-10-26T12:00:00Z"},
                "mode": "monitor-ingress", "networks": {"monitor-ingress": {}} if networks is None else networks}

    def test_failed_boot_and_lost_network_require_recovery(self):
        for status in ("exited", "dead", "created"):
            self.assertTrue(recovery.needs_recovery(self.info(status)))
        self.assertTrue(recovery.needs_recovery(self.info(networks={})))

    def test_healthy_paused_starting_and_host_services_are_preserved(self):
        for status in ("running", "paused", "restarting"):
            self.assertFalse(recovery.needs_recovery(self.info(status)))
        self.assertFalse(recovery.needs_recovery(self.info(health="starting")))
        info = self.info(networks={})
        info["mode"] = "host"
        self.assertFalse(recovery.needs_recovery(info))

    def test_unhealthy_restart_cooldown(self):
        info = self.info(health="unhealthy")
        now = dt.datetime(2026, 10, 26, 12, 4, tzinfo=dt.timezone.utc)
        self.assertFalse(recovery.needs_recovery(info, now))
        self.assertTrue(recovery.needs_recovery(info, now + dt.timedelta(minutes=1)))

    def test_recreate_only_failed_service_without_build_pull_or_dependency_changes(self):
        calls = []
        def run(args, **kwargs):
            calls.append(args)
            if "ps" in args:
                return args[-1] + "-id\n"
            if "inspect" in args:
                return json.dumps(self.info("exited" if args[-1] == "cyd-monitor-app-id" else "running"))
            return ""
        with patch.object(recovery, "run", side_effect=run), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(recovery.recover(Path("/deployment")), 0)
        mutations = [args for args in calls if "up" in args]
        self.assertEqual(len(mutations), 1)
        self.assertEqual(mutations[0][-7:], ["-d", "--no-deps", "--no-build", "--pull", "never", "--force-recreate", "cyd-monitor-app"])

    def test_failed_start_is_retried_and_private_error_is_not_logged(self):
        def run(args, **kwargs):
            if "ps" in args:
                return "container-id\n"
            if "inspect" in args:
                return json.dumps(self.info("exited"))
            raise subprocess.CalledProcessError(1, args, stderr="private-address secret-token")
        output = io.StringIO()
        with patch.object(recovery, "run", side_effect=run), contextlib.redirect_stdout(output):
            self.assertEqual(recovery.recover(Path("/deployment")), 1)
            self.assertEqual(recovery.recover(Path("/deployment")), 1)
        self.assertNotIn("private-address", output.getvalue())
        self.assertNotIn("secret-token", output.getvalue())
        self.assertIn("next timer run", output.getvalue())

    def test_missing_or_scaled_services_are_never_created(self):
        for result in ("", "one\ntwo\n"):
            with patch.object(recovery, "run", return_value=result) as run, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(recovery.recover(Path("/deployment")), 1)
            self.assertEqual(run.call_count, 3)

    def test_systemd_arguments_escape_specifiers_and_environment_expansion(self):
        self.assertEqual(recovery.unit_arg('/a path/%value/$name'), '"/a path/%%value/$$name"')
        with self.assertRaises(ValueError):
            recovery.unit_arg("/path\nExecStart=unexpected")


if __name__ == "__main__":
    unittest.main()
