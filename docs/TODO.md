# Implementation TODO

Local demo only. The app runs on the machine where Cursor is running and listens on `127.0.0.1:5000`. Each step is one small change. Finish security and a short doc note in the same step before moving on.

## 1. Project initialization and basic UI

- [x] Add `requirements.txt` (`flask`, `psutil`), `.gitignore` (`.venv/`, `__pycache__/`, local config and data files), and `app.py`.
- [x] Serve three server-rendered pages with a simple desktop layout: sign-in, server list, and metrics (cards for CPU, memory, and network; a table for ports). Static placeholders only.
- [x] Bind the app to `127.0.0.1` only.
- [x] **Security:** Do not commit the virtualenv, caches, or files that will later hold the password hash or server list.
- [x] **Docs:** Add `README.md` with the local run commands: create `.venv`, install requirements, run `python app.py`, open `http://127.0.0.1:5000`.

## 2. Sign-in and unit tests

- [x] On first run, write a local config file with a Werkzeug PBKDF2 hash of the demo password. The username is `admin`. The demo password is `admin`. Never store the plain password.
- [x] Sign-in starts a session only for `admin` / `admin`. A wrong username or password shows an error and stays on the sign-in page. Sign-out clears the session. Unsigned visitors see only the sign-in page.
- [x] Add unit tests for a good login, a bad login, “config stores a hash”, and sign-out.
- [x] **Security:** Generate a session secret outside the repo. Compare passwords with the hash helper. No extra accounts and no password-change screen.
- [x] **Docs:** Note the demo account and that the config file stores a hash.

## 3. GitHub Actions

- [x] Add a workflow that installs dependencies and runs the unit tests on push and pull request.
- [x] **Security:** No secrets in the workflow. Tests create their own temp config and do not read a password file from the repo.
- [x] **Docs:** Add one line to the README describing what the workflow runs.

## 4. Server list

- [x] Load saved servers from a local JSON file and show display name and hostname or IP. An empty file shows an empty list.
- [x] **Security:** Read the file from a fixed local path. Render names and hostnames as text.
- [x] **Docs:** Note the JSON file path and that it is gitignored.

## 5. Add and remove a server

- [x] Add requires both display name and hostname or IP, then saves the list. Remove deletes that label. The list is still there after a restart.
- [x] Adding or removing does not open a connection to the hostname.
- [x] **Security:** Accept only the two text fields. Ignore any other input. Keep the list file local.
- [x] **Docs:** Note that a server entry is a label, not a remote connection.

## 6. Metrics snapshot

- [x] On the metrics page, show live local CPU percent, memory used and total, network receive and transmit rate since the previous sample, and listening TCP ports with the process name when the OS allows it.
- [x] The page is read-only. Show the server’s display name and hostname, plus a link back to the list.
- [x] **Security:** Collect metrics only from the local host with `psutil`. Do not connect to the saved hostname. Show process names as text.
- [x] **Docs:** List the four snapshot fields and that the first network sample can show totals until a rate exists.

## 7. Refresh and errors

- [x] Update the metrics view every 5 seconds with no Refresh button. If collection fails, show an error and leave the rest of the page intact.
- [x] **Security:** The refresh endpoint requires a signed-in session and returns only the local snapshot.
- [x] **Docs:** Note the 5-second refresh and the error behavior.

## 8. Local check

- [x] Run through the requirements “Done when” list on this machine: bad password rejected, `admin` / `admin` accepted, hash on disk, add and remove a server, list survives a restart, metrics update every 5 seconds, no edit controls.
- [x] **Security:** Confirm the app is bound to localhost and no password or server list is committed.
- [x] **Docs:** Check the README run steps against the app.
