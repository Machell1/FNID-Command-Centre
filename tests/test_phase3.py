"""Phase 3 tests — DPP pipeline, SOP checklists, witness statements, disclosure log."""



# ── DPP Pipeline ───────────────────────────────────────────────────

def test_dpp_pipeline_home(admin_client):
    """DPP pipeline dashboard loads."""
    resp = admin_client.get("/dpp/")
    assert resp.status_code == 200
    assert b"DPP" in resp.data or b"Pipeline" in resp.data


def test_dpp_new_form(admin_client):
    """New DPP submission form loads."""
    resp = admin_client.get("/dpp/new")
    assert resp.status_code == 200


def test_dpp_create_entry(admin_client, db):
    """Create a DPP pipeline entry."""
    # First create a case to link
    db.execute("""
        INSERT INTO cases (case_id, registration_date, classification,
            oic_badge, oic_name, oic_rank, parish, offence_description,
            law_and_section, created_by)
        VALUES ('DPP-TEST-001', '2026-01-01', 'Firearms - Possession',
            'ADMIN', 'Admin', 'Superintendent', 'Manchester',
            'Test offence', 's.5 Firearms Act', 'Admin')
    """)
    db.commit()

    resp = admin_client.post("/dpp/new", data={
        "linked_case_id": "DPP-TEST-001",
        "classification": "Firearms - Possession",
        "oic_name": "Admin",
        "suspect_name": "Test Suspect",
        "offence_summary": "Illegal possession of firearm",
        "dpp_status": "Submitted",
    }, follow_redirects=True)
    assert resp.status_code == 200


def test_dpp_detail_page(admin_client, db):
    """DPP detail page loads for an existing entry."""
    db.execute("""
        INSERT INTO dpp_pipeline (linked_case_id, classification, oic_name,
            suspect_name, offence_summary, dpp_status, created_by)
        VALUES ('CASE-001', 'Narcotics', 'Insp. Jones', 'John Doe',
            'Drug trafficking', 'Submitted', 'Admin')
    """)
    db.commit()
    row = db.execute("SELECT id FROM dpp_pipeline ORDER BY id DESC LIMIT 1").fetchone()

    resp = admin_client.get(f"/dpp/{row['id']}")
    assert resp.status_code == 200


# ── SOP Checklists ─────────────────────────────────────────────────

def test_sop_list(admin_client):
    """SOP checklist list page loads."""
    resp = admin_client.get("/sop/")
    assert resp.status_code == 200
    assert b"SOP" in resp.data or b"Compliance" in resp.data


def test_sop_new_form(admin_client):
    """New SOP checklist form loads."""
    resp = admin_client.get("/sop/new")
    assert resp.status_code == 200


def test_sop_create(admin_client, db):
    """Create an SOP checklist."""
    db.execute("""
        INSERT INTO cases (case_id, registration_date, classification,
            oic_badge, oic_name, oic_rank, parish, offence_description,
            law_and_section, created_by)
        VALUES ('SOP-TEST-001', '2026-01-01', 'Narcotics - Possession',
            'ADMIN', 'Admin', 'Superintendent', 'Manchester',
            'Drug possession', 's.7 DDA', 'Admin')
    """)
    db.commit()

    resp = admin_client.post("/sop/new", data={
        "linked_case_id": "SOP-TEST-001",
        "oic_name": "Admin",
        "station_diary_entry": "Yes",
        "crime_report_filed": "Yes",
        "scene_log_started": "No",
    }, follow_redirects=True)
    assert resp.status_code == 200


def test_sop_detail(admin_client, db):
    """SOP detail page loads."""
    db.execute("""
        INSERT INTO sop_checklists (linked_case_id, oic_name, created_by)
        VALUES ('CASE-001', 'Admin', 'Admin')
    """)
    db.commit()
    row = db.execute("SELECT id FROM sop_checklists ORDER BY id DESC LIMIT 1").fetchone()

    resp = admin_client.get(f"/sop/{row['id']}")
    assert resp.status_code == 200


