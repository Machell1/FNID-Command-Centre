"""Tests for chain of custody functionality."""



def _insert_case(conn, case_id="COC/SD/A3/FNID/2026/0001"):
    """Insert a minimal case for linking chain of custody records."""
    conn.execute("""
        INSERT INTO cases (
            case_id, registration_date, classification, oic_badge,
            oic_name, oic_rank, parish, offence_description,
            law_and_section, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (case_id, "2026-01-01", "Firearms - Possession", "TEST001",
          "Test Officer", "Inspector of Police", "Manchester",
          "Illegal possession of firearm",
          "s.5 Firearms Act", "Test Officer"))
    conn.commit()
    return case_id


def test_create_chain_of_custody_record(app):
    """A new chain_of_custody record is stored with all required fields."""
    with app.app_context():
        from fnid_portal.models import generate_id, get_db

        conn = get_db()
        case_id = _insert_case(conn)

        exhibit_tag = generate_id("EXH", "chain_of_custody", "exhibit_tag")
        conn.execute("""
            INSERT INTO chain_of_custody
            (exhibit_tag, exhibit_type, description, linked_case_id,
             seized_date, seized_by, seized_location, current_custodian,
             storage_location, condition, photos_taken, seal_intact,
             record_status, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (exhibit_tag, "Firearm (complete weapon)",
              "9mm pistol recovered from suspect", case_id,
              "2026-01-15", "TEST001", "Residential Premises",
              "TEST001", "FNID Evidence Room",
              "Good - no visible damage", "Yes", "Yes",
              "Draft", "Test Officer"))
        conn.commit()

        row = conn.execute(
            "SELECT * FROM chain_of_custody WHERE exhibit_tag = ?",
            (exhibit_tag,)
        ).fetchone()
        conn.close()

        assert row is not None
        assert row["exhibit_type"] == "Firearm (complete weapon)"
        assert row["linked_case_id"] == case_id
        assert row["seized_by"] == "TEST001"
        assert row["storage_location"] == "FNID Evidence Room"
        assert exhibit_tag.startswith("EXH-")


def test_transfer_logging_captures_all_fields(app):
    """Transfer fields (from, to, date, reason) are stored correctly."""
    with app.app_context():
        from fnid_portal.models import generate_id, get_db

        conn = get_db()
        case_id = _insert_case(conn, case_id="COC/SD/A3/FNID/2026/0002")
        exhibit_tag = generate_id("EXH", "chain_of_custody", "exhibit_tag")

        conn.execute("""
            INSERT INTO chain_of_custody
            (exhibit_tag, exhibit_type, description, linked_case_id,
             seized_date, seized_by, current_custodian, storage_location,
             transfer_date, transfer_from, transfer_to, transfer_reason,
             condition, seal_intact, record_status, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (exhibit_tag, "Drug Sample (for lab analysis)",
              "White powder substance - 50g", case_id,
              "2026-02-01", "TEST001", "LAB-TECH-001", "IFSLM Lab",
              "2026-02-02", "TEST001", "LAB-TECH-001",
              "Forensic analysis submission",
              "Sealed in evidence bag", "Yes", "Submitted", "Test Officer"))
        conn.commit()

        row = conn.execute(
            "SELECT * FROM chain_of_custody WHERE exhibit_tag = ?",
            (exhibit_tag,)
        ).fetchone()
        conn.close()

        assert row is not None
        assert row["transfer_from"] == "TEST001"
        assert row["transfer_to"] == "LAB-TECH-001"
        assert row["transfer_date"] == "2026-02-02"
        assert row["transfer_reason"] == "Forensic analysis submission"
        assert row["current_custodian"] == "LAB-TECH-001"


def test_seal_integrity_tracking(app):
    """Seal integrity field is stored and can be updated."""
    with app.app_context():
        from fnid_portal.models import generate_id, get_db

        conn = get_db()
        case_id = _insert_case(conn, case_id="COC/SD/A3/FNID/2026/0003")
        exhibit_tag = generate_id("EXH", "chain_of_custody", "exhibit_tag")

        conn.execute("""
            INSERT INTO chain_of_custody
            (exhibit_tag, exhibit_type, description, linked_case_id,
             seized_date, seized_by, current_custodian, storage_location,
             condition, seal_intact, record_status, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (exhibit_tag, "Ammunition (live rounds)",
              "12 rounds 9mm ammunition", case_id,
              "2026-01-20", "TEST001", "TEST001", "Evidence Room A",
              "Sealed evidence bag", "Yes", "Draft", "Test Officer"))
        conn.commit()

        # Verify initial seal state
        row = conn.execute(
            "SELECT seal_intact FROM chain_of_custody WHERE exhibit_tag = ?",
            (exhibit_tag,)
        ).fetchone()
        assert row["seal_intact"] == "Yes"

        # Simulate a broken seal during inspection
        conn.execute(
            "UPDATE chain_of_custody SET seal_intact = 'No' WHERE exhibit_tag = ?",
            (exhibit_tag,)
        )
        conn.commit()

        row = conn.execute(
            "SELECT seal_intact FROM chain_of_custody WHERE exhibit_tag = ?",
            (exhibit_tag,)
        ).fetchone()
        conn.close()

        assert row["seal_intact"] == "No"


def test_exhibit_tag_auto_generated(app):
    """generate_id produces sequential EXH-prefixed tags."""
    with app.app_context():
        from fnid_portal.models import generate_id, get_db

        tag1 = generate_id("EXH", "chain_of_custody", "exhibit_tag")
        assert tag1.startswith("EXH-")

        # Insert it so the next one increments
        conn = get_db()
        _insert_case(conn, case_id="COC/SD/A3/FNID/2026/0004")
        conn.execute("""
            INSERT INTO chain_of_custody
            (exhibit_tag, exhibit_type, description, linked_case_id,
             created_by)
            VALUES (?, 'Firearm', 'Test 1', 'COC/SD/A3/FNID/2026/0004', 'Test')
        """, (tag1,))
        conn.commit()
        conn.close()

        tag2 = generate_id("EXH", "chain_of_custody", "exhibit_tag")
        assert tag2.startswith("EXH-")
        # Sequential: second tag should have a higher number
        num1 = int(tag1.split("-")[-1])
        num2 = int(tag2.split("-")[-1])
        assert num2 == num1 + 1


def test_forensics_unit_page_loads(logged_in_client):
    """The forensics unit home page loads and shows custody records."""
    resp = logged_in_client.get("/unit/forensics")
    assert resp.status_code == 200
    assert b"Forensics" in resp.data or b"forensics" in resp.data
