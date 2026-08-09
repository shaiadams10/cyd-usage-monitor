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
        self.assertIn(b'data-tab="flash"', dashboard)
        self.assertIn(b"pio run -e esp32-2432S028R", dashboard)
        self.assertNotIn(b"esp32-2432S028R-wokwi", dashboard)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        status, body, _ = self.request("/api/admin/cyd-status")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "error")

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

    def test_public_and_device_surfaces_are_isolated(self):
        self.assertEqual(self.request("/api/v1/cyd-status", basic=False, bearer=True)[0], 404)
        self.assertEqual(self.request("/", device=True)[0], 404)
        self.assertEqual(self.request("/api/v1/collector-status", device=True)[0], 404)

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
