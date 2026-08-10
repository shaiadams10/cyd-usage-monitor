import base64
import http.client
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path


_TEMP = tempfile.TemporaryDirectory()
os.environ["CYD_MONITOR_DATA_DIR"] = _TEMP.name
os.environ["MONITOR_ADMIN_PASSWORD"] = "test-admin-password-long-enough"
os.environ["CYD_API_TOKEN"] = "test-device-token-long-enough-1234"
os.environ["CYD_MONITOR_POLL_SECONDS"] = "90"

try:
    from . import collector
    from . import server as app
except ImportError:
    import collector
    import server as app


class QuietHandler(app.Handler):
    def log_message(self, _format, *_args):
        pass


class ServerApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = app.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.httpd.surface = "dashboard"
        cls.device_httpd = app.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.device_httpd.surface = "device"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.device_thread = threading.Thread(target=cls.device_httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.device_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.httpd.server_port}"
        cls.device_base_url = f"http://127.0.0.1:{cls.device_httpd.server_port}"
        cls.basic = "Basic " + base64.b64encode(b"admin:test-admin-password-long-enough").decode("ascii")

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.device_httpd.shutdown()
        cls.httpd.server_close()
        cls.device_httpd.server_close()
        cls.thread.join(timeout=5)
        cls.device_thread.join(timeout=5)
        _TEMP.cleanup()

    def setUp(self):
        self.profile = {
            "id": "codex-0123456789", "provider": "codex", "label": "Demo account",
            "enabled": True, "created_at": app.utcnow(),
        }
        app.write_json(app.PROFILES_FILE, {"profiles": [self.profile], "active_profile_id": self.profile["id"]})
        app.write_json(app.CONTROL_FILE, {"requests": []})
        app.write_json(app.RUNTIME_FILE, {"requests": {}})
        app.write_json(app.STATE_FILE, {"profiles": {}})
        for target in (app.OPENROUTER_SECRET_FILE, app.OPENROUTER_STATE_FILE, app.INCIDENTS_FILE):
            try:
                target.unlink()
            except FileNotFoundError:
                pass

    def request(self, path, *, method="GET", payload=None, basic=True, csrf=False, bearer=False, device=False, content_type="application/json"):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        base_url = self.device_base_url if device else self.base_url
        request = urllib.request.Request(base_url + path, data=data, method=method)
        if basic:
            request.add_header("Authorization", self.basic)
        if bearer:
            request.add_header("Authorization", "Bearer test-device-token-long-enough-1234")
        if data is not None:
            request.add_header("Content-Type", content_type)
        if csrf:
            request.add_header("X-CYD-CSRF", "1")
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        try:
            raw = response.read()
            headers = dict(response.headers.items())
            body = json.loads(raw) if raw and "application/json" in response.headers.get("Content-Type", "") else raw
            return response.status, body, headers
        finally:
            response.close()

    def test_dashboard_and_admin_preview_use_basic_auth(self):
        status, dashboard, headers = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b'data-tab="utilities"', dashboard)
        self.assertIn(b"Keyboard touch shortcuts", dashboard)
        self.assertIn(b"Usage Monitor", dashboard)
        self.assertIn(b"OpenRouter account", dashboard)
        self.assertIn(b"cyd_set_openrouter", dashboard)
        self.assertIn(b"openrouterForm", dashboard)
        self.assertIn(b"OpenRouter key saved privately", dashboard)
        self.assertIn(b"Next account", dashboard)
        self.assertIn(b"pio run -e esp32-2432S028R", dashboard)
        self.assertNotIn(b"esp32-2432S028R-wokwi", dashboard)
        self.assertIn(b"Interactive simulated CYD screen", dashboard)
        self.assertIn(b'class="preview-device"', dashboard)
        self.assertIn(b'class="preview-details"', dashboard)
        self.assertIn(b"width:340px; height:255px", dashboard)
        self.assertIn(b"@media(max-width:1050px)", dashboard)
        self.assertIn(b"cyd_pointer", dashboard)
        self.assertIn(b"pointerdown", dashboard)
        self.assertIn(b"window.cydPreviewNextAccount", dashboard)
        self.assertIn(b'class="button remove compact hidden"', dashboard)
        self.assertIn(b"Incident history", dashboard)
        self.assertIn(b"host evidence", dashboard)
        self.assertNotIn(b"account-meta", dashboard)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        status, body, _ = self.request("/api/admin/cyd-status")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "error")

    def test_collector_status_returns_structured_incidents_without_transcripts(self):
        app.write_json(app.INCIDENTS_FILE, {"incidents": [{
            "id": "safe-id", "profile_id": self.profile["id"], "provider": "codex",
            "account": "Demo account", "status": "recovered", "started_at": "2026-08-10T00:53:00Z",
            "recovered_at": "2026-08-10T00:54:30Z", "failed_polls": 1,
            "explanation": "The status panel was incomplete.", "diagnostics": {"nonempty_lines": 12, "evidence_id": "abc123"},
        }]})
        status, body, _ = self.request("/api/v1/collector-status")
        self.assertEqual(status, 200)
        self.assertEqual(body["incidents"]["incidents"][0]["diagnostics"]["evidence_id"], "abc123")
        self.assertNotIn("transcript", json.dumps(body).lower())

    def test_wasm_usage_controls_stay_above_antigravity_content(self):
        source = (Path(__file__).resolve().parents[1] / "simulator" / "lvgl_cyd_sim.c").read_text(encoding="utf-8")
        self.assertIn("lv_obj_add_event_cb(next_button, next_account_event", source)
        self.assertIn("lv_obj_clear_flag(grid, LV_OBJ_FLAG_CLICKABLE)", source)
        self.assertIn("lv_obj_move_background(grid)", source)

    def test_flashing_guide_is_admin_protected_and_available(self):
        self.assertEqual(self.request("/docs/flashing-guide", basic=False)[0], 401)
        status, body, headers = self.request("/docs/flashing-guide")
        self.assertEqual(status, 200)
        self.assertTrue(headers["Content-Type"].startswith("text/html"))
        self.assertIn(b"# Flashing a CYD Device", body)
        self.assertIn(b"pio run -e esp32-2432S028R", body)
        self.assertNotIn(b"esp32-2432S028R-wokwi", body)
        self.assertNotIn(b"CYD_API_TOKEN=", body)

    def test_device_endpoint_remains_bearer_only(self):
        self.assertEqual(app.Handler.protocol_version, "HTTP/1.1")
        self.assertEqual(self.request("/api/v1/cyd-status", device=True)[0], 401)
        self.assertEqual(self.request("/api/v1/cyd-status", basic=False, bearer=True, device=True)[0], 200)
        self.assertEqual(self.request("/api/v1/openrouter-status", device=True)[0], 401)
        status, body, _ = self.request("/api/v1/openrouter-status", basic=False, bearer=True, device=True)
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "unconfigured")

    def test_public_and_device_surfaces_are_isolated(self):
        self.assertEqual(self.request("/api/v1/cyd-status", basic=False, bearer=True)[0], 404)
        self.assertEqual(self.request("/", device=True)[0], 404)
        self.assertEqual(self.request("/api/v1/collector-status", device=True)[0], 404)
        self.assertEqual(self.request("/api/v1/openrouter-status", basic=False, bearer=True)[0], 404)
        self.assertEqual(self.request("/api/admin/openrouter-status", device=True)[0], 404)

    def test_openrouter_secret_setup_is_private_and_removable(self):
        secret = "management-secret-that-must-never-be-returned"
        path = "/api/admin/openrouter-config"
        payload = {"key": secret, "label": "Personal Router"}
        self.assertEqual(self.request(path, method="POST", payload=payload)[0], 403)
        status, body, _ = self.request(path, method="POST", payload=payload, csrf=True)
        self.assertEqual(status, 202)
        self.assertNotIn(secret, json.dumps(body))
        self.assertEqual(app.read_json(app.OPENROUTER_SECRET_FILE, {})["key"], secret)
        if os.name != "nt":
            self.assertEqual(app.OPENROUTER_SECRET_FILE.stat().st_mode & 0o777, 0o600)
        status, public, _ = self.request("/api/v1/collector-status")
        self.assertEqual(status, 200)
        self.assertNotIn(secret, json.dumps(public))
        self.assertTrue(public["openrouter"]["configured"])

        status, removed, _ = self.request(
            "/api/admin/remove-openrouter-config", method="POST", payload={}, csrf=True,
        )
        self.assertEqual(status, 200)
        self.assertFalse(removed["configured"])
        self.assertFalse(app.OPENROUTER_SECRET_FILE.exists())

    def test_openrouter_payload_sanitizes_stale_and_error_state(self):
        app.write_json(app.OPENROUTER_SECRET_FILE, {"key": "private", "label": "Router"})
        app.write_json(app.OPENROUTER_STATE_FILE, {
            "provider": "openrouter", "status": "ok", "account_label": "Router",
            "remaining_credits": 4.5, "collected_at": "2020-01-01T00:00:00Z",
        })
        status, body, _ = self.request("/api/admin/openrouter-status")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "error")
        self.assertIn("stale", body["error"])

    def test_next_account_returns_the_new_display_payload(self):
        second = {
            "id": "codex-9876543210", "provider": "codex", "label": "Second account",
            "enabled": True, "created_at": app.utcnow(),
        }
        app.write_json(app.PROFILES_FILE, {
            "profiles": [self.profile, second], "active_profile_id": self.profile["id"],
        })
        status, body, _ = self.request("/api/v1/next-account", basic=False, bearer=True, device=True)
        self.assertEqual(status, 200)
        self.assertEqual(body["provider"], "error")
        self.assertIn("Waiting for the CLI collector", body["primary_sub"])
        self.assertEqual(app.profiles_config()["active_profile_id"], second["id"])

    def test_device_requests_reuse_one_http11_connection(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.device_httpd.server_port, timeout=5)
        headers = {"Authorization": "Bearer test-device-token-long-enough-1234"}
        try:
            connection.request("GET", "/api/v1/cyd-status", headers=headers)
            first = connection.getresponse()
            self.assertEqual(first.status, 200)
            first.read()
            socket = connection.sock

            connection.request("GET", "/api/v1/cyd-status", headers=headers)
            second = connection.getresponse()
            self.assertEqual(second.status, 200)
            second.read()
            self.assertIs(connection.sock, socket)
        finally:
            connection.close()

    def test_admin_posts_require_csrf_header_and_json(self):
        path = "/api/admin/profiles"
        payload = {"provider": "codex", "label": "Second account"}
        self.assertEqual(self.request(path, method="POST", payload=payload)[0], 403)
        self.assertEqual(self.request(path, method="POST", payload=payload, csrf=True, content_type="text/plain")[0], 415)
        status, body, _ = self.request(path, method="POST", payload=payload, csrf=True)
        self.assertEqual(status, 201)
        self.assertEqual(body["label"], "Second account")

    def test_authorization_input_is_private_and_consumed_once(self):
        request_id = "00000000-0000-4000-8000-000000000002"
        app.write_json(app.RUNTIME_FILE, {"requests": {request_id: {
            "kind": "login", "status": "running", "phase": "awaiting_browser",
            "profile_id": self.profile["id"],
        }}})
        secret_value = "temporary-authorization-value"
        status, _, _ = self.request(
            "/api/admin/login-input", method="POST",
            payload={"request_id": request_id, "value": secret_value}, csrf=True,
        )
        self.assertEqual(status, 200)
        status, body, _ = self.request("/api/v1/collector-status")
        self.assertEqual(status, 200)
        self.assertNotIn(secret_value, json.dumps(body))

        previous_dir = collector.LOGIN_INPUT_DIR
        collector.LOGIN_INPUT_DIR = app.LOGIN_INPUT_DIR
        try:
            self.assertEqual(collector.consume_login_input(request_id), secret_value)
            self.assertEqual(collector.consume_login_input(request_id), "")
        finally:
            collector.LOGIN_INPUT_DIR = previous_dir

    def test_remove_profile_deletes_collector_credentials(self):
        profile_root = Path(_TEMP.name) / "profiles"
        profile_dir = profile_root / self.profile["id"]
        profile_dir.mkdir(parents=True, exist_ok=True)
        (profile_dir / "credential.json").write_text("private", encoding="utf-8")

        status, body, _ = self.request(
            "/api/admin/remove-profile", method="POST",
            payload={"profile_id": self.profile["id"]}, csrf=True,
        )
        self.assertEqual(status, 202)

        saved = {
            "DATA_DIR": collector.DATA_DIR, "PROFILES_FILE": collector.PROFILES_FILE,
            "CONTROL_FILE": collector.CONTROL_FILE, "RUNTIME_FILE": collector.RUNTIME_FILE,
            "STATE_FILE": collector.STATE_FILE, "PROFILE_ROOT": collector.PROFILE_ROOT,
        }
        collector.DATA_DIR = app.DATA_DIR
        collector.PROFILES_FILE = app.PROFILES_FILE
        collector.CONTROL_FILE = app.CONTROL_FILE
        collector.RUNTIME_FILE = app.RUNTIME_FILE
        collector.STATE_FILE = app.STATE_FILE
        collector.PROFILE_ROOT = profile_root
        try:
            collector.process_requests({})
        finally:
            for name, value in saved.items():
                setattr(collector, name, value)
        self.assertFalse(profile_dir.exists())
        runtime = app.read_json(app.RUNTIME_FILE, {"requests": {}})["requests"][body["request_id"]]
        self.assertEqual(runtime["status"], "completed")


if __name__ == "__main__":
    unittest.main()
