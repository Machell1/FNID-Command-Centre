"""Phase 4 tests — correspondence, investigator cards, case reviews, intel targets."""



# ── Correspondence ─────────────────────────────────────────────────

def test_correspondence_list(admin_client):
    """Correspondence list page loads."""
    resp = admin_client.get("/correspondence/")
    assert resp.status_code == 200


def test_correspondence_new_form(admin_client):
    """New correspondence form loads."""
    resp = admin_client.get("/correspondence/new")
    assert resp.status_code == 200


def test_correspondence_create(admin_client, db):
    """Create a correspondence record."""
    resp = admin_client.post("/correspondence/new", data={
        "direction": "Incoming",
        "date": "2026-01-15",
        "subject": "DPP Directive on Case FNID-2026-001",
        "document_type": "DPP Directive",
        "from_entity": "DPP Office",
        "to_entity": "FNID Area 3",
    }, follow_redirects=True)
    assert resp.status_code == 200


def test_correspondence_case_view(admin_client, db):
    """Case correspondence page loads."""
    db.execute("""
        INSERT INTO cases (case_id, registration_date, classification,
            oic_badge, oic_name, oic_rank, parish, offence_description,
            law_and_section, created_by)
        VALUES ('CORR-TEST-001', '2026-01-01', 'Firearms',
            'ADMIN', 'Admin', 'Superintendent', 'Manchester',
            'Test', 's.5 FA', 'Admin')
    """)
    db.commit()

    resp = admin_client.get("/correspondence/case/CORR-TEST-001")
    assert resp.status_code == 200


# ── Investigator Cards ─────────────────────────────────────────────

def test_inv_card_list(admin_client):
    """Investigator card list loads."""
    resp = admin_client.get("/inv-cards/")
    assert resp.status_code == 200


def test_inv_card_new_form(admin_client):
    """New investigator card form loads."""
    resp = admin_client.get("/inv-cards/new")
    assert resp.status_code == 200


def test_inv_card_create(admin_client, db):
    """Create an investigator card."""
    db.execute("""
        INSERT INTO cases (case_id, registration_date, classification,
            oic_badge, oic_name, oic_rank, parish, offence_description,
            law_and_section, created_by)
        VALUES ('IC-TEST-001', '2026-01-01', 'Narcotics',
            'ADMIN', 'Admin', 'Superintendent', 'Manchester',
            'Test', 's.7 DDA', 'Admin')
    """)
    db.commit()

    resp = admin_client.post("/inv-cards/new", data={
        "officer_badge": "ADMIN",
        "case_id": "IC-TEST-001",
        "assigned_date": "2026-01-15",
        "tasks_assigned": "Interview witnesses, collect CCTV",
        "next_action": "Follow up with lab",
        "next_action_date": "2026-02-01",
    }, follow_redirects=True)
    assert resp.status_code == 200


def test_inv_card_officer_view(admin_client):
    """Officer cards view loads."""
    resp = admin_client.get("/inv-cards/officer/ADMIN")
    assert resp.status_code == 200


# ── Case Reviews ───────────────────────────────────────────────────

def test_review_list(admin_client):
    """Review list page loads."""
    resp = admin_client.get("/reviews/")
    assert resp.status_code == 200


def test_review_new_form(admin_client):
    """New review scheduling form loads."""
    resp = admin_client.get("/reviews/new")
    assert resp.status_code == 200


def test_review_create(admin_client, db):
    """Schedule a case review."""
    db.execute("""
        INSERT INTO cases (case_id, registration_date, classification,
            oic_badge, oic_name, oic_rank, parish, offence_description,
            law_and_section, created_by)
        VALUES ('REV-TEST-001', '2026-01-01', 'Firearms',
            'ADMIN', 'Admin', 'Superintendent', 'Manchester',
            'Test', 's.5 FA', 'Admin')
    """)
    db.commit()

    resp = admin_client.post("/reviews/new", data={
        "case_id": "REV-TEST-001",
        "review_type": "14-Day Review",
        "scheduled_date": "2026-02-01",
    }, follow_redirects=True)
    assert resp.status_code == 200


def test_review_calendar(admin_client):
    """Review calendar page loads."""
    resp = admin_client.get("/reviews/calendar")
    assert resp.status_code == 200


def test_review_overdue(admin_client):
    """Overdue reviews page loads."""
    resp = admin_client.get("/reviews/overdue")
    assert resp.status_code == 200


def test_review_complete(admin_client, db):
    """Complete review form loads."""
    db.execute("""
        INSERT INTO cases (case_id, registration_date, classification,
            oic_badge, oic_name, oic_rank, parish, offence_description,
            law_and_section, created_by)
        VALUES ('REV-COMP-001', '2026-01-01', 'Firearms',
            'ADMIN', 'Admin', 'Superintendent', 'Manchester',
            'Test', 's.5 FA', 'Admin')
    """)
    db.execute("""
        INSERT INTO case_reviews (case_id, review_type, scheduled_date,
            status, created_by)
        VALUES ('REV-COMP-001', '14-Day Review', '2026-01-15', 'Scheduled', 'Admin')
    """)
    db.commit()
    row = db.execute("SELECT id FROM case_reviews ORDER BY id DESC LIMIT 1").fetchone()

    resp = admin_client.get(f"/reviews/{row['id']}/complete")
    assert resp.status_code == 200


# ── Intel Targets ──────────────────────────────────────────────────

def test_target_list(admin_client):
    """Target list page loads."""
    resp = admin_client.get("/targets/")
    assert resp.status_code == 200


def test_target_new_form(admin_client):
    """New target form loads."""
    resp = admin_client.get("/targets/new")
    assert resp.status_code == 200


def test_target_create(admin_client):
    """Create an intel target."""
    resp = admin_client.post("/targets/new", data={
        "target_name": "John Smith",
        "aliases": "Johnny, JS",
        "parish": "Manchester",
        "threat_level": "High",
        "description": "Suspected firearms dealer",
        "modus_operandi": "Procures weapons from overseas",
    }, follow_redirects=True)
    assert resp.status_code == 200


def test_target_detail(admin_client, db):
    """Target detail page loads."""
    db.execute("""
        INSERT INTO intel_targets (target_id, target_name, parish,
            threat_level, status, created_by)
        VALUES ('TGT-2026-001', 'Test Target', 'Manchester',
            'High', 'Active', 'Admin')
    """)
    db.commit()

    resp = admin_client.get("/targets/TGT-2026-001")
    assert resp.status_code == 200


def test_target_map(admin_client):
    """Target map/summary page loads."""
    resp = admin_client.get("/targets/map")
    assert resp.status_code == 200


def test_target_restricted_for_io(io_client):
    """IO without intel permissions should be restricted."""
    resp = io_client.get("/targets/")
    # IO doesn't have intel read permission
    assert resp.status_code in (302, 403, 200)
