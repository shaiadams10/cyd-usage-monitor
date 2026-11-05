import contextlib
import http.server
import json
import os
import subprocess
import sys
import time
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

try:
    from . import wakeup_cli as cli
    from .wakeups import WakeupError
except ImportError:
    import wakeup_cli as cli
    from wakeups import WakeupError


class WakeupCliTests(unittest.TestCase):
    def test_normalized_usage_windows_keep_resets_and_do_not_double_count_disabled_pool(self):
        sample = {"status":"ok", "account_name":"a@example.invalid", "collected_at":time.time(), "metrics":{"gemini":{"five_hour":{"remaining_pct":0,"reset":"Weekly limit reached"},"weekly":{"remaining_pct":0,"reset":"Nov 7, 11pm"}}}}
        reading = cli.normalize_snapshot({"provider":"antigravity","wakeup_model":"gemini-current"},sample)
        self.assertEqual([w["window"] for w in reading["quota_windows"]], ["weekly"])
        self.assertEqual(reading["quota_windows"][0]["reset_text"], "Nov 7, 11pm")
        sample["metrics"]["gemini"]["five_hour"]["reset"] = "9pm"
        self.assertEqual(len(cli.normalize_snapshot({"provider":"antigravity","wakeup_model":"gemini-current"},sample)["quota_windows"]),2)

    def test_manual_identity_reuses_only_fresh_same_account_quota(self):
        now = time.time()
        snapshot = {"status":"ok", "account_name":"a@example.invalid", "collected_at":now, "metrics":{"five_hour":{"remaining_pct":90,"reset":"20:11"}}}
        collector = SimpleNamespace(STATE_FILE=Path("unused"), read_json=lambda *args: {"profiles":{"codex-0123456789":snapshot}})
        profile = {"id":"codex-0123456789", "provider":"codex"}
        reading = cli.manual_identity_reading(collector, profile, "a@example.invalid")
        self.assertEqual(reading["window_reset_text"], "20:11")
        for changes in ({"collected_at":now-121}, {"status":"error"}, {"stale":True}, {"retrying":True}, {"account_name":"other@example.invalid"}):
            with self.subTest(changes=changes):
                original = snapshot.copy(); snapshot.update(changes)
                reading = cli.manual_identity_reading(collector, profile, "a@example.invalid")
                self.assertEqual(reading["window_state"], "unknown")
                self.assertFalse(reading["window_reset_text"])
                self.assertTrue(reading["identity_verified"])
                snapshot.clear(); snapshot.update(original)

    def test_claude_environment_drops_inherited_routing_and_disables_resends(self):
        env = cli.claude_environment({"HOME": "/private/profile", "CLAUDE_CONFIG_DIR": "/private/config", "ANTHROPIC_API_KEY": "never-use", "ANTHROPIC_BASE_URL": "https://invalid", "ANTHROPIC_MODEL": "expensive", "CLAUDE_CODE_RETRY_WATCHDOG": "1", "CLAUDE_CODE_SIMPLE": "1"})
        self.assertFalse(any(key.startswith("ANTHROPIC_") for key in env))
        self.assertNotIn("CLAUDE_CODE_SIMPLE", env)
        for key in ("CLAUDE_CODE_MAX_RETRIES", "CLAUDE_CODE_NONSTREAMING_TIMEOUT_RETRIES", "CLAUDE_CODE_RETRY_WATCHDOG"):
            self.assertEqual(env[key], "0")
        self.assertEqual(env["CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK"], "1")
        self.assertEqual(env["CLAUDE_CODE_MAX_TURNS"], "1")
        self.assertEqual(env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"], "16")
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], "/private/config")

    def test_claude_command_fixed_prompt_no_tools_or_paid_fallback(self):
        command = cli.claude_command("claude", "a" * 32)
        self.assertEqual(command[command.index("--print") + 1], "say OK")
        self.assertEqual(command[command.index("--tools") + 1], "")
        self.assertNotIn("--bare", command)
        self.assertEqual(command[command.index("--effort") + 1], "low")
        settings = json.loads(command[command.index("--settings") + 1])
        self.assertEqual(settings["availableModels"], [cli.CLAUDE_MODEL])
        self.assertEqual(settings["fallbackModel"], [])

    def test_normalization_only_trusts_explicit_idle_and_official_identity(self):
        profile = {"provider": "codex"}
        snapshot = {"status": "ok", "account_name": "a@example.invalid", "collected_at": "2026-11-04T12:00:00Z", "metrics": {"five_hour": {"remaining_pct": 100, "reset": ""}, "weekly": {"remaining_pct": 50}}}
        reading = cli.normalize_snapshot(profile, snapshot)
        self.assertEqual(reading["window_state"], "unknown")
        self.assertTrue(reading["identity_verified"])
        snapshot["metrics"]["five_hour"]["reset"] = "20:11"
        self.assertEqual(cli.normalize_snapshot(profile,snapshot)["window_state"],"unknown")
        snapshot["metrics"]["five_hour"]["reset"] = "Quota available"
        self.assertEqual(cli.normalize_snapshot(profile, snapshot)["window_state"], "idle")
        snapshot["retrying"] = True
        self.assertEqual(cli.normalize_snapshot(profile, snapshot)["window_state"], "unknown")
        snapshot["account_name"] = "Claude Code"
        self.assertFalse(cli.normalize_snapshot(profile, snapshot)["identity_verified"])

    def test_antigravity_uses_selected_models_quota_pool(self):
        sample={"status":"ok","account_name":"a@example.invalid","collected_at":"2026-11-04T12:00:00Z","metrics":{
            "gemini":{"five_hour":{"remaining_pct":100,"reset":"Quota available"},"weekly":{"remaining_pct":90}},
            "claude":{"five_hour":{"remaining_pct":0,"reset":"Weekly limit reached"},"weekly":{"remaining_pct":0}}}}
        gemini=cli.normalize_snapshot({"provider":"antigravity","wakeup_model":"gemini-current"},sample)
        claude=cli.normalize_snapshot({"provider":"antigravity","wakeup_model":"claude-current"},sample)
        unknown=cli.normalize_snapshot({"provider":"antigravity","wakeup_model":"unknown"},sample)
        self.assertEqual(gemini["weekly_remaining_pct"],90);self.assertEqual(gemini["window_state"],"idle")
        self.assertEqual(claude["weekly_remaining_pct"],0);self.assertEqual(claude["window_state"],"active")
        self.assertIsNone(unknown["weekly_remaining_pct"]);self.assertEqual(unknown["window_state"],"unknown")

    def test_claude_sender_rechecks_identity_and_validates_one_turn(self):
        collector = SimpleNamespace(cli_executable=lambda provider: __file__, profile_lock=lambda _: contextlib.nullcontext(),
                                    profile_environment=lambda p: {}, profile_workdir=lambda p: Path("."),
                                    claude_account_status=lambda *a: {"account_name": "a@example.invalid"})
        profile = {"id": "claude-0123456789", "wakeup_account_identity": "a@example.invalid"}
        with mock.patch.object(cli, "_claude_supported", return_value=True): adapter = cli.build_claude_adapter(collector,catalogue=[{"id":cli.CLAUDE_MODEL,"label":"Haiku","reasoning_levels":["low"]}])
        with mock.patch.object(cli, "run_once", return_value=subprocess.CompletedProcess([], 0, json.dumps({"is_error": False, "num_turns": 1, "modelUsage": {cli.CLAUDE_MODEL: {}}}), "")) as run:
            self.assertEqual(adapter.send(profile, "say OK", "a" * 32), {"state": "sent"})
            self.assertEqual(run.call_count, 1)
        with mock.patch.object(cli, "run_once") as run:
            with self.assertRaises(WakeupError): adapter.send(dict(profile, wakeup_account_identity="b@example.invalid"), "say OK", "a" * 32)
            run.assert_not_called()
        with mock.patch.object(cli, "run_once", return_value=subprocess.CompletedProcess([], 0, '{"is_error":false,"num_turns":2}', "")) as run:
            self.assertEqual(adapter.send(profile, "say OK", "a" * 32)["state"], "unknown")
            self.assertEqual(run.call_count, 1)


