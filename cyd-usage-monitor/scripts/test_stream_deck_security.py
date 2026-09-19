"""Windows transport regression tests using synthetic tokens and a local HTTP server.

Fixtures override only user-setting lookup to avoid reading operator credentials.
No real account selection or provider requests are made.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SCRIPTS = Path(__file__).parent


@unittest.skipUnless(sys.platform == "win32", "Windows COM helpers")
class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Select this machine's outbound interface without sending any datagram.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            cls.host = probe.getsockname()[0]
        cls.hits = []
        cls.redirect = False
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                cls.hits.append((self.path, self.headers.get("Authorization")))
                if cls.redirect:
                    self.send_response(302)
                    self.send_header("Location", f"http://{cls.host}:{self.server.server_port}/redirect-target")
                    self.end_headers()
                    return
                body = json.dumps({"account_name": "test", "accounts": []}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                cls.hits.append((self.path, self.headers.get("Authorization")))
                body = json.dumps({"status": "ok", "profile_id": data["profile_id"]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        cls.server = ThreadingHTTPServer((cls.host, 0), Handler)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.temp = tempfile.TemporaryDirectory()
        cls.fixture = Path(cls.temp.name)
        ps = (SCRIPTS / "stream-deck-next-account.ps1").read_text(encoding="utf8")
        ps = ps.replace('[Environment]::GetEnvironmentVariable($Name, "User")',
                        '[Environment]::GetEnvironmentVariable($Name, "Process")')
        (cls.fixture / "helper.ps1").write_text(ps, encoding="utf8")
        vbs = (SCRIPTS / "stream-deck-next-account.vbs").read_text(encoding="utf8")
        vbs = vbs.replace('shell.Environment("USER")', 'shell.Environment("PROCESS")')
        (cls.fixture / "helper.vbs").write_text(vbs, encoding="utf8")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()
        cls.temp.cleanup()

    def setUp(self):
        type(self).redirect = False
        self.hits.clear()

    def invoke(self, kind, endpoint=None, args=()):
        env = dict(os.environ, CYD_API_TOKEN="synthetic-device-token",
                   CYD_USAGE_MONITOR_NEXT_ACCOUNT_URL=endpoint or
                   f"http://{self.host}:{self.server.server_port}/api/v1/next-account",
                   HTTP_PROXY="http://127.0.0.1:1", HTTPS_PROXY="http://127.0.0.1:1")
        command = (["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                    "-File", str(self.fixture / "helper.ps1")] if kind == "ps" else
                   ["cscript.exe", "//B", "//NoLogo", str(self.fixture / "helper.vbs")])
        return subprocess.run(command + list(args), env=env, capture_output=True, timeout=15)

    def test_success_with_proxy_environment_and_direct_selection(self):
        for kind in ("ps", "vbs"):
            with self.subTest(kind=kind):
                self.assertEqual(self.invoke(kind).returncode, 0)
                args = ("-ProfileId", "codex-aaaaaaaaaa") if kind == "ps" else ("codex-aaaaaaaaaa",)
                self.assertEqual(self.invoke(kind, args=args).returncode, 0)
        self.assertEqual(len(self.hits), 4)
        self.assertTrue(all(token == "Bearer synthetic-device-token" for _, token in self.hits))
        self.assertEqual(self.invoke("ps", args=("-ListAccounts",)).returncode, 0)

    def test_redirect_is_never_followed_and_token_not_printed(self):
        type(self).redirect = True
        for kind in ("ps", "vbs"):
            result = self.invoke(kind)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(b"synthetic-device-token", result.stdout + result.stderr)
        self.assertEqual([path for path, _ in self.hits], ["/api/v1/next-account"] * 2)

    def test_invalid_endpoints_and_profile_rejected_before_network(self):
        for kind in ("ps", "vbs"):
            for endpoint in ("http://127.0.0.1/api/v1/next-account",
                             "http://010.0.0.1/api/v1/next-account",
                             "http://192.168.1.2:65536/api/v1/next-account",
                             "http://example.com/api/v1/next-account",
                             f"http://{self.host}:{self.server.server_port}/api/v1/next-account?token=x"):
                with self.subTest(kind=kind, endpoint=endpoint):
                    self.assertNotEqual(self.invoke(kind, endpoint).returncode, 0)
            args = ("-ProfileId", "invalid") if kind == "ps" else ("invalid",)
            self.assertNotEqual(self.invoke(kind, args=args).returncode, 0)
        self.assertEqual(self.hits, [])


if __name__ == "__main__":
    unittest.main()
