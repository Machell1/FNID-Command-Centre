# FNID Command Centre v2.0

**Production case-management platform for the Jamaica Constabulary Force,
Firearms & Narcotics Investigation Division — Area 3**
(Manchester, St. Elizabeth, Clarendon)

Distributed as a one-click Windows installer. Runs entirely locally per officer:
SQLite, plain HTTP on `127.0.0.1`, no cloud dependency.

---

## Compliance & policy foundation

| Document | Reference |
|----------|-----------|
| JCF Case Management Policy & SOP | JCF/FW/PL/C&S/0001/2024 |
| Firearms Act | 2022 |
| Dangerous Drugs Act | 2015 (as amended) |
| Gun Court Act | 1974 |
| Proceeds of Crime Act (POCA) | 2007 |
| Bail Act | 2023 |
| Data Protection Act | 2020 |
| DPP Prosecution Protocol | April 2012 |
| DPP Disclosure Protocol | September 2013 |

---

## Install (Windows)

1. Download `FNID-Command-Centre-Setup-<version>.exe` from the release.
2. Right-click → **Run as administrator**.
3. Follow the wizard. The installer drops:
   - The application into `C:\Program Files\FNID Command Centre`.
   - A Start Menu folder and (optional) Desktop shortcut.
   - An uninstaller registered with Windows Apps & Features.
4. Launch from the Start Menu or the desktop icon.
   - A tray icon (navy/gold "FNID") appears in the system tray.
   - The default browser opens to `http://127.0.0.1:5000`.

### User data location

All officer-writable data lives under the user's profile, not under
Program Files (which is read-only for non-admins):

```
%LOCALAPPDATA%\FNID Command Centre\
├── fnid.db                     SQLite database
├── .secret_key                 Per-install Flask SECRET_KEY (auto-generated)
├── _initial_credentials.txt    First-run admin password — delete after first login
├── uploads\                    File attachments
├── exports\                    Generated PDFs / Excel workbooks
└── logs\                       Rotating fnid.log (5 × 5 MB)
```

Uninstalling the application does **not** remove this directory — your case
data, exhibits, and logs are preserved.

### First sign-in

After install, open `%LOCALAPPDATA%\FNID Command Centre\_initial_credentials.txt`
for the auto-generated `ADMIN` badge password. Sign in, change the password
immediately, then delete that file.

To enable additional officers, use **Admin → User Management** or have them
register at `/register` with a `@jcf.gov.jm` email address (whitelisted).

---

## Run from source (developers)

Requirements: Python 3.11 - 3.13, Windows / Linux / macOS.

```powershell
git clone https://github.com/Machell1/FNID-Command-Centre
cd FNID-Command-Centre
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run the dev server (Flask debug, auto-reload)
$env:FLASK_ENV = "development"
$env:FNID_USE_REPO_DATA = "1"       # keep data inside the repo for dev
python main.py
# → http://127.0.0.1:5000
```

`bash` equivalent:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
FLASK_ENV=development FNID_USE_REPO_DATA=1 python main.py
```

---

## Build the installer

```powershell
.\scripts\build_installer.ps1
```

Prerequisites: Python 3.11+, [Inno Setup 6](https://jrsoftware.org/isdl.php).

The script:

1. Sets up `.venv` if needed
2. Installs dependencies
3. Generates the `.ico`
4. Runs the smoke tests (`tests\_smoke_routes_full.py`, `tests\_smoke_post.py`)
5. Builds the PyInstaller bundle into `dist\FNID-Command-Centre\`
6. Compiles the Inno Setup `.iss` into `installer\Output\FNID-Command-Centre-Setup-<version>.exe`

---

## Architecture

| Component | Path | Purpose |
|-----------|------|---------|
| Web app | `fnid_portal/` | Flask + Jinja2 + SQLite |
| Launcher | `launcher.py` | Waitress + tray icon + auto browser |
| Installer | `installer/fnid.iss` | Inno Setup script |
| Build spec | `fnid_command_centre.spec` | PyInstaller config |

The portal is a single Flask application with 38 route blueprints across
five domain phases:

- **Phase 1** — Core case management, RBAC, CR forms, file movement, MCR, intel, admin, search
- **Phase 2** — Transport, DCRR, evidence, analytics, batch ops, notifications, reports
- **Phase 3** — DPP pipeline, SOP checklists, witness statements, disclosure log
- **Phase 4** — Correspondence, investigator cards, case reviews, intel targets
- **Phase 5** — Documents, KPIs, workflow engine, AI assistants

### Schema highlights

- `cases` — single source of truth, immutable CR# per SOP 9.1.13, 7-year retention
- `dcrr` + `major_crime_register` — polymorphic registry support
- `firearm_seizures`, `narcotics_seizures`, `intel_reports`, `chain_of_custody`, `dpp_pipeline`
- `audit_log` — WORM, 7-year retention

### Case-status state machine

```
OPEN → ASSIGNED → ACTIVE → [UNDER_REVIEW | AWAITING_COURT | SUSPENDED | CLEARED]
                                                            ↓
                                                       COLD_CASE (3 years)
                                                            ↓
                                                       REOPENED → OPEN
