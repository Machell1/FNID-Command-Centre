"""Official JCF CR form clone tests."""

import json

from fnid_portal.official_cr_forms import OFFICIAL_CR_FORM_TYPES, get_form_layout


def _create_case(db, case_id="CR-OFFICIAL-001"):
    db.execute("""
        INSERT INTO cases (case_id, registration_date, classification,
            oic_badge, oic_name, oic_rank, parish, offence_description,
            law_and_section, suspect_name, suspect_dob, suspect_address,
            victim_name, victim_address, created_by)
        VALUES (?, '2026-01-01', 'Firearms - Possession',
            'ADMIN', 'Admin Officer', 'Inspector', 'Manchester',
            'Test offence', 's.5 Firearms Act', 'John Brown',
            '1990-01-01', 'Mandeville', 'Jane Brown', 'Manchester', 'Admin')
    """, (case_id,))
    db.commit()
    return case_id


def test_policy_library_marks_cr10_unavailable(admin_client):
    resp = admin_client.get("/policy/forms")
    assert resp.status_code == 200
    assert b"CR10" in resp.data
    assert b"Coming Soon" in resp.data


def test_all_official_word_templates_are_primary(admin_client):
    for form_type in OFFICIAL_CR_FORM_TYPES:
        resp = admin_client.get(f"/policy/forms/{form_type}/blank", follow_redirects=True)
        assert resp.status_code == 200, form_type
        assert ".docx" in resp.headers["Content-Disposition"]

        browser_resp = admin_client.get(f"/policy/forms/{form_type}/browser")
        assert browser_resp.status_code == 200, form_type
        assert form_type.encode() in browser_resp.data
        assert b"jcf-paper" in browser_resp.data
        assert b"<input" in browser_resp.data or b"<textarea" in browser_resp.data

    print_resp = admin_client.get("/policy/forms/CR1/print", follow_redirects=True)
    assert print_resp.status_code == 200
    assert ".docx" in print_resp.headers["Content-Disposition"]

    download_resp = admin_client.get("/policy/forms/CR1/download")
    assert download_resp.status_code == 200
    assert ".docx" in download_resp.headers["Content-Disposition"]


def test_cr2_blank_form_preserves_word_geometry(admin_client):
    """CR2 should render from the uploaded DOCX table geometry, not a generic form."""
    layout = get_form_layout("CR2")
    tables = [element for element in layout["elements"] if element["kind"] == "table"]

    assert layout["page"]["width_in"] == 8.5
    assert layout["page"]["height_in"] == 11
    assert len(tables[0]["grid"]) == 10
    assert any(
        cell.get("rowspan", 1) > 1
        for row in tables[0]["rows"]
        for cell in row["cells"]
    )

    resp = admin_client.get("/policy/forms/CR2/browser")
    assert resp.status_code == 200
    assert b"<colgroup>" in resp.data
    assert b"rowspan=" in resp.data
    assert b"jcf-field-cell" in resp.data


def test_all_official_new_forms_load(admin_client, db):
    case_id = _create_case(db)
    for form_type in OFFICIAL_CR_FORM_TYPES:
        resp = admin_client.get(f"/cases/{case_id}/forms/new/{form_type}")
        assert resp.status_code == 200, form_type
        assert form_type.encode() in resp.data
        assert b"CR-OFFICIAL-001" in resp.data
        assert b"jcf-paper" in resp.data


def test_case_detail_links_official_forms_workflow(admin_client, db):
    case_id = _create_case(db)
    db.execute(
        """
        INSERT INTO cr_forms (form_id, case_id, form_type, form_data, status, created_by)
        VALUES ('CR1-DETAIL-TEST', ?, 'CR1', '{}', 'Draft', 'Admin')
        """,
        (case_id,),
    )
    db.commit()
    row = db.execute("SELECT * FROM cr_forms WHERE form_id = 'CR1-DETAIL-TEST'").fetchone()

    resp = admin_client.get(f"/cases/{case_id}")

    assert resp.status_code == 200
    assert b"Investigator Forms" in resp.data
    assert b"Team Lead Review" in resp.data
    assert f"/cases/{case_id}/forms".encode() in resp.data
    assert f"/cases/{case_id}/forms/{row['id']}/edit".encode() in resp.data
    assert f"/cases/{case_id}/forms/{row['id']}/print".encode() in resp.data
    assert b"/policy/forms/CR1/download" in resp.data


def test_saved_official_form_renders_read_only_print(admin_client, db):
    case_id = _create_case(db)
    layout = get_form_layout("CR1")
    field_name = next(field["name"] for field in layout["fields"] if field["type"] != "checkbox")

    resp = admin_client.post(
        f"/cases/{case_id}/forms/new/CR1",
        data={field_name: "Official test value", "form_status": "Submitted"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    row = db.execute("SELECT * FROM cr_forms WHERE case_id = ? AND form_type = 'CR1'", (case_id,)).fetchone()
    assert row is not None
    saved = json.loads(row["form_data"])
    assert saved[field_name] == "Official test value"

    print_resp = admin_client.get(f"/cases/{case_id}/forms/{row['id']}/print")
    assert print_resp.status_code == 200
    assert b"Official test value" in print_resp.data
    assert b"<input" not in print_resp.data
    assert b"<textarea" not in print_resp.data


def test_policy_case_reference_with_slashes_routes_and_exports(admin_client, db):
    case_id = _create_case(db, "FNID/SD/A3/FNID/2026/9999")

    detail_resp = admin_client.get(f"/cases/{case_id}")
    assert detail_resp.status_code == 200
    assert case_id.encode() in detail_resp.data

    forms_resp = admin_client.get(f"/cases/{case_id}/forms")
    assert forms_resp.status_code == 200
    assert b"Investigator Section" in forms_resp.data
    assert f"/cases/{case_id}/forms/new/CR1/docx".encode() in forms_resp.data

    word_resp = admin_client.get(f"/cases/{case_id}/forms/new/CR1/docx")
    assert word_resp.status_code == 200
    assert ".docx" in word_resp.headers["Content-Disposition"]

    new_resp = admin_client.get(f"/cases/{case_id}/forms/new/CR1")
    assert new_resp.status_code == 200
    assert case_id.encode() in new_resp.data

    layout = get_form_layout("CR1")
    field_name = next(field["name"] for field in layout["fields"] if field["type"] != "checkbox")
    save_resp = admin_client.post(
        f"/cases/{case_id}/forms/new/CR1",
        data={field_name: "Slash case reference export", "form_status": "Draft"},
        follow_redirects=True,
    )
    assert save_resp.status_code == 200

    row = db.execute("SELECT * FROM cr_forms WHERE case_id = ? AND form_type = 'CR1'", (case_id,)).fetchone()
    assert row is not None

    pdf_resp = admin_client.get(f"/cases/{case_id}/forms/{row['id']}/pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.mimetype == "application/pdf"
    assert 'filename="CR1_FNID-SD-A3-FNID-2026-9999.pdf"' in pdf_resp.headers["Content-Disposition"]
