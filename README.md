# Demo Server Monitoring

Local read-only view of CPU, memory, network, and listening ports on this machine.

## Run

From the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 and sign in with the demo account `admin` / `admin`.

The app listens on localhost only.

## Sign-in

The demo account is `admin` with password `admin`. On first run the app writes `config.json` with a Werkzeug PBKDF2 hash of that password. The plain password is not stored. A session secret is generated in `.session_secret` on this machine. Both files are gitignored.

## Servers

Saved servers are loaded from `servers.json` in the project directory. That file is gitignored. Each entry is a display name and a hostname or IP: a label, not a remote connection. Adding or removing a server does not open a connection to the hostname.

## Metrics

Opening a server shows a read-only snapshot from this machine:

- CPU percent
- Memory used and memory total
- Network receive and transmit rate since the previous sample
- Listening TCP ports, with the process name when the operating system allows it

The first network sample can show totals until a rate exists. The view refreshes every 5 seconds with no Refresh button. If collection fails, the page shows an error and leaves the rest of the page intact.

## Tests

GitHub Actions installs dependencies and runs the unit tests on every push and pull request.
