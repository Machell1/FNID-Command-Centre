"""Tests for the FNID Morning Crime Report engine."""

from datetime import datetime, timedelta

from fnid_portal.mcr_engine import (
    _get_mcr_window,
    _is_fnid_relevant,
    compile_mcr,
    generate_leads_report,
)


def test_get_mcr_window_default(app):
    """MCR window spans 24 hours ending at 05:30 on the target date."""
    with app.app_context():
        today = datetime.now().date()
        window_start, window_end = _get_mcr_window(today)

        assert window_end.hour == 5
        assert window_end.minute == 30
        assert window_end.date() == today
        assert window_start == window_end - timedelta(days=1)


def test_get_mcr_window_with_string_date(app):
    """MCR window accepts a date string in YYYY-MM-DD format."""
    with app.app_context():
        window_start, window_end = _get_mcr_window("2026-03-01")
        assert window_end.date() == datetime(2026, 3, 1).date()
        assert window_end.hour == 5
        assert window_end.minute == 30


def test_is_fnid_relevant_matches_firearm_keywords():
    """_is_fnid_relevant returns True for firearm-related text."""
    assert _is_fnid_relevant("Recovered a firearm from suspect") is True
    assert _is_fnid_relevant("Illegal gun possession") is True
    assert _is_fnid_relevant("Ammunition found in vehicle") is True
    assert _is_fnid_relevant("SHOOTING incident reported") is True


def test_is_fnid_relevant_matches_narcotics_keywords():
    """_is_fnid_relevant returns True for narcotics-related text."""
    assert _is_fnid_relevant("Cocaine seized at checkpoint") is True
    assert _is_fnid_relevant("Cannabis cultivation found") is True
    assert _is_fnid_relevant("Narcotics trafficking ring") is True
    assert _is_fnid_relevant("ganja found in vehicle") is True


def test_is_fnid_relevant_returns_false_for_unrelated():
    """_is_fnid_relevant returns False for non-FNID text."""
    assert _is_fnid_relevant("Traffic accident on Highway 2000") is False
    assert _is_fnid_relevant("Missing person report filed") is False
    assert _is_fnid_relevant("Domestic dispute resolved") is False
    assert _is_fnid_relevant("") is False
    assert _is_fnid_relevant(None) is False


