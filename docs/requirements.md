# Demo Server Monitoring — Requirements

Local demo for internal teams who today sign in to Linux servers to check CPU, memory, network, and port usage. The app runs on the same machine as Cursor and shows live data from that machine.

## Problem

L1, L2, and L3 staff in infrastructure and application development must log in to servers to see current resource and port usage. This demo gives them a read-only web view of those figures from one place.

## Users

Internal L1, L2, and L3 teams. For this demo everyone shares one admin account. There are no separate roles.

## Product decisions

- The app runs locally and collects live metrics on that Linux host with `psutil`.
- Each saved server is a label: display name and hostname or IP. Live numbers come from the host running the app and are shown for every saved server.
- The metrics view is a current snapshot that refreshes every 5 seconds.
- Metrics pages are read-only. The signed-in admin can add and remove servers.
- Sign-in is a single user, `admin`. The password is stored only as a hash in a local config file. The demo password is `admin`. There is no user management and no password-change screen.

## Tech

- Python 3
- Flask, server-rendered pages
- `psutil` for CPU, memory, network, and listening ports
- Local JSON files for the password hash and the server list
- No database, no SSH, no separate frontend build

## Sign-in

- Unauthenticated visitors see only the sign-in page.
- Username `admin` and password `admin` start a session.
- The config file stores a password hash (Werkzeug PBKDF2 or equivalent), never the plain password.
- A wrong username or password shows an error and stays on the sign-in page.
- A signed-in user can sign out.

## Servers

- A server list shows display name and hostname or IP.
- Add server asks for display name and hostname or IP. Both are required.
- Remove server deletes that label from the list.
- The list is saved in a local JSON file and is still there after a restart.
- Adding or removing a server does not open a connection to that hostname. It only changes the labels in the demo.

## Metrics

Opening a server shows a read-only snapshot for the local host:

- CPU percent
- Memory used and memory total
- Network receive and transmit rate since the previous sample (first load can show totals until a rate is available)
- Listening TCP ports, including the process name when the OS allows it

The view updates every 5 seconds without a Refresh button. Values cannot be edited. If metric collection fails, the page shows an error instead of breaking the layout.

## Screens

1. **Sign in** — username, password, error message.
2. **Servers** — list, add form, remove action, link to metrics, sign out.
3. **Server metrics** — name, hostname or IP, the four snapshot areas, and a link back to the server list.

Layout is a simple desktop page: clear type, cards for CPU, memory, and network, and a table for ports. The demo targets a local browser window.

## Run locally

From the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install flask psutil
python app.py
```

Open `http://127.0.0.1:5000` and sign in with `admin` / `admin`.

The app listens on localhost only. The default password is for this local demo.

## Done when

- Sign-in rejects a bad password and accepts `admin` / `admin`.
- The password in the config file is a hash.
- Admin can add a server with a name and hostname, see it in the list, and remove it.
- After a restart, the server list is unchanged.
- The metrics page shows live CPU, memory, network, and listening ports from this machine and updates every 5 seconds.
- The metrics page has no edit controls.

## Out of scope

Remote collection, historical charts, alerts, extra user accounts, password change, and any host other than the machine running the app.
