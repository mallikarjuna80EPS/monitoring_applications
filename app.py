import json
import secrets
import threading
import time
from pathlib import Path

import psutil
from flask import Flask, abort, current_app, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = ROOT / "config.json"
DEFAULT_SERVERS_PATH = ROOT / "servers.json"
DEFAULT_SECRET_PATH = ROOT / ".session_secret"
USERNAME = "admin"
DEMO_PASSWORD = "admin"
METRICS_ERROR = "Could not collect metrics."
PUBLIC_ENDPOINTS = {"sign_in", "sign_out", "static"}


def human_bytes(amount):
    value = float(amount)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{value:.0f} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def write_private(path, text):
    path.write_text(text, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def load_or_create_config(path):
    if path.is_file() and path.stat().st_size > 0:
        return json.loads(path.read_text(encoding="utf-8"))
    data = {
        "username": USERNAME,
        "password_hash": generate_password_hash(DEMO_PASSWORD, method="pbkdf2:sha256"),
    }
    write_private(path, json.dumps(data, indent=2) + "\n")
    return data


def load_or_create_secret(path):
    if path.is_file():
        secret = path.read_text(encoding="utf-8").strip()
        if secret:
            return secret
    secret = secrets.token_hex(32)
    write_private(path, secret + "\n")
    return secret


def load_servers(path):
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    servers = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        hostname = item.get("hostname")
        server_id = item.get("id")
        if isinstance(name, str) and isinstance(hostname, str) and isinstance(server_id, str):
            servers.append({"id": server_id, "name": name, "hostname": hostname})
    return servers


def save_servers(path, servers):
    cleaned = [
        {"id": server["id"], "name": server["name"], "hostname": server["hostname"]}
        for server in servers
    ]
    write_private(path, json.dumps(cleaned, indent=2) + "\n")


def empty_snapshot():
    return {
        "cpu_percent": "—",
        "memory_used_label": "—",
        "memory_total_label": "—",
        "net_recv_label": "—",
        "net_sent_label": "—",
        "net_note": "",
        "ports": [],
    }


def listening_ports():
    try:
        connections = psutil.net_connections(kind="tcp")
    except psutil.AccessDenied:
        return []
    ports = []
    for conn in connections:
        if conn.status != psutil.CONN_LISTEN or not conn.laddr:
            continue
        process = ""
        if conn.pid:
            try:
                process = psutil.Process(conn.pid).name()
            except (psutil.Error, OSError):
                process = ""
        ports.append(
            {
                "port": conn.laddr.port,
                "address": conn.laddr.ip,
                "process": process,
            }
        )
    ports.sort(key=lambda item: (item["port"], item["address"], item["process"]))
    return ports


def collect_snapshot(app):
    cpu = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    counters = psutil.net_io_counters()
    if counters is None:
        raise RuntimeError("Network counters are unavailable.")
    now = time.monotonic()
    with app.extensions["net_lock"]:
        sample = app.extensions["net_sample"]
        if sample["time"] is None or now <= sample["time"]:
            recv_label = human_bytes(counters.bytes_recv)
            sent_label = human_bytes(counters.bytes_sent)
            note = "totals until a rate is available"
        else:
            elapsed = now - sample["time"]
            recv_rate = max(0, counters.bytes_recv - sample["recv"]) / elapsed
            sent_rate = max(0, counters.bytes_sent - sample["sent"]) / elapsed
            recv_label = human_bytes(recv_rate) + "/s"
            sent_label = human_bytes(sent_rate) + "/s"
            note = "per second since the previous sample"
        sample["time"] = now
        sample["recv"] = counters.bytes_recv
        sample["sent"] = counters.bytes_sent
    return {
        "cpu_percent": f"{cpu:.1f}",
        "memory_used_label": human_bytes(memory.used),
        "memory_total_label": human_bytes(memory.total),
        "net_recv_label": recv_label,
        "net_sent_label": sent_label,
        "net_note": note,
        "ports": listening_ports(),
    }


def create_app(config_path=None, servers_path=None, secret_path=None):
    app = Flask(__name__)
    config_file = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    servers_file = Path(servers_path) if servers_path else DEFAULT_SERVERS_PATH
    secret_file = Path(secret_path) if secret_path else DEFAULT_SECRET_PATH
    config = load_or_create_config(config_file)
    app.secret_key = load_or_create_secret(secret_file)
    app.config["CONFIG_PATH"] = config_file
    app.config["SERVERS_PATH"] = servers_file
    app.config["PASSWORD_HASH"] = config.get("password_hash", "")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.extensions["net_sample"] = {"time": None, "recv": 0, "sent": 0}
    app.extensions["net_lock"] = threading.Lock()

    def signed_in():
        return session.get("user") == USERNAME

    @app.context_processor
    def inject_auth():
        return {"signed_in": signed_in()}

    @app.before_request
    def require_sign_in():
        if request.endpoint in PUBLIC_ENDPOINTS or signed_in():
            return None
        if request.endpoint == "metrics_snapshot":
            return jsonify({"error": "Sign in required."}), 401
        return redirect(url_for("sign_in"))

    @app.route("/", methods=["GET", "POST"])
    def sign_in():
        if request.method == "GET" and signed_in():
            return redirect(url_for("servers"))
        if request.method == "POST":
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            try:
                password_ok = check_password_hash(app.config["PASSWORD_HASH"], password)
            except (TypeError, ValueError):
                password_ok = False
            if username == USERNAME and password_ok:
                session.clear()
                session["user"] = USERNAME
                return redirect(url_for("servers"))
            session.clear()
            return render_template(
                "sign_in.html",
                error="Invalid username or password.",
                username=username,
            )
        return render_template("sign_in.html", error=None, username="")

    @app.post("/sign-out")
    def sign_out():
        session.clear()
        return redirect(url_for("sign_in"))

    @app.route("/servers", methods=["GET", "POST"])
    def servers():
        path = app.config["SERVERS_PATH"]
        error = None
        form = {"display_name": "", "hostname": ""}
        if request.method == "POST":
            form["display_name"] = request.form.get("display_name", "").strip()
            form["hostname"] = request.form.get("hostname", "").strip()
            if not form["display_name"] or not form["hostname"]:
                error = "Display name and hostname or IP are both required."
            else:
                items = load_servers(path)
                items.append(
                    {
                        "id": secrets.token_hex(8),
                        "name": form["display_name"],
                        "hostname": form["hostname"],
                    }
                )
                save_servers(path, items)
                return redirect(url_for("servers"))
        return render_template("servers.html", servers=load_servers(path), error=error, form=form)

    @app.post("/servers/<server_id>/remove")
    def remove_server(server_id):
        path = app.config["SERVERS_PATH"]
        save_servers(path, [server for server in load_servers(path) if server["id"] != server_id])
        return redirect(url_for("servers"))

    @app.get("/servers/<server_id>/metrics")
    def metrics(server_id):
        server = next((item for item in load_servers(app.config["SERVERS_PATH"]) if item["id"] == server_id), None)
        if server is None:
            abort(404)
        snapshot = empty_snapshot()
        error = None
        try:
            snapshot = collect_snapshot(current_app)
        except Exception:
            error = METRICS_ERROR
        return render_template("metrics.html", server=server, snapshot=snapshot, error=error)

    @app.get("/api/metrics")
    def metrics_snapshot():
        if not signed_in():
            return jsonify({"error": "Sign in required."}), 401
        try:
            payload = collect_snapshot(current_app)
            status = 200
        except Exception:
            payload = {"error": METRICS_ERROR}
            status = 500
        response = jsonify(payload)
        response.headers["Cache-Control"] = "no-store"
        response.status_code = status
        return response

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000)
