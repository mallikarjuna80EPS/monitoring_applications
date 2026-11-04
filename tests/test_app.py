import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

from werkzeug.security import check_password_hash

from app import create_app


class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.config_path = root / "config.json"
        self.servers_path = root / "servers.json"
        self.secret_path = root / "secret"
        self.app = create_app(
            config_path=self.config_path,
            servers_path=self.servers_path,
            secret_path=self.secret_path,
        )
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def login(self, username="admin", password="admin", **extra):
        data = {"username": username, "password": password}
        data.update(extra)
        return self.client.post("/", data=data)

    def test_good_login(self):
        response = self.login(role="root")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/servers", response.headers["Location"])
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("user"), "admin")
            self.assertNotIn("role", sess)
        page = self.client.get("/servers")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Add server", page.data)

    def test_bad_login(self):
        wrong_password = self.login(password="wrong")
        self.assertEqual(wrong_password.status_code, 200)
        self.assertIn(b"Invalid username or password.", wrong_password.data)
        self.assertIn(b"Sign in", wrong_password.data)
        with self.client.session_transaction() as sess:
            self.assertNotIn("user", sess)
        servers = self.client.get("/servers")
        self.assertEqual(servers.status_code, 302)
        self.assertEqual(urlparse(servers.headers["Location"]).path, "/")

        wrong_user = self.login(username="root", password="admin")
        self.assertEqual(wrong_user.status_code, 200)
        self.assertIn(b"Invalid username or password.", wrong_user.data)
        self.assertEqual(self.client.get("/servers").status_code, 302)

    def test_config_stores_a_hash(self):
        self.assertTrue(str(self.config_path).startswith(self.tmp.name))
        raw = self.config_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        self.assertEqual(data["username"], "admin")
        self.assertTrue(data["password_hash"].startswith("pbkdf2:"))
        self.assertNotIn("password", data)
        self.assertNotEqual(data["password_hash"], "admin")
        self.assertTrue(check_password_hash(data["password_hash"], "admin"))
        self.assertFalse(check_password_hash(data["password_hash"], "wrong"))
        repo_config = Path(__file__).resolve().parents[1] / "config.json"
        self.assertNotEqual(self.config_path.resolve(), repo_config)

    def test_sign_out(self):
        self.login()
        response = self.client.post("/sign-out")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlparse(response.headers["Location"]).path, "/")
        with self.client.session_transaction() as sess:
            self.assertNotIn("user", sess)
        servers = self.client.get("/servers")
        self.assertEqual(servers.status_code, 302)

    def test_unsigned_visitor_only_sees_sign_in(self):
        for path in ("/servers", "/metrics", "/servers/abc/metrics"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(urlparse(response.headers["Location"]).path, "/")
        sign_in = self.client.get("/")
        self.assertEqual(sign_in.status_code, 200)
        self.assertIn(b"Sign in", sign_in.data)
        self.assertNotIn(b"Add server", sign_in.data)

    def test_empty_server_file_shows_empty_list(self):
        self.servers_path.write_text("", encoding="utf-8")
        self.login()
        page = self.client.get("/servers")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"No servers yet.", page.data)

    def test_add_requires_both_fields_and_ignores_extra(self):
        self.login()
        missing = self.client.post("/servers", data={"display_name": "Lab", "hostname": "   "})
        self.assertEqual(missing.status_code, 200)
        self.assertIn(b"both required", missing.data)
        self.assertFalse(self.servers_path.exists())

        saved = self.client.post(
            "/servers",
            data={
                "display_name": "Nowhere",
                "hostname": "no-such-host.invalid",
                "command": "ssh root@no-such-host.invalid",
                "port": "22",
            },
            follow_redirects=True,
        )
        self.assertEqual(saved.status_code, 200)
        self.assertIn(b"Nowhere", saved.data)
        self.assertIn(b"no-such-host.invalid", saved.data)
        on_disk = json.loads(self.servers_path.read_text(encoding="utf-8"))
        self.assertEqual(list(on_disk[0].keys()), ["id", "name", "hostname"])
        self.assertEqual(on_disk[0]["hostname"], "no-such-host.invalid")
        self.assertNotIn(b"ssh root", saved.data)

    def test_names_render_as_text(self):
        self.login()
        self.client.post(
            "/servers",
            data={"display_name": "<script>alert(1)</script>", "hostname": "<b>10.0.0.8</b>"},
        )
        page = self.client.get("/servers")
        self.assertNotIn(b"<script>alert", page.data)
        self.assertIn(b"&lt;script&gt;alert(1)&lt;/script&gt;", page.data)
        self.assertIn(b"&lt;b&gt;10.0.0.8&lt;/b&gt;", page.data)

    def test_remove_server_and_list_survives_new_process(self):
        self.login()
        self.client.post("/servers", data={"display_name": "Lab", "hostname": "10.1.1.1"})
        self.client.post("/servers", data={"display_name": "Other", "hostname": "10.1.1.2"})
        saved = json.loads(self.servers_path.read_text(encoding="utf-8"))
        self.client.post(f"/servers/{saved[0]['id']}/remove")
        remaining = json.loads(self.servers_path.read_text(encoding="utf-8"))
        self.assertEqual([item["name"] for item in remaining], ["Other"])

        again = create_app(
            config_path=self.config_path,
            servers_path=self.servers_path,
            secret_path=self.secret_path,
        )
        again.config["TESTING"] = True
        client = again.test_client()
        client.post("/", data={"username": "admin", "password": "admin"})
        page = client.get("/servers")
        self.assertIn(b"Other", page.data)
        self.assertNotIn(b">Lab<", page.data)

    def test_no_password_change_or_extra_account_routes(self):
        self.login()
        for path in ("/register", "/password", "/users", "/account"):
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_metrics_page_is_read_only_local_snapshot(self):
        self.login()
        self.client.post("/servers", data={"display_name": "Lab", "hostname": "10.2.2.2"})
        server_id = json.loads(self.servers_path.read_text(encoding="utf-8"))[0]["id"]
        page = self.client.get(f"/servers/{server_id}/metrics")
        self.assertEqual(page.status_code, 200)
        body = page.data.decode()
        self.assertIn("Lab", body)
        self.assertIn("10.2.2.2", body)
        self.assertIn("percent", body)
        self.assertIn("Listening ports", body)
        self.assertIn("totals until a rate is available", body)
        self.assertIn("setInterval(refresh, 5000)", body)
        self.assertNotIn("<input", body)
        self.assertNotIn("<textarea", body)
        self.assertNotIn("Refresh", body)
        self.assertNotRegex(body, r"10\.2\.2\.2.+(connect|ssh)")

    def test_metrics_refresh_requires_session(self):
        anonymous = self.client.get("/api/metrics?hostname=example.com")
        self.assertEqual(anonymous.status_code, 401)
        self.assertEqual(anonymous.get_json(), {"error": "Sign in required."})
        self.login()
        response = self.client.get("/api/metrics?hostname=example.com")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertIn("cpu_percent", body)
        self.assertIn("memory_used_label", body)
        self.assertIn("memory_total_label", body)
        self.assertIn("net_recv_label", body)
        self.assertIn("net_sent_label", body)
        self.assertIn("ports", body)
        self.assertNotIn("hostname", body)
        self.assertNotIn("password", body)
        self.assertNotIn("password_hash", body)
        self.assertNotIn("example.com", json.dumps(body))

    def test_metrics_collection_error_keeps_layout(self):
        self.login()
        self.client.post("/servers", data={"display_name": "Lab", "hostname": "10.9.9.9"})
        server_id = json.loads(self.servers_path.read_text(encoding="utf-8"))[0]["id"]
        with patch("app.collect_snapshot", side_effect=RuntimeError("disk")):
            page = self.client.get(f"/servers/{server_id}/metrics")
            api = self.client.get("/api/metrics")
        self.assertEqual(page.status_code, 200)
        text = page.data.decode()
        self.assertRegex(text, r'id="metrics-error"[^>]*>Could not collect metrics\.</p>')
        self.assertIn("Listening ports", text)
        self.assertIn("Lab", text)
        self.assertIn("10.9.9.9", text)
        self.assertIn("Back to servers", text)
        self.assertIn('id="cpu-value"', text)
        self.assertEqual(api.status_code, 500)
        self.assertEqual(api.get_json(), {"error": "Could not collect metrics."})


if __name__ == "__main__":
    unittest.main()
