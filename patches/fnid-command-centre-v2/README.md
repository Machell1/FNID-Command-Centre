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

```
┌─────────────────────────────────────────────────────────┐
│  PERIMETER          WAF → VPN → TLS 1.3 → Geo-Block     │
├─────────────────────────────────────────────────────────┤
│  IDENTITY           JCF AD → MFA → RBAC/ABAC            │
├─────────────────────────────────────────────────────────┤
│  FNID UNITS         Intelligence | Operations | Seizures  │
│                     Arrests/Court | Forensics | Registry│
├─────────────────────────────────────────────────────────┤
│  CORE ENGINE        Unified Registry ↔ Investigation     │
│                     DPP Pipeline | Exhibit Custody      │
├─────────────────────────────────────────────────────────┤
│  DATA               PostgreSQL | WORM Audit | S3 Lock     │
│                     Redis Cache | Cross-Region Backup     │
└─────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Docker (Recommended for Production)

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with production secrets

# 2. Build and start
docker-compose up --build -d

# 3. Initialize database
docker-compose exec app flask db upgrade

# 4. Access
# Web UI: https://localhost
# API: https://localhost/api/v1
```

### Manual Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env

# 3. Initialize database
flask db init
flask db migrate
flask db upgrade

# 4. Run
flask run
```

---

## Database Schema

### Core Entity: `cases`
- Single source of truth for all case records
- Polymorphic registry support (`DCRR`, `MAJOR`, `MINOR`)
- Immutable CR# per SOP 9.1.13
- 7-year retention with soft-delete only

### Registry Extensions
- `dcrr_entries` — Divisional Case Report Register (Appendix 13)
- `station_registers` — Major/Minor Crime Registers (Appendix 11 & 12)

### Investigation Module
- `investigations` — IO assignment, review scheduling
- `investigation_worksheets` — CR 1 digital form (Appendix 9)
- `action_sheets` — CR 2 task management (Appendix 10)

### FNID Domain
- `fnid_seizures` — Firearms & narcotics cataloguing
- `intelligence_reports` — Source grading, cross-case linking
- `dpp_file_pipeline` — Prosecution bundle management
- `exhibits` — Chain of custody (CR 5, Appendix 16)

### Audit & Compliance
- `audit_log` — WORM (Write Once Read Many), cryptographic chain
- 7-year retention, non-repudiation enforcement

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
| Authentication | JWT + bcrypt + MFA (TOTP/Smart Card) |
| Authorization | RBAC (rank-based) + ABAC (unit/division/station) |
| Transport | TLS 1.3, HSTS, secure cookies |
| Data | AES-256 at rest, field-level encryption for PII |
| Audit | WORM log, SHA-256 chain, 7-year retention |
| Network | VPN-only admin, geo-blocking, WAF |

---

## Testing

```bash
# Run all tests
pytest -v

# With coverage
pytest --cov=src/fnid_portal --cov-report=html

# Specific module
pytest tests/test_registry.py -v
```

---

## API Endpoints

| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/auth/login` | POST | Officer authentication | Public |
| `/auth/me` | GET | Current officer profile | JWT |
| `/api/v1/cases` | GET | List cases (filtered) | JWT |
| `/api/v1/cases` | POST | Create new case | JWT + Registrar |
| `/api/v1/cases/<id>` | GET | Case details | JWT + Access |
| `/api/v1/cases/<id>/investigation` | GET | Investigation data | JWT + Access |
| `/api/v1/dashboard/stats` | GET | Dashboard statistics | JWT |
| `/api/v1/divisions` | GET | Division reference | JWT |
| `/api/v1/stations` | GET | Station reference | JWT |
| `/api/v1/officers` | GET | Officer directory | JWT |

---

## License

MIT License — Jamaica Constabulary Force

**CONFIDENTIAL**: This system contains sensitive law enforcement data. Unauthorized access is a criminal offence under the Data Protection Act, 2020 and the Constabulary Force Act.