class CustomPromptTests(unittest.TestCase):
    def test_custom_prompt_is_one_literal_argument_for_all_providers(self):
        try:
            from .wakeup_codex import codex_command
        except ImportError:
            from wakeup_codex import codex_command
        prompt = 'Reply "hello"; $(literal) `literal`\nNo tools.'
        commands = [cli.claude_command("claude", "a" * 32, prompt=prompt),
                    cli.antigravity_command("agy", "flash", "low", prompt),
                    codex_command("codex", "luna", "low", Path("instructions.md"), prompt)]
        for command in commands:
            self.assertEqual(command.count(prompt), 1)
            self.assertNotIn("say OK", command)
        codex = codex_command("codex", "luna", "low", Path("instructions.md"), "resume")
        self.assertEqual(codex[-2:], ["--", "resume"])

class GuardedPromptTests(unittest.TestCase):
    def test_deadline_stops_hanging_process_without_resubmission(self):
        with tempfile.TemporaryDirectory() as directory:
            started=time.monotonic()
            result=cli.run_guarded_once([sys.executable,"-u","-c","import time; print('started',flush=True); time.sleep(15)"],dict(os.environ),Path(directory),timeout=.2)
        self.assertNotEqual(result.returncode,0)
        self.assertLess(time.monotonic()-started,3)
        self.assertEqual(result.stdout.count("started"),1)
    def test_retry_and_nested_tool_activity_stops_cli(self):
        for event in ({"type":"error","message":"rate limited"},{"type":"item.started","item":{"type":"command_execution"}}):
            with self.subTest(event=event),tempfile.TemporaryDirectory() as directory:
                script="import time; print("+repr(json.dumps(event))+",flush=True); time.sleep(15)"
                started=time.monotonic();result=cli.run_guarded_once([sys.executable,"-u","-c",script],dict(os.environ),Path(directory),timeout=5)
                self.assertNotEqual(result.returncode,0);self.assertLess(time.monotonic()-started,3)
    def test_antigravity_command_submits_exactly_one_fixed_prompt(self):
        command=cli.antigravity_command("agy","current-flash","medium")
        self.assertEqual(command.count("say OK"),1)
        self.assertEqual(command[command.index("--model")+1],"current-flash")
        self.assertEqual(command[command.index("--effort")+1],"medium")
        self.assertNotIn("--continue",command)
        with tempfile.TemporaryDirectory() as directory:
            cli.antigravity_agent(Path(directory));text=(Path(directory)/".agents/agents/cyd-wakeup.md").read_text()
            self.assertIn("tools: []",text);self.assertIn("inheritMcp: false",text)
    def test_antigravity_native_result_envelope_and_failure_are_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            collector=SimpleNamespace(cli_executable=lambda _:"agy",profile_lock=lambda _:contextlib.nullcontext(),
                collect_profile=lambda p:{"account_name":"a@example.invalid"},profile_environment=lambda p:{"HOME":directory},profile_workdir=lambda p:Path(directory))
            catalogue=[{"id":"flash-current","label":"Flash","reasoning_levels":["low","medium"]}]
            adapter=cli.build_antigravity_adapter(collector,catalogue=catalogue).select("flash-current","medium")
            profile={"id":"antigravity-0123456789","wakeup_account_identity":"a@example.invalid"}
            result=subprocess.CompletedProcess([],0,'{"event":"result","result":{"status":"SUCCESS","num_turns":1}}\n',"")
            with mock.patch.object(cli,"run_guarded_once",return_value=result) as run:
                self.assertEqual(adapter.send(profile,"say OK","a"*32),{"state":"sent"})
                run.assert_called_once()
            result=subprocess.CompletedProcess([],1,'{"event":"result","result":{"status":"ERROR","error":"unknown model"}}\n',"")
            with mock.patch.object(cli,"run_guarded_once",return_value=result) as run:
                outcome=adapter.send(profile,"say OK","b"*32)
                self.assertEqual(outcome["state"],"failed");self.assertIn("unavailable",outcome["reason"]);run.assert_called_once()
    def test_failure_classification_never_exposes_provider_transcript(self):
        reason=cli.safe_cli_reason("Antigravity","unknown model https://secret.invalid token=secret-personal-token","failed")
        self.assertIn("selected model is unavailable",reason)
        self.assertNotIn("secret",reason)


