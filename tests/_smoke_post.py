"""
POST smoke test for critical create flows.

Logs in as admin, creates: case, intel target, edits target. Verifies each
flow returns 302 + new record exists in DB.
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


def main():
    app = create_app("testing")
    # Ensure officers table exists with admin
    conn = models.get_db()
    conn.execute(
        """
        INSERT OR REPLACE INTO officers
            (badge_number, full_name, rank, section, role, password_hash, email,
             unit_access, is_active, must_change_password, admin_tier,
             verification_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'all', 1, 0, 1, 'active')
        """,
        ("POST-ADMIN", "POST Admin", "CPL", "FNID Area 3", "admin",
         generate_password_hash("Post!Smoke#1234"), "post@test.local"),
    )
    conn.commit()
    conn.close()

    results = []

    def check(name, ok, detail=""):
        marker = "PASS" if ok else "FAIL"
        results.append((name, ok))
        print(f"  [{marker}] {name}" + (f" — {detail}" if detail else ""))

    with app.test_client() as client:
        r = client.post(
            "/login", data={"badge_number": "POST-ADMIN", "password": "Post!Smoke#1234"},
            follow_redirects=False,
        )
        check("login", r.status_code == 302, f"status={r.status_code}")

        # ---- Case intake ----
        r = client.post("/cases/intake", data={
            "classification": "Firearm",
            "parish": "Manchester",
            "division": "FNID Area 3",
            "offence_description": "Illegal possession of firearm",
            "law_and_section": "Firearms Act s.20(1)",
            "suspect_name": "Smoke Test Suspect",
            "suspect_address": "1 Test St",
            "diary_number": "SD/MAN/2026/001",
            "crime_type": "major",
            "workflow_type": "non-uniformed",
            "primary_register_type": "dcrr",
            "station_code": "MAN",
        }, follow_redirects=False)
        check("POST /cases/intake", r.status_code == 302,
              f"status={r.status_code} location={r.headers.get('Location','')}")

        # Pick up the new case_id from redirect location.
        # Format is /cases/<station>/<diary>/<area>/<unit>/<year>/<seq>.
        loc = r.headers.get("Location", "")
        case_id = loc.split("/cases/", 1)[-1].rstrip("/") if "/cases/" in loc else ""
        check("case_id allocated", bool(case_id), f"case_id={case_id}")

        # ---- Case detail loads ----
        if case_id:
            r = client.get(f"/cases/{case_id}", follow_redirects=False)
            check(f"GET /cases/{case_id}", r.status_code == 200,
                  f"status={r.status_code}")

        # ---- Intel target create ----
        r = client.post("/intel/targets/new", data={
            "name": "Smoke Test Target",
            "aliases": "ST, Smoke",
            "description": "Test target for smoke",
            "parish": "Manchester",
            "area": "Mandeville",
            "threat_level": "High",
            "status": "Active",
            "mo": "Vehicle-borne",
            "notes": "Created by smoke test",
        }, follow_redirects=False)
        check("POST /intel/targets/new", r.status_code == 302,
              f"status={r.status_code}")

        # ---- Intel target list shows new ----
        r = client.get("/intel/targets", follow_redirects=False)
        ok = r.status_code == 200 and b"Smoke Test Target" in r.data
        check("GET /intel/targets shows new target", ok, f"status={r.status_code}")

        # ---- Find target_id and edit ----
        c = models.get_db()
        row = c.execute(
            "SELECT target_id FROM intel_targets WHERE target_name = ?",
            ("Smoke Test Target",),
        ).fetchone()
        c.close()
        if row:
            tid = row["target_id"]
            r = client.post(f"/intel/targets/{tid}/edit", data={
                "name": "Smoke Test Target",
                "aliases": "Updated alias",
                "description": "Edited",
                "parish": "St. Elizabeth",
                "area": "Black River",
                "threat_level": "Critical",
                "status": "Active",
                "mo": "Updated MO",
                "notes": "Edited by smoke test",
            }, follow_redirects=False)
            check(f"POST /intel/targets/{tid}/edit",
                  r.status_code == 302, f"status={r.status_code}")

            c = models.get_db()
            after = c.execute(
                "SELECT parish FROM intel_targets WHERE target_id = ?", (tid,)
            ).fetchone()
            c.close()
            check("edit persisted to DB",
                  after and after["parish"] == "St. Elizabeth",
                  f"parish={after['parish'] if after else None}")

        # ---- Change password ----
        r = client.post("/change-password", data={
            "current_password": "Post!Smoke#1234",
            "new_password": "NewPass!2026#X",
            "confirm_password": "NewPass!2026#X",
        }, follow_redirects=False)
        check("POST /change-password", r.status_code == 302,
              f"status={r.status_code}")

    total = len(results)
    passed = sum(1 for _, ok in results if ok)
    print(f"\n=== {passed}/{total} POST flows passed ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
