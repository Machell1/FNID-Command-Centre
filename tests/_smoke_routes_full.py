"""
Full smoke test: seed the DB with realistic data, log in as admin, hit every
GET route (both parameterless and parameterised). Reports any 5xx responses.

Run: python tests/_smoke_routes_full.py
"""
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

os.environ["FLASK_ENV"] = "testing"
os.environ["WTF_CSRF_ENABLED"] = "0"

from werkzeug.security import generate_password_hash

from fnid_portal import create_app, models


def setup_admin(conn):
    """Upsert a SMOKE-ADMIN account with a known password."""
    pwd = "Admin!Smoke#1234"
    conn.execute(
        """
        INSERT OR REPLACE INTO officers
            (badge_number, full_name, rank, section, role, password_hash, email,
             unit_access, is_active, must_change_password, admin_tier,
             verification_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 1, 'active')
        """,
        (
            "SMOKE-ADMIN", "Smoke Admin", "CPL", "FNID Area 3", "admin",
            generate_password_hash(pwd), "smoke@test.local", "all",
        ),
    )
    conn.commit()
    return "SMOKE-ADMIN", pwd


def first_id(conn, table, col):
    row = conn.execute(f"SELECT {col} FROM {table} LIMIT 1").fetchone()
    return row[col] if row else None


def build_param_map(conn):
    """Return a dict mapping common URL-arg names to a realistic value."""
    return {
        # cases
        "case_id": first_id(conn, "cases", "case_id"),
        # intel
        "target_id": first_id(conn, "intel_targets", "target_id"),
        "intel_id": first_id(conn, "intel_reports", "intel_id"),
        # operations / seizures / arrests
        "op_id": first_id(conn, "operations", "op_id"),
        "seizure_id": first_id(conn, "firearm_seizures", "seizure_id"),
        "firearm_id": first_id(conn, "firearm_seizures", "seizure_id"),
        "narcotic_id": first_id(conn, "narcotics_seizures", "seizure_id"),
        "arrest_id": first_id(conn, "arrests", "arrest_id"),
        # chain of custody, witnesses, disclosure
        "exhibit_tag": first_id(conn, "chain_of_custody", "id"),
        "lab_ref": first_id(conn, "lab_tracking", "lab_ref"),
        "statement_id": first_id(conn, "witness_statements", "statement_id"),
        "disclosure_id": first_id(conn, "disclosure_log", "disclosure_id"),
        # generic int IDs (DPP/correspondence/etc)
        "id": "1",
        "record_id": "1",
        "subtype": "operation",
        "date": "2026-01-15",
        "vehicle_id": first_id(conn, "transport_vehicles", "vehicle_id") or "skip",
        "report_type": "monthly",
        # admin / users
        "badge": "SMOKE-ADMIN",
        # registers
        "dcrr_id": "1",
        # unit portals
        "unit": "ganja",
        # forms
        "form_type": "CR1",
        "form_id": "1",
        # files / docs
        "doc_id": "1",
        "filename": "test.pdf",
        # assistants
        "agent_key": "skip",
        "run_id": "skip",
        "action_id": "1",
        # alerts / reviews
        "alert_id": "1",
        "review_id": "1",
        # correspondence
        "correspondence_id": "1",
        # path:*
        "path": "test",
    }


def main():
    app = create_app("testing")

    # Seed full operational data
    from fnid_portal.seed import seed_database
    seed_database(force=True)

    conn = models.get_db()
    badge, pwd = setup_admin(conn)
    params = build_param_map(conn)
    conn.close()

    print("\nParam map (first 15):")
    for k in list(params)[:15]:
        print(f"  {k:18} = {params[k]}")

    skip_endpoints = {"static", "auth.logout"}
    skip_param_values = {"skip", None, ""}

    parameterless = []
    parameterised = []
    not_substitutable = []

    for rule in app.url_map.iter_rules():
        if rule.endpoint in skip_endpoints:
            continue
        if "GET" not in (rule.methods or set()):
            continue

        if not rule.arguments:
            parameterless.append(rule)
            continue

        # Substitute
        sub_values = {}
        skip = False
        for arg in rule.arguments:
            if arg not in params:
                not_substitutable.append((rule, arg))
                skip = True
                break
            v = params[arg]
            if v in skip_param_values:
                skip = True
                break
            sub_values[arg] = v
        if skip:
            continue

        try:
            url = rule.build(sub_values, append_unknown=False)
            if isinstance(url, tuple):
                url = url[1]
            parameterised.append((rule.endpoint, url))
        except Exception as exc:
            not_substitutable.append((rule, f"build error: {exc}"))

    with app.test_client() as client:
        resp = client.post(
            "/login", data={"badge_number": badge, "password": pwd},
            follow_redirects=False,
        )
        if resp.status_code not in (200, 302):
            print(f"FATAL: login failed {resp.status_code}")
            return 1

        def hit(routes_iter, label):
            results = {"ok": [], "redirect": [], "client_err": [], "server_err": []}
            for endpoint, url in routes_iter:
                try:
                    r = client.get(url, follow_redirects=False)
                    code = r.status_code
                    if 200 <= code < 300:
                        results["ok"].append((endpoint, url, code))
                    elif 300 <= code < 400:
                        results["redirect"].append((endpoint, url, code))
                    elif 400 <= code < 500:
                        results["client_err"].append((endpoint, url, code))
                    else:
                        body = r.data[:600].decode("utf-8", errors="replace")
                        results["server_err"].append((endpoint, url, code, body))
                except Exception as exc:
                    import traceback
                    results["server_err"].append(
                        (endpoint, url, "EXC", traceback.format_exc()[-600:])
                    )
            total = sum(len(v) for v in results.values())
            print(f"\n=== {label}: {total} routes ===")
            print(f"  OK: {len(results['ok']):3}  Redir: {len(results['redirect']):3}"
                  f"  4xx: {len(results['client_err']):3}  5xx: {len(results['server_err']):3}")
            if results["server_err"]:
                print("\n  SERVER ERRORS:")
                for row in results["server_err"]:
                    print(f"  [{row[2]}] {row[1]}  ({row[0]})")
                    body = row[3] if len(row) > 3 else ""
                    # Pull the actual exception line
                    last_lines = [
                        ln.strip() for ln in body.split("\n")
                        if ln.strip() and (
                            "Error" in ln or "Exception" in ln
                            or "BuildError" in ln or "OperationalError" in ln
                            or "AttributeError" in ln or "TypeError" in ln
                            or "KeyError" in ln or "ValueError" in ln
                        )
                    ]
                    for ln in last_lines[-3:]:
                        print(f"        {ln[:200]}")
            return results

        plain = [(r.endpoint, r.rule) for r in parameterless]
        plain_results = hit(plain, "Parameterless GET")
        param_results = hit(parameterised, "Parameterised GET")

        if not_substitutable:
            print(f"\n  Skipped (no param value): {len(not_substitutable)} routes")
            for rule, arg in not_substitutable[:20]:
                print(f"    {rule.rule:50}  needs={arg}")

        # 4xx details
        for src, label in ((plain_results, "param-less"), (param_results, "param")):
            if src["client_err"]:
                print(f"\n  4xx ({label}):")
                for endpoint, url, code in src["client_err"]:
                    print(f"    [{code}] {url:50}  ({endpoint})")

        bad = (
            len(plain_results["server_err"]) + len(param_results["server_err"])
        )
        return 0 if bad == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
