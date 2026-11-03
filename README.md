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

Open http://127.0.0.1:5000

The app listens on localhost only. The virtualenv, Python caches, and the local config and server-list files are gitignored.
