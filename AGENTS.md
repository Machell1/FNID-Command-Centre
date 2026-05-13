# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

FNID Command Centre v2.0 — a Flask-based law enforcement case management platform. There are two app variants in this repo:

| Path | Role | Database | Entry point |
|------|------|----------|-------------|
| `fnid_portal/` | **Primary app** (actively developed) | SQLite | `python3 main.py` |
| `src/fnid_portal/` | v2 API variant | PostgreSQL/SQLAlchemy | `wsgi.py` |
| `frontend/` | React SPA (Vite) | — | `npm run dev` (port 3000, proxies `/api` → Flask 5000) |

The CI targets the primary app (`fnid_portal/` + `tests/`).

### Running the primary Flask app

```bash
FLASK_ENV=development python3 main.py
# Serves on http://127.0.0.1:5000
```

- On first start the app auto-creates the SQLite DB at `fnid_portal/data/fnid.db`, seeds 28 officer accounts with random passwords, and prints them to stdout.
- The default admin account badge is `ADMIN` with a random password (printed on first run). All seeded accounts have `must_change_password=1`.
- `main.py` calls `webbrowser.open()` which produces harmless D-Bus errors in headless environments — ignore them.

### Running the React frontend

```bash
cd frontend && npm run dev   # Vite on port 3000
```

Vite proxies `/api` requests to `http://localhost:5000` (requires Flask running).

### Linting

- **Python:** `ruff check fnid_portal/ tests/` (per CI). The Makefile targets `flake8`/`black` on `src/fnid_portal` but CI uses `ruff`.
- **Frontend:** `cd frontend && npx eslint .`
- Pre-existing lint warnings exist in both Python and TypeScript code.

### Testing

```bash
pytest tests/ -v --ignore=tests/test_ai_assistants.py
```

- `tests/test_ai_assistants.py` must be excluded — it imports `fnid_portal.secret_keys` which is a stub module created during setup.
- The test suite has two fixture families: the `conftest.py` provides fixtures for the v2 SQLAlchemy variant (`app`, `client`, `auth_headers`), while many primary-app tests expect `logged_in_client`, `admin_client`, and `db` fixtures that are not yet defined. Expect ~30 passes and pre-existing failures/errors from the fixture mismatch.
- Tests that call `fnid_portal.models` functions directly (e.g. `test_case_numbers`, `test_deadlines`) fail with "Database not configured" because they don't use an app context.

### System dependencies

`xhtml2pdf` (PDF export) requires `libcairo2-dev`, `pkg-config`, and `python3-dev` system packages for the `pycairo` build.

### Known gotchas

- `setup.py` (v2 variant, `package_dir={'': 'src'}`) conflicts with `pyproject.toml` (`where = ["."]`). With Python 3.12+ `pip install -e ".[dev]"` may fail. Install dependencies directly from `requirements.txt` + pyproject.toml deps instead.
- The `fnid_portal/secret_keys.py` module is missing from the repo and must be present for the app to start (it provides `get_secret` and `has_secret` for AI assistant integration).
