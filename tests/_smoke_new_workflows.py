"""
POST smoke for the new workflows added by the self-sufficiency QA:
  - Witness statement body composition + PDF export
  - Correspondence memo body composition + PDF export
  - DPP bundle PDF export
"""
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

os.environ["FLASK_ENV"] = "testing"
os.environ["WTF_CSRF_ENABLED"] = "0"
os.environ["FNID_USE_REPO_DATA"] = "1"

from werkzeug.security import generate_password_hash

from fnid_portal import create_app, models


def main():
    app = create_app("testing")

    # Seed FIRST (force wipes officers too), then insert our test admin.
    from fnid_portal.seed import seed_database
    seed_database(force=True)

    conn = models.get_db()
    conn.execute(
        """
        INSERT OR REPLACE INTO officers
            (badge_number, full_name, rank, section, role, password_hash, email,
             unit_access, is_active, must_change_password, admin_tier,
             verification_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'all', 1, 0, 1, 'active')
        """,
        ("QA-ADMIN", "QA Admin", "CPL", "FNID Area 3", "admin",
         generate_password_hash("Pw#QA!2026"), "qa@test.local"),
    )
    conn.commit()

    case_id = conn.execute(
        "SELECT case_id FROM cases LIMIT 1"
    ).fetchone()["case_id"]
    print(f"case_id = {case_id}")

    # Insert a DPP pipeline entry linked to that case.
    cur = conn.execute(
        """INSERT INTO dpp_pipeline
           (linked_case_id, dpp_file_date, crown_counsel, dpp_status,
            evidential_sufficiency, public_interest_met,
            voluntary_bill, returned_for_investigation,
            submitted_by, submitted_date, created_by, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'Yes', 'Yes', 'No', 'No',
                   'QA', datetime('now'), 'QA', datetime('now'), datetime('now'))""",
        (case_id, "2026-05-01", "QC Smith", "Awaiting Ruling"),
    )
    conn.commit()
    dpp_id = cur.lastrowid
    print(f"dpp_id = {dpp_id}")
    conn.close()

    results = []
    def check(name, ok, detail=""):
        results.append((name, ok))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    with app.test_client() as client:
        r = client.post("/login", data={"badge_number": "QA-ADMIN", "password": "Pw#QA!2026"})
        check("login", r.status_code == 302, f"status={r.status_code}")

        # ---- Witness statement with body ----
        BODY = "<p>On 12 May 2026 at approximately 14:35 hrs, I was at the corner of "
        BODY += "Main Street and Caledonia Road, Mandeville, when I observed...</p>"
        r = client.post("/witnesses/new", data={
            "linked_case_id": case_id,
            "witness_name": "QA Witness One",
            "witness_type": "Civilian",
            "witness_address": "1 Test Lane, Mandeville",
            "witness_phone": "876-555-0001",
            "relation_to_case": "Eye-witness",
            "statement_date": "2026-05-12",
            "statement_taken_by": "QA Admin",
            "statement_pages": "1",
            "statement_signed": "Yes",
            "witness_willing": "Yes",
            "available_for_court": "Yes",
            "record_status": "Final",
            "notes": "QA internal note",
            "statement_text": BODY,
        }, follow_redirects=False)
        check("POST /witnesses/new with body", r.status_code == 302, f"status={r.status_code}")

        # Pull statement_id back from DB
        c = models.get_db()
        row = c.execute(
            "SELECT statement_id, statement_text FROM witness_statements "
            "WHERE witness_name = ?", ("QA Witness One",)
        ).fetchone()
        c.close()
        check("statement_text persisted",
              row and row["statement_text"] and "Caledonia Road" in row["statement_text"],
              f"len={len(row['statement_text']) if row and row['statement_text'] else 0}")

        if row:
            sid = row["statement_id"]
            # Print view
            r = client.get(f"/witnesses/{sid}/print")
            check("GET /witnesses/<id>/print",
                  r.status_code == 200 and b"Witness Statement" in r.data and b"Caledonia Road" in r.data,
                  f"status={r.status_code} size={len(r.data)}")
            # PDF download
            r = client.get(f"/witnesses/{sid}/pdf")
            ok = r.status_code == 200 and r.data[:5] == b"%PDF-"
            check("GET /witnesses/<id>/pdf",
                  ok, f"status={r.status_code} size={len(r.data)} head={r.data[:10]!r}")

        # ---- Correspondence with body ----
        MEMO = "<p>This memo confirms that the case file is ready for DPP review.</p>"
        MEMO += "<p>Please find the bundled exhibits at Section 7.</p>"
        r = client.post("/correspondence/new", data={
            "direction": "Outgoing",
            "date": "2026-05-13",
            "reference_number": "FNID/A3/2026/QA",
            "from_entity": "QA Admin, FNID Area 3",
            "to_entity": "ACP CIB",
            "subject": "QA Smoke Test Memo",
            "document_type": "Memo",
            "case_id": case_id,
            "action_required": "Acknowledge receipt",
            "action_deadline": "2026-05-20",
            "notes": "",
            "body": MEMO,
        }, follow_redirects=False)
        check("POST /correspondence/new with body", r.status_code == 302, f"status={r.status_code}")
        m = re.search(r"/correspondence/(\d+)", r.headers.get("Location", ""))
        if m:
            cid = m.group(1)
            r = client.get(f"/correspondence/{cid}/print")
            check("GET /correspondence/<id>/print",
                  r.status_code == 200 and b"JAMAICA CONSTABULARY FORCE" in r.data and b"QA Smoke Test Memo" in r.data,
                  f"status={r.status_code}")
            r = client.get(f"/correspondence/{cid}/pdf")
            ok = r.status_code == 200 and r.data[:5] == b"%PDF-"
            check("GET /correspondence/<id>/pdf",
                  ok, f"status={r.status_code} size={len(r.data)}")

        # ---- DPP bundle ----
        r = client.get(f"/dpp/{dpp_id}/bundle")
        check("GET /dpp/<id>/bundle (preview)",
              r.status_code == 200 and b"DPP File Bundle" in r.data and b"QA Witness One" in r.data,
              f"status={r.status_code} size={len(r.data)}")

        r = client.get(f"/dpp/{dpp_id}/bundle.pdf")
        ok = r.status_code == 200 and r.data[:5] == b"%PDF-"
        check("GET /dpp/<id>/bundle.pdf",
              ok, f"status={r.status_code} size={len(r.data)} head={r.data[:10]!r}")

    passed = sum(1 for _, ok in results if ok)
    print(f"\n=== {passed}/{len(results)} workflow checks passed ===")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