@unittest.skipUnless(os.environ.get("CYD_TEST_NATIVE_CLAUDE") == "1", "Optional native CLI loopback safety probe")
class NativeClaudeSafetyTests(unittest.TestCase):
    """Only fake local keys/endpoints. Never authenticate or call a provider."""
    def test_single_request_success_failure_truncation_and_tool_continuation(self):
        executable = os.environ.get("CYD_TEST_NATIVE_CLAUDE_BIN", str(Path.home() / ".local" / "bin" / ("claude.exe" if os.name == "nt" else "claude")))
        self.assertTrue(cli._claude_supported(executable, Path(executable).stat().st_mtime_ns))
        for scenario in ("success", "502", "429", "529", "drop", "tool"):
            with self.subTest(scenario=scenario):
                self.probe(executable, scenario)

    def probe(self, executable, scenario):
        calls = []
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                body = json.loads(raw)
                calls.append(body)
                if scenario in {"502", "429", "529"}:
                    reply = json.dumps({"type": "error", "error": {"type": "overloaded_error" if scenario == "529" else "rate_limit_error" if scenario == "429" else "api_error", "message": "synthetic error"}}).encode()
                    self.send_response(int(scenario)); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(reply))); self.send_header("retry-after", "0"); self.end_headers(); self.wfile.write(reply)
                    return
                self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.send_header("Connection", "close"); self.end_headers()
                def emit(kind, data):
                    self.wfile.write(("event: " + kind + "\ndata: " + json.dumps(dict(data, type=kind)) + "\n\n").encode()); self.wfile.flush()
                emit("message_start", {"message": {"id": "msg_synthetic", "type": "message", "role": "assistant", "content": [], "model": cli.CLAUDE_MODEL, "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 5, "output_tokens": 0}}})
                if scenario == "tool":
                    emit("content_block_start", {"index": 0, "content_block": {"type": "tool_use", "id": "tool_synthetic", "name": "Bash", "input": {}}})
                    emit("content_block_delta", {"index": 0, "delta": {"type": "input_json_delta", "partial_json": '{"command":"echo forbidden"}'}})
                else:
                    emit("content_block_start", {"index": 0, "content_block": {"type": "text", "text": ""}})
                    emit("content_block_delta", {"index": 0, "delta": {"type": "text_delta", "text": "okay"}})
                if scenario != "drop":
                    emit("content_block_stop", {"index": 0})
                    emit("message_delta", {"delta": {"stop_reason": "tool_use" if scenario == "tool" else "end_turn", "stop_sequence": None}, "usage": {"output_tokens": 1}})
                    emit("message_stop", {})
                self.close_connection = True
            def do_GET(self):
                self.send_response(200); self.send_header("Content-Length", "2"); self.end_headers(); self.wfile.write(b"{}")
            def log_message(self, *args): pass
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                baseline = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP") if key in os.environ}
                baseline.update(HOME=directory, USERPROFILE=directory, CLAUDE_CONFIG_DIR=directory)
                env = cli.claude_environment(baseline)
                env.update(ANTHROPIC_API_KEY="synthetic-local-key", ANTHROPIC_BASE_URL=f"http://127.0.0.1:{server.server_port}")
                result = cli.run_once(cli.claude_command(executable, "a" * 32), env, Path(directory), timeout=20)
                self.assertEqual(len(calls), 1, f"{scenario} caused duplicate model requests")
                self.assertEqual(calls[0]["model"], cli.CLAUDE_MODEL)
                self.assertEqual(calls[0].get("tools", []), [])
                self.assertEqual(calls[0]["max_tokens"], 16)
                if scenario == "success":
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(json.loads(result.stdout)["num_turns"], 1)
                else:
                    self.assertNotEqual(result.returncode, 0)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)


if __name__ == "__main__": unittest.main()
