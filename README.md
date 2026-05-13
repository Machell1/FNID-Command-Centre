# FNID Command Centre v2.0

**Production-Ready Law Enforcement Platform**

Jamaica Constabulary Force — Firearms & Narcotics Investigation Division (FNID), Area 3  
(Manchester, St. Elizabeth, Clarendon)

---

## Compliance & Policy Foundation

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

## Architecture Overview

The platform ships as two complementary stacks:

| Component | Path | Database | Entry Point |
|-----------|------|----------|-------------|
| **Primary Portal** | `fnid_portal/` | SQLite | `python main.py` / `gunicorn wsgi:app` |
| React SPA | `frontend/` | — (API consumer) | `npm run dev` (port 3000) |
| v2 API variant | `src/fnid_portal/` | PostgreSQL | — (reference only) |

The **primary portal** is the actively-developed, production application.  
It uses Flask + Flask-Login + Jinja2 templates backed by SQLite.

---

## Quick Start

### Development

```bash
# 1. Install Python dependencies (requires libcairo2-dev, pkg-config, python3-dev)
pip install -r requirements.txt

# 2. Create the secrets stub (gitignored — needed for AI assistant integration)
cat > fnid_portal/secret_keys.py << 'EOF'
import os
def get_secret(key): return os.environ.get(key)
def has_secret(key): return bool(os.environ.get(key))
EOF

# 3. Start the development server
FLASK_ENV=development python main.py
# → http://127.0.0.1:5000

# 4. (Optional) Start the React SPA frontend
cd frontend && npm install && npm run dev
# → http://localhost:3000 (proxies /api to Flask)
```

On first start the app creates the SQLite database, seeds 28 officer
accounts with random passwords (printed to stdout), and creates a
default `ADMIN` account.

### Production (Gunicorn)

```bash
export FNID_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
gunicorn wsgi:app --bind 0.0.0.0:5000 --workers 4
```

### Docker

```bash
cp .env.example .env
# Edit .env with production secrets
docker-compose up --build -d
```

---

## Database Schema

### Core Entity: `cases`
- Single source of truth for all case records
- Polymorphic registry support (`DCRR`, `MAJOR`, `MINOR`)
- Immutable CR# per SOP 9.1.13
- 7-year retention with soft-delete only

### Registry Extensions
- `dcrr` — Divisional Case Report Register (Appendix 13)
- `major_crime_register` — Major Crime Register (Appendix 11 & 12)

### FNID Domain
- `firearm_seizures` / `narcotics_seizures` — Seizure cataloguing
- `intel_reports` — Source grading, cross-case linking
- `dpp_pipeline` — Prosecution bundle management
- `chain_of_custody` — Exhibit tracking (CR 5, Appendix 16)

### Audit & Compliance
- `audit_log` — WORM (Write Once Read Many), 7-year retention

---

## State Machine

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
| Authentication | Flask-Login sessions + bcrypt password hashing |
| Authorization | RBAC (rank-based) + unit/division/station access |
| Transport | TLS 1.3, HSTS, secure cookies |
| Rate Limiting | Flask-Limiter on auth endpoints (10/min) |
| CSRF | Flask-WTF CSRFProtect on all form routes |
| Headers | CSP, X-Frame-Options DENY, Referrer-Policy |
| Audit | WORM log, 7-year retention |
| Monitoring | Sentry integration (optional, via SENTRY_DSN) |

---

## Testing

```bash
# Run all tests (excludes AI assistant tests by default)
pytest tests/ -v --ignore=tests/test_ai_assistants.py

# Lint
ruff check fnid_portal/ tests/

# Frontend
cd frontend && npx eslint . && npx tsc -b
```

---

## API Endpoints

### Server-rendered (Flask-Login session auth)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/login` | GET/POST | Officer authentication |
| `/cases/` | GET | Case list with filters |
| `/cases/intake` | GET/POST | New case registration |
| `/unit/<unit>` | GET | Unit portal page |
| `/admin/settings` | GET/POST | Admin configuration |

### JSON API (session auth, for React SPA)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/login` | POST | JSON login |
| `/api/v1/auth/me` | GET | Current user profile |
| `/api/v1/dashboard/` | GET | Dashboard statistics |
| `/api/v1/dashboard/command` | GET | Command-level charts |

---

## License

MIT License — Jamaica Constabulary Force

**CONFIDENTIAL**: This system contains sensitive law enforcement data. Unauthorized access is a criminal offence under the Data Protection Act, 2020 and the Constabulary Force Act.
