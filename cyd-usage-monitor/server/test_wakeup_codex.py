import contextlib
import json
import subprocess
import tempfile
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
try:
    from . import wakeup_codex as cli
    from . import wakeup_cli
except ImportError:
    import wakeup_codex as cli
    import wakeup_cli

CHOICES = [{"id": "available-luna", "label": "Luna", "reasoning_levels": ["low", "medium"]}]
class CodexWakeupTests(unittest.TestCase):
    def test_account_read_handshake_only_never_starts_a_turn(self):
        script = '''import sys,json
for expected in ("initialize", "initialized", "account/read"):
 message=json.loads(sys.stdin.readline())
 assert message["method"]==expected
 if expected=="initialize": print(json.dumps({"id":message["id"],"result":{}}),flush=True)
 if expected=="account/read":
  assert message["params"]=={"refreshToken":False}
  print(json.dumps({"id":message["id"],"result":{"account":{"type":"chatgpt","email":"a@example.invalid"}}}),flush=True)
sys.stdin.read()
'''
        original = subprocess.Popen
        def start(command, **kwargs):
            self.assertEqual(command[1], "app-server")
            return original([sys.executable, "-u", "-c", script], **kwargs)
        with patch.object(cli.subprocess, "Popen", side_effect=start):
            self.assertEqual(cli.account_identity("codex", {}, Path(".")), "a@example.invalid")

    def test_identity_change_never_submits_prompt(self):
        collector = SimpleNamespace(cli_executable=lambda _: "codex", profile_lock=lambda _: contextlib.nullcontext(), profile_environment=lambda p: {}, profile_workdir=lambda p: Path("."))
        adapter = cli.build_adapter(collector, "available-luna", "low", CHOICES)
        with patch.object(cli, "account_identity", return_value="different@example.invalid"), patch.object(wakeup_cli, "run_guarded_once") as run:
            with self.assertRaises(ValueError): adapter.send({"id": "codex-0123456789", "wakeup_account_identity": "a@example.invalid"}, "say OK", "a"*32)
            run.assert_not_called()

    def test_send_now_uses_identity_metadata_and_postflight_reads_panel(self):
        collector = SimpleNamespace(cli_executable=lambda _: "codex", profile_lock=lambda _: contextlib.nullcontext(), profile_environment=lambda p: {}, profile_workdir=lambda p: Path("."))
        profile = {"id": "codex-0123456789", "provider": "codex", "wakeup_source": "manual"}
        with patch.object(cli, "require_model"), patch.object(cli, "account_identity", return_value="a@example.invalid"), patch.object(wakeup_cli, "collect_preflight", return_value={"panel":True}) as panel:
            adapter = cli.build_adapter(collector, "available-luna", "low", CHOICES)
            reading = adapter.preflight(profile)
            self.assertTrue(reading["identity_verified"])
            self.assertEqual(reading["window_state"], "unknown")
            panel.assert_not_called()
            self.assertEqual(adapter.postflight(profile), {"panel":True})
            panel.assert_called_once()

    def test_command_pins_user_choice_disables_retries_and_submits_one_prompt(self):
        command = cli.codex_command("codex", "available-luna", "medium", Path("instructions.md"))
        self.assertEqual(command.count("say OK"), 1)
        self.assertEqual(command[command.index("--model") + 1], "available-luna")
        values = dict(command[i+1].split("=", 1) for i,v in enumerate(command) if v == "-c")
        self.assertEqual(values["model_reasoning_effort"], '"medium"')
        self.assertEqual(values["model_providers.cyd-wakeup.request_max_retries"], "0")
        self.assertEqual(values["model_providers.cyd-wakeup.stream_max_retries"], "0")
        self.assertEqual(values["features.multi_agent"], "false")
        self.assertNotIn("--continue", command)
    def test_selected_adapter_sends_once_and_failure_is_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            collector = SimpleNamespace(cli_executable=lambda _:"codex", profile_lock=lambda _:contextlib.nullcontext(),
                collect_profile=lambda p:{"account_name":"a@example.invalid"}, profile_environment=lambda p:{}, profile_workdir=lambda p:Path(directory))
            profile={"id":"codex-0123456789","wakeup_account_identity":"a@example.invalid"}
            result=subprocess.CompletedProcess([],1,'{"type":"error","message":"unknown model"}\n',"")
            with patch.object(cli,"account_identity",return_value="a@example.invalid"), patch.object(wakeup_cli,"run_guarded_once",return_value=result) as run:
                adapter = cli.build_adapter(collector,catalogue=CHOICES).select("available-luna", "low")
                self.assertTrue(adapter.public()["available"])
                outcome=adapter.send(profile,"say OK","a"*32)
            self.assertEqual(outcome["state"],"failed")
            self.assertIn("unavailable",outcome["reason"])
            run.assert_called_once()
    def test_missing_binary_explains_setup(self):
        adapter=cli.build_adapter(SimpleNamespace(cli_executable=lambda _:None),catalogue=[])
        self.assertFalse(adapter.public()["available"])
    def test_separate_sender_binary_is_selected(self):
        seen=[]
        collector=SimpleNamespace(cli_executable=lambda _:"quota-codex", wakeup_cli_executable=lambda provider:seen.append(provider) or "current-codex")
        adapter=cli.build_adapter(collector,catalogue=CHOICES)
        self.assertTrue(adapter.public()["available"])
        self.assertEqual(seen,["codex"])

    def test_unknown_selection_never_falls_back(self):
        adapter=cli.build_adapter(SimpleNamespace(cli_executable=lambda _:"codex"),catalogue=CHOICES)
        with self.assertRaises(ValueError):adapter.select("other","low")