def test_sop_case_compliance(admin_client, db):
    """Case compliance summary loads."""
    db.execute("""
        INSERT INTO cases (case_id, registration_date, classification,
            oic_badge, oic_name, oic_rank, parish, offence_description,
            law_and_section, created_by)
        VALUES ('SOP-COMP-001', '2026-01-01', 'Firearms',
            'ADMIN', 'Admin', 'Superintendent', 'Manchester',
            'Test', 's.5 FA', 'Admin')
    """)
    # Also create a checklist for the case so it doesn't redirect
    db.execute("""
        INSERT INTO sop_checklists (linked_case_id, oic_name, created_by)
        VALUES ('SOP-COMP-001', 'Admin', 'Admin')
    """)
    db.commit()

    resp = admin_client.get("/sop/compliance/SOP-COMP-001")
    assert resp.status_code == 200


# ── Witness Statements ─────────────────────────────────────────────

def test_witness_list(logged_in_client):
    """Witness list page loads."""
    resp = logged_in_client.get("/witnesses/")
    assert resp.status_code == 200


def test_witness_new_form(logged_in_client):
    """New witness form loads."""
    resp = logged_in_client.get("/witnesses/new")
    assert resp.status_code == 200


def test_witness_create(admin_client, db):
    """Create a witness statement record."""
    db.execute("""
        INSERT INTO cases (case_id, registration_date, classification,
            oic_badge, oic_name, oic_rank, parish, offence_description,
            law_and_section, created_by)
        VALUES ('WIT-TEST-001', '2026-01-01', 'Firearms',
            'ADMIN', 'Admin', 'Superintendent', 'Manchester',
            'Test', 's.5 FA', 'Admin')
    """)
    db.commit()

    resp = admin_client.post("/witnesses/new", data={
        "linked_case_id": "WIT-TEST-001",
        "witness_name": "Jane Doe",
        "witness_type": "Eyewitness",
        "statement_date": "2026-01-15",
    }, follow_redirects=True)
    assert resp.status_code == 200


def test_witness_case_view(admin_client, db):
    """Case witnesses page loads."""
    db.execute("""
        INSERT INTO cases (case_id, registration_date, classification,
            oic_badge, oic_name, oic_rank, parish, offence_description,
            law_and_section, created_by)
        VALUES ('WIT-CASE-001', '2026-01-01', 'Firearms',
            'ADMIN', 'Admin', 'Superintendent', 'Manchester',
            'Test', 's.5 FA', 'Admin')
    """)
    db.commit()

    resp = admin_client.get("/witnesses/case/WIT-CASE-001")
    assert resp.status_code == 200


# ── Disclosure Log ─────────────────────────────────────────────────

def test_disclosure_list(logged_in_client):
    """Disclosure list page loads."""
    resp = logged_in_client.get("/disclosure/")
    assert resp.status_code == 200


def test_disclosure_new_form(logged_in_client):
    """New disclosure form loads."""
    resp = logged_in_client.get("/disclosure/new")
    assert resp.status_code == 200


def test_disclosure_create(admin_client, db):
    """Create a disclosure record."""
    db.execute("""
        INSERT INTO cases (case_id, registration_date, classification,
            oic_badge, oic_name, oic_rank, parish, offence_description,
            law_and_section, created_by)
        VALUES ('DIS-TEST-001', '2026-01-01', 'Narcotics',
            'ADMIN', 'Admin', 'Superintendent', 'Manchester',
            'Test', 's.7 DDA', 'Admin')
    """)
    db.commit()

    resp = admin_client.post("/disclosure/new", data={
        "linked_case_id": "DIS-TEST-001",
        "disclosure_type": "Initial",
        "material_disclosed": "Witness statements bundle",
    }, follow_redirects=True)
    assert resp.status_code == 200


def test_disclosure_case_view(admin_client, db):
    """Case disclosures page loads."""
    db.execute("""
        INSERT INTO cases (case_id, registration_date, classification,
            oic_badge, oic_name, oic_rank, parish, offence_description,
            law_and_section, created_by)
        VALUES ('DIS-CASE-001', '2026-01-01', 'Narcotics',
            'ADMIN', 'Admin', 'Superintendent', 'Manchester',
            'Test', 's.7 DDA', 'Admin')
    """)
    db.commit()

    resp = admin_client.get("/disclosure/case/DIS-CASE-001")
    assert resp.status_code == 200
