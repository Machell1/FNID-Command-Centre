"""Tests for case lifecycle: intake, transitions, and review scheduling."""


from fnid_portal.routes.cases import VALID_TRANSITIONS, _validate_transition


def test_case_intake_creates_case(logged_in_client, app):
    """POST to /cases/intake creates a new case record in the database."""
    resp = logged_in_client.post("/cases/intake", data={
        "classification": "Firearms - Possession",
        "parish": "Manchester",
        "offence_description": "Illegal possession of firearm during search",
        "law_and_section": "s.5 Firearms Act 2022",
        "station_code": "MAND",
        "crime_type": "major",
        "workflow_type": "non-uniformed",
        "suspect_name": "John Doe",
        "victim_name": "Jamaica Constabulary Force",
    }, follow_redirects=False)

    # Should redirect (to the case detail page)
    assert resp.status_code == 302
    location = resp.headers.get("Location", "")
    assert "/cases/" in location

    # Verify case exists in the database
    from fnid_portal.models import get_db
    with app.app_context():
        conn = get_db()
        cases = conn.execute(
            "SELECT * FROM cases WHERE classification = ?",
            ("Firearms - Possession",)
        ).fetchall()
        conn.close()

        assert len(cases) >= 1
        case = cases[0]
        assert case["current_stage"] == "intake"
        assert case["parish"] == "Manchester"
        assert case["station_code"] == "MAND"
        assert case["case_id"].startswith("MAND/")


def test_case_intake_creates_dcrr(logged_in_client, app):
    """Case intake also creates a DCRR entry linked to the case."""
    logged_in_client.post("/cases/intake", data={
        "classification": "Narcotics - Trafficking (Import/Export)",
        "parish": "St. Elizabeth",
        "offence_description": "Cocaine trafficking intercept",
        "law_and_section": "s.8 DDA",
        "station_code": "BLKR",
    }, follow_redirects=False)

    from fnid_portal.models import get_db
    with app.app_context():
        conn = get_db()
        dcrr = conn.execute(
            "SELECT * FROM dcrr WHERE station = 'BLKR'"
        ).fetchall()
        conn.close()

        assert len(dcrr) >= 1
        assert dcrr[0]["dcrr_number"].startswith("DCRR/BLKR/")


def test_valid_transitions_dict():
    """VALID_TRANSITIONS dict defines expected stage flows."""
    # Intake can go to appreciation, vetting, or assignment
    assert "appreciation" in VALID_TRANSITIONS["intake"]
    assert "vetting" in VALID_TRANSITIONS["intake"]
    assert "assignment" in VALID_TRANSITIONS["intake"]

    # Closed is a terminal state with no outgoing transitions
    assert VALID_TRANSITIONS["closed"] == set()

    # Investigation has multiple valid next stages
    assert "review" in VALID_TRANSITIONS["investigation"]
    assert "suspended" in VALID_TRANSITIONS["investigation"]
    assert "court_preparation" in VALID_TRANSITIONS["investigation"]

    # Suspended can be reopened or closed
    assert "reopened" in VALID_TRANSITIONS["suspended"]
    assert "closed" in VALID_TRANSITIONS["suspended"]


def test_validate_transition_allows_valid(app):
    """_validate_transition returns True for transitions in the matrix."""
    assert _validate_transition("intake", "vetting") is True
    assert _validate_transition("intake", "assignment") is True
    assert _validate_transition("investigation", "review") is True
    assert _validate_transition("suspended", "reopened") is True
    assert _validate_transition("cold_case", "closed") is True


def test_validate_transition_blocks_invalid(app):
    """_validate_transition returns False for transitions not in the matrix."""
    assert _validate_transition("intake", "closed") is False
    assert _validate_transition("closed", "intake") is False
    assert _validate_transition("investigation", "intake") is False
    assert _validate_transition("vetting", "closed") is False


def test_case_transition_updates_stage_in_db(app):
    """Performing a transition updates the case's current_stage in the DB."""
    with app.app_context():
        from fnid_portal.models import get_db
        from fnid_portal.routes.cases import _record_lifecycle

        # Insert a case at the investigation stage
        conn = get_db()
        case_id = "LC/SD/A3/FNID/2026/0001"
        conn.execute("""
            INSERT INTO cases (
                case_id, registration_date, classification, oic_badge,
                oic_name, oic_rank, parish, offence_description,
                law_and_section, created_by, current_stage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (case_id, "2026-01-01", "Firearms - Possession", "T001",
              "Test Officer", "Inspector", "Manchester", "Test offence",
              "s.5 Firearms Act", "Test Officer", "investigation"))
        conn.commit()

        # Validate and apply transition to 'review'
        assert _validate_transition("investigation", "review") is True
        _record_lifecycle(conn, case_id, "review", "Test Officer",
                          "Scheduled review")
        conn.commit()

        updated = conn.execute(
            "SELECT current_stage FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()
        conn.close()

        assert updated["current_stage"] == "review"


def test_case_review_scheduled_after_intake(logged_in_client, app):
    """Case intake schedules a preliminary_vetting review."""
    logged_in_client.post("/cases/intake", data={
        "classification": "Firearms - Stockpiling",
        "parish": "Clarendon",
        "offence_description": "Multiple firearms recovered",
        "law_and_section": "s.6 Firearms Act 2022",
        "station_code": "MAYP",
    }, follow_redirects=False)

    from fnid_portal.models import get_db
    with app.app_context():
        conn = get_db()
        case = conn.execute(
            "SELECT case_id FROM cases WHERE station_code = 'MAYP' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert case is not None
        case_id = case["case_id"]

        reviews = conn.execute(
            "SELECT * FROM case_reviews WHERE case_id = ? AND review_type = 'preliminary_vetting'",
            (case_id,)
        ).fetchall()
        conn.close()

        assert len(reviews) >= 1
        assert reviews[0]["status"] == "Scheduled"


def test_lifecycle_records_created(app):
    """_record_lifecycle creates an entry in case_lifecycle table."""
    with app.app_context():
        from fnid_portal.models import get_db
        from fnid_portal.routes.cases import _record_lifecycle

        conn = get_db()
        case_id = "LC/SD/A3/FNID/2026/0002"
        conn.execute("""
            INSERT INTO cases (
                case_id, registration_date, classification, oic_badge,
                oic_name, oic_rank, parish, offence_description,
                law_and_section, created_by, current_stage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (case_id, "2026-02-01", "Narcotics - Possession with Intent",
              "T002", "Another Officer", "Sergeant", "St. Elizabeth",
              "Cocaine found in vehicle", "s.8 DDA",
              "Another Officer", "intake"))
        conn.commit()

        _record_lifecycle(conn, case_id, "vetting", "Supervisor",
                          "Moved to vetting stage")
        conn.commit()

        entries = conn.execute(
            "SELECT * FROM case_lifecycle WHERE case_id = ?", (case_id,)
        ).fetchall()
        conn.close()

        assert len(entries) >= 1
        assert entries[-1]["stage"] == "vetting"
        assert entries[-1]["entered_by"] == "Supervisor"