```

| Transition | Authority | SOP Reference |
|------------|-----------|---------------|
| OPEN → ASSIGNED | Registrar / Station Manager | 9.2.2 |
| ACTIVE → SUSPENDED | DCO | 9.3.9 |
| SUSPENDED → COLD_CASE | DCO / ACO / ACP CIB | 9.3.10 |
| CLOSED → REOPENED | ACP CIB / Director CIB HQ / ACO / DCO | 9.3.7 |

---

## Security

| Layer | Implementation |
|-------|---------------|
| Authentication | Flask-Login sessions + Werkzeug password hashing (PBKDF2) |
| Authorization | RBAC (rank + role + unit/division/station access) |
| Transport | Plain HTTP on `127.0.0.1` only (single-PC install); HTTPS supported via `FNID_LOCAL_HTTP=0` behind a reverse proxy |
| Rate limiting | Flask-Limiter on `/login` and `/register` (10/min) |
| CSRF | Flask-WTF `CSRFProtect` on all form routes |
| Headers | Flask-Talisman: CSP, X-Frame-Options DENY, Referrer-Policy, Permissions-Policy |
| Audit | WORM log, 7-year retention, every login / mutation logged |
| Monitoring | Optional Sentry (set `SENTRY_DSN` env var) |
| Lockout | 5 failed attempts → 30-minute lockout |
| Passwords | min 10 chars, must include upper/lower/digit/symbol, badge / name disallowed |

---

## Testing

```powershell
# Full unit/integration test suite
.\.venv\Scripts\python.exe -m pytest tests\ -v --ignore=tests\test_ai_assistants.py

# Fast smoke tests (used by build_installer.ps1)
.\.venv\Scripts\python.exe tests\_smoke_routes_full.py
.\.venv\Scripts\python.exe tests\_smoke_post.py

# Lint
.\.venv\Scripts\python.exe -m ruff check fnid_portal\ tests\
```

The smoke harness boots the app, seeds realistic data, logs in as admin,
and exercises every GET route plus the major creation flows. CI should run
both smoke files before publishing a release.

---

## Environment overrides

| Var | Default | Purpose |
|-----|---------|---------|
| `FNID_DATA_DIR` | (auto) | Override the whole data root |
| `FNID_DB_PATH` | `<data>/fnid.db` | SQLite file |
| `FNID_UPLOAD_DIR` | `<data>/uploads` | Attachment storage |
| `FNID_EXPORT_DIR` | `<data>/exports` | Generated reports |
| `FNID_LOG_DIR` | `<data>/logs` | Rotating logs |
| `FNID_SECRET_KEY` | (file) | Flask secret; otherwise persisted to `<data>/.secret_key` |
| `FNID_LOCAL_HTTP` | `1` | `0` enables HTTPS / HSTS (for reverse proxy) |
| `FNID_PORT` | `5000` | Launcher port; auto-finds free port if taken |
| `FNID_NO_BROWSER` | unset | `1` skips auto-opening the browser |
| `FNID_NO_TRAY` | unset | `1` skips the tray icon (headless) |
| `FNID_SEED_ROSTER` | unset | `1` seeds the 28-officer FNID Area 3 roster on first run |
| `FNID_USE_REPO_DATA` | unset | `1` keeps data inside the repo for source-checkout dev |
| `SENTRY_DSN` | unset | Enables Sentry error reporting |

---

## License

MIT — Jamaica Constabulary Force.

**CONFIDENTIAL.** This system contains sensitive law-enforcement data.
Unauthorized access is an offence under the Data Protection Act, 2020 and
the Constabulary Force Act.
