# FNID Area 3 Operational Portal

Web-based case management and operational tracking system for the Jamaica Constabulary Force Firearms & Narcotics Investigation Division (FNID), Area 3 (Manchester, St. Elizabeth, Clarendon).

## Features

- **6 Unit Portals**: Intelligence, Operations, Seizures, Arrests/Court, Forensics/Evidence, Case Registry
- **Case Management**: Full investigation lifecycle from intelligence through conviction
- **SOP Compliance**: Checklist tracking aligned to JCF operational requirements
- **DPP File Pipeline**: Tracks file preparation per Prosecution Protocol (2012) and Disclosure Protocol (2013)
- **Dashboards**: Per-unit and command-level statistics with Chart.js visualizations
- **Audit Trail**: All record changes logged with officer identification
- **Excel Export**: Export unit data to .xlsx format

## Tech Stack

- **Backend**: Python 3.12, Flask 3.x
- **Database**: SQLite with WAL mode
- **Frontend**: Bootstrap 5.3, DataTables, Chart.js
- **WSGI**: Gunicorn
- **Container**: Docker

## Quick Start

### Docker (recommended)

```bash
# Copy and configure environment
cp .env.example .env
# Edit .env and set FNID_SECRET_KEY

# Build and run
docker compose up --build
```

The portal will be available at http://localhost:5000.

### Manual

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env as needed

# Run development server
python wsgi.py
```

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `FNID_SECRET_KEY` | Production | Dev fallback | Flask session secret key |
| `FLASK_ENV` | No | `development` | `development`, `production`, or `testing` |
| `FNID_DB_PATH` | No | `src/fnid_portal/data/fnid.db` | SQLite database path |
| `FNID_UPLOAD_DIR` | No | `src/fnid_portal/data/uploads` | File upload directory |
| `FNID_EXPORT_DIR` | No | `src/fnid_portal/data/exports` | Excel export directory |

## Project Structure

```
src/fnid_portal/
    __init__.py         # App factory
    config.py           # Environment-based configuration
    constants.py        # JCF controlled inputs and dropdown values
    models.py           # SQLite database schema
    routes/
        auth.py         # Login / logout
        main.py         # Home page, command dashboard
        units.py        # Unit portals, CRUD operations
        data.py         # Import / export
        api.py          # JSON API endpoints
    static/             # CSS, JS assets
    templates/          # Jinja2 templates by unit
tests/
    conftest.py         # Pytest fixtures
    test_app.py         # Smoke tests
```

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Applicable Legislation

- Firearms (Prohibition, Restriction and Regulation) Act, 2022
- Dangerous Drugs Act (as amended 2015)
- Gun Court Act, 1974
- Proceeds of Crime Act (POCA), 2007
- Bail Act, 2023
- Constabulary Force Act s.15 (48-Hour Rule)
- DPP Prosecution Protocol (April 2012)
- DPP Disclosure Protocol (September 2013)

## License

MIT
