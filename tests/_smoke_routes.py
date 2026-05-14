"""
Smoke test: log in as admin and hit every GET route that takes no args.
Goal: find 500-class errors before users do.

Run: python tests/_smoke_routes.py
"""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

os.environ["FLASK_ENV"] = "testing"
os.environ["WTF_CSRF_ENABLED"] = "0"

from werkzeug.security import generate_password_hash

from fnid_portal import create_app, models


def setup_admin():
    """Create a known-password admin so we can log in. Idempotent."""
    conn = models.get_db()
    cur = conn.cursor()
    cur.execute("SELECT badge_number FROM officers WHERE badge_number = ?", ("SMOKE-ADMIN",))
    pwd = "Admin!Smoke#1234"
    if cur.fetchone():
        cur.execute(
            "UPDATE officers SET password_hash = ?, must_change_password = 0, "
            "verification_status = 'active', is_active = 1, failed_attempts = 0, "
            "locked_at = NULL, admin_tier = 1, role = 'admin', unit_access = 'all' "
            "WHERE badge_number = ?",
            (generate_password_hash(pwd), "SMOKE-ADMIN"),
        )
    else:
        cur.execute(
            """INSERT INTO officers
               (badge_number, full_name, rank, section, role, password_hash, email,
                unit_access, is_active, must_change_password, admin_tier,
                verification_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 1, 'active')""",
            ("SMOKE-ADMIN", "Smoke Admin", "CPL", "FNID Area 3", "admin",
             generate_password_hash(pwd), "smoke@test.local", "all"),
        )
    conn.commit()
    conn.close()
    return "SMOKE-ADMIN", pwd


def main():
    app = create_app("testing")
    badge, pwd = setup_admin()

    skip_methods = {"HEAD", "OPTIONS"}
    skip_endpoints = {
        "static",
        "auth.logout",  # would end the session
    }

    routes = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint in skip_endpoints:
            continue
        if any(arg in rule.rule for arg in ("<", ">")):
            continue
        methods = (rule.methods or set()) - skip_methods
        if "GET" not in methods:
            continue
        routes.append((rule.endpoint, rule.rule))

    routes.sort(key=lambda r: r[1])

    with app.test_client() as client:
        login_resp = client.post(
            "/login",
            data={"badge_number": badge, "password": pwd},
            follow_redirects=False,
        )
        if login_resp.status_code not in (200, 302):
            print(f"FATAL: login failed with {login_resp.status_code}")
            print(login_resp.data[:1000].decode("utf-8", errors="replace"))
            return 1
        # Check we ended up authenticated (not redirected back to /login)
        loc = login_resp.headers.get("Location", "")
        print(f"Login -> {login_resp.status_code} {loc}")

        # Verify by hitting home
        home = client.get("/", follow_redirects=False)
        print(f"GET / -> {home.status_code}")
        if home.status_code == 302 and "/login" in home.headers.get("Location", ""):
            print("FATAL: session not established (bounced to /login)")
            return 1

        results = {"ok": [], "redirect": [], "client_err": [], "server_err": [], "other": []}
        for endpoint, rule in routes:
            try:
                resp = client.get(rule, follow_redirects=False)
                code = resp.status_code
                if 200 <= code < 300:
                    results["ok"].append((endpoint, rule, code))
                elif 300 <= code < 400:
                    loc = resp.headers.get("Location", "")
                    results["redirect"].append((endpoint, rule, code, loc))
                elif 400 <= code < 500:
                    results["client_err"].append((endpoint, rule, code))
                elif code >= 500:
                    body = resp.data[:500].decode("utf-8", errors="replace")
                    results["server_err"].append((endpoint, rule, code, body))
                else:
                    results["other"].append((endpoint, rule, code))
            except Exception as exc:
                import traceback
                tb = traceback.format_exc()[-500:]
                results["server_err"].append((endpoint, rule, "EXC", tb))

    total = sum(len(v) for v in results.values())
    print(f"\n=== Smoke test: {total} parameterless GET routes ===\n")
    print(f"  OK (2xx):     {len(results['ok'])}")
    print(f"  Redirect:     {len(results['redirect'])}")
    print(f"  Client 4xx:   {len(results['client_err'])}")
    print(f"  Server 5xx:   {len(results['server_err'])}")
    print(f"  Other:        {len(results['other'])}")

    if results["server_err"]:
        print("\n--- SERVER ERRORS ---")
        for row in results["server_err"]:
            print(f"\n  [{row[2]}] {row[1]}  ({row[0]})")
            snippet = row[3].replace("\n", " | ")[:400]
            print(f"        {snippet}")

    if results["client_err"]:
        print("\n--- CLIENT 4XX ---")
        for endpoint, rule, code in results["client_err"]:
            print(f"  [{code}] {rule:50}  ({endpoint})")

    if results["redirect"]:
        # Most should be to /login (auth-required) or to a unit page.
        # Anything unusual is worth a look.
        login_redirects = sum(1 for r in results["redirect"] if "/login" in r[3])
        if login_redirects:
            print(f"\n  (note: {login_redirects} routes redirected to /login -- "
                  "session may have been invalidated by some route)")

    return 0 if not results["server_err"] else 2


if __name__ == "__main__":
    sys.exit(main())