def test_compile_mcr_collects_entries(app):
    """compile_mcr collects entries from source tables within the window."""
    with app.app_context():
        from fnid_portal.models import get_db

        # Calculate window for tomorrow so we can insert data inside it
        target = (datetime.now() + timedelta(days=1)).date()
        window_start, window_end = _get_mcr_window(target)

        # Insert a case within the window
        mid_window = (window_start + timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        conn.execute("""
            INSERT INTO cases (
                case_id, registration_date, classification, oic_badge,
                oic_name, oic_rank, parish, offence_description,
                law_and_section, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("MCR/SD/A3/FNID/2026/0001", "2026-03-01",
              "Firearms - Possession", "T001", "Test Officer", "Inspector",
              "Manchester", "Illegal firearm seized during search warrant",
              "s.5 Firearms Act", "Test Officer", mid_window))
        conn.commit()
        conn.close()

        mcr_date, entries = compile_mcr(
            target_date=target.strftime("%Y-%m-%d"),
            compiled_by="Test Officer"
        )

        assert mcr_date == target.strftime("%Y-%m-%d")
        assert len(entries) >= 1
        # The firearm case should be flagged as FNID-relevant
        relevant = [e for e in entries if e["fnid_relevant"]]
        assert len(relevant) >= 1


def test_compile_mcr_idempotent(app):
    """Calling compile_mcr twice for the same date returns existing data."""
    with app.app_context():
        from fnid_portal.models import get_db

        target = (datetime.now() + timedelta(days=2)).date()
        window_start, window_end = _get_mcr_window(target)
        mid_window = (window_start + timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db()
        conn.execute("""
            INSERT INTO cases (
                case_id, registration_date, classification, oic_badge,
                oic_name, oic_rank, parish, offence_description,
                law_and_section, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("MCR/SD/A3/FNID/2026/0002", "2026-03-02",
              "Narcotics - Trafficking (Import/Export)", "T001",
              "Test Officer", "Inspector", "St. Elizabeth",
              "Cocaine trafficking intercept",
              "s.8 DDA", "Test Officer", mid_window))
        conn.commit()
        conn.close()

        target_str = target.strftime("%Y-%m-%d")
        date1, entries1 = compile_mcr(target_date=target_str, compiled_by="A")
        date2, entries2 = compile_mcr(target_date=target_str, compiled_by="B")

        assert date1 == date2
        assert len(entries1) == len(entries2)


def test_generate_leads_report_structure(app):
    """generate_leads_report returns a dict with expected keys."""
    with app.app_context():
        from fnid_portal.models import get_db

        # Insert MCR entries directly
        conn = get_db()
        conn.execute("""
            INSERT INTO mcr_entries
            (mcr_date, window_start, window_end, source_table, source_id,
             classification, parish, summary, fnid_relevant, compiled_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("2026-04-01", "2026-03-31 05:30:00", "2026-04-01 05:30:00",
              "cases", "RPT/001", "Firearms - Possession", "Manchester",
              "Case RPT/001: Firearm recovered", 1, "Test"))
        conn.commit()
        conn.close()

        report = generate_leads_report("2026-04-01")

        assert "mcr_date" in report
        assert report["mcr_date"] == "2026-04-01"
        assert "total_entries" in report
        assert report["total_entries"] >= 1
        assert "follow_up_lines" in report
        assert "hotspot_trends" in report
        assert "briefing_topics" in report


def test_generate_leads_report_empty_date(app):
    """generate_leads_report for a date with no entries returns a message."""
    with app.app_context():
        report = generate_leads_report("1999-01-01")
        assert "message" in report


def test_mcr_pages_render_with_history(admin_client, db):
    """MCR dashboard, report, briefing, and leads pages render stored entries."""
    db.execute("""
        INSERT INTO mcr_entries
        (mcr_date, window_start, window_end, source_table, source_id,
         classification, parish, summary, fnid_relevant, lead_suggestions,
         compiled_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ("2026-05-04", "2026-05-03 05:30:00", "2026-05-04 05:30:00",
          "cases", "FNID/SD/A3/FNID/2026/0001",
          "Firearms - Possession", "Manchester",
          "Case FNID/SD/A3/FNID/2026/0001: firearm recovered", 1,
          '["Submit for IBIS/eTrace analysis if not already done"]',
          "Admin Officer"))
    db.commit()

    for path in (
        "/mcr/",
        "/mcr/2026-05-04",
        "/mcr/2026-05-04/cr7",
        "/mcr/2026-05-04/briefing",
        "/mcr/2026-05-04/leads",
    ):
        response = admin_client.get(path)
        assert response.status_code == 200


def test_mcr_new_opens_official_cr7(admin_client):
    """The primary MCR entry path opens the official CR7 form."""
    response = admin_client.get("/mcr/new", follow_redirects=True)
    assert response.status_code == 200
    assert b"Official CR7 Morning Crime Report" in response.data
    assert b"Exact CR7 Word" in response.data
    assert b"Add a supporting MCR line entry" in response.data


def test_mcr_official_cr7_save(admin_client, db):
    """Registry can save the official CR7 Morning Crime Report form."""
    response = admin_client.post("/mcr/2026-05-04/cr7", data={
        "cr7_area_division_station_for_period": "FNID Area 3 for period test",
        "cr7_offences_s": "Firearms - Possession",
        "cr7_where_committed": "Manchester",
        "cr7_brief_of_case": "Synthetic CR7 brief of case",
        "cr7_sender_and_station": "Admin Officer - FNID Area 3",
        "form_status": "Submitted",
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Official CR7 Morning Crime Report saved as Submitted" in response.data

    row = db.execute("""
        SELECT form_id, form_type, status, form_data
        FROM mcr_cr7_forms
        WHERE mcr_date = ?
    """, ("2026-05-04",)).fetchone()
    assert row is not None
    assert row["form_id"] == "CR7/MCR/2026-05-04"
    assert row["form_type"] == "CR7"
    assert row["status"] == "Submitted"
    assert "Synthetic CR7 brief of case" in row["form_data"]


def test_mcr_manual_entry_form_and_post(admin_client, db):
    """Registry can manually enter a supporting MCR line item."""
    form_response = admin_client.get("/mcr/entries/new")
    assert form_response.status_code == 200
    assert b"Add Supporting MCR Line Entry" in form_response.data
    assert b"Source Reference No." in form_response.data

    post_response = admin_client.post("/mcr/entries/new", data={
        "mcr_date": "2026-05-04",
        "source_table": "Major Crime Register",
        "source_id": "MCR/2026/0007",
        "classification": "Firearms - Possession",
        "parish": "Manchester",
        "summary": "Synthetic MCR matter: firearm recovered during patrol.",
        "fnid_relevant": "1",
        "lead_suggestions": "Submit firearm for ballistic analysis",
    }, follow_redirects=True)

    assert post_response.status_code == 200
    assert b"MCR matter entered successfully" in post_response.data
    assert b"Synthetic MCR matter" in post_response.data

    row = db.execute("""
        SELECT source_table, source_id, fnid_relevant, lead_suggestions
        FROM mcr_entries
        WHERE mcr_date = ? AND source_id = ?
    """, ("2026-05-04", "MCR/2026/0007")).fetchone()
    assert row is not None
    assert row["source_table"] == "Major Crime Register"
    assert row["fnid_relevant"] == 1
    assert "ballistic analysis" in row["lead_suggestions"]
