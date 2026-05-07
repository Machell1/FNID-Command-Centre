"""Tests for the FNID case reference number engine."""

from datetime import datetime

from fnid_portal.case_numbers import (
    STATION_CODES,
    generate_case_reference,
    generate_dcrr_number,
    generate_form_id,
    parse_case_reference,
)


def test_generate_case_reference_format(app):
    """Case reference follows {station}/{diary}/{division}/{unit}/{year}/{seq} format."""
    with app.app_context():
        ref = generate_case_reference()
        parts = ref.split("/")
        assert len(parts) == 6
        # Default components
        assert parts[0] == "FNID"       # default station
        assert parts[1] == "SD"         # default diary type
        assert parts[2] == "A3"         # default division
        assert parts[3] == "FNID"       # default unit
        assert parts[4] == str(datetime.now().year)
        assert parts[5].isdigit()
        assert len(parts[5]) == 4       # zero-padded to 4 digits


def test_generate_case_reference_sequential(app):
    """Without DB insert, generate_case_reference returns the same sequence."""
    with app.app_context():
        ref1 = generate_case_reference()
        ref2 = generate_case_reference()
        # Without inserting ref1 into the DB, both calls return the same sequence
        # because _next_sequence finds no existing records
        assert ref1 == ref2


def test_generate_case_reference_custom_station(app):
    """Custom station code is included in the reference."""
    with app.app_context():
        ref = generate_case_reference(station_code="MAND")
        assert ref.startswith("MAND/")


def test_station_codes_mapping():
    """STATION_CODES dict contains expected entries."""
    assert STATION_CODES["mandeville"] == "MAND"
    assert STATION_CODES["fnid_hq"] == "FNID"
    assert "christiana" in STATION_CODES


def test_generate_dcrr_number_format(app):
    """DCRR number follows DCRR/{station}/{year}/{seq} format."""
    with app.app_context():
        dcrr = generate_dcrr_number()
        parts = dcrr.split("/")
        assert len(parts) == 4
        assert parts[0] == "DCRR"
        assert parts[1] == "FNID"
        assert parts[2] == str(datetime.now().year)
        assert parts[3].isdigit()
        assert len(parts[3]) == 4


def test_generate_form_id_format(app):
    """Form ID follows {form_type}/{case_id}/{seq} format."""
    with app.app_context():
        case_id = "FNID/SD/A3/FNID/2026/0001"
        form_id = generate_form_id("CR1", case_id)
        assert form_id.startswith(f"CR1/{case_id}/")
        seq = form_id.rsplit("/", 1)[-1]
        assert seq.isdigit()
        assert len(seq) == 3


def test_parse_case_reference_valid():
    """parse_case_reference splits a valid reference into components."""
    ref = "MAND/SD/A3/FNID/2026/0042"
    result = parse_case_reference(ref)
    assert result["station"] == "MAND"
    assert result["diary_type"] == "SD"
    assert result["division"] == "A3"
    assert result["unit"] == "FNID"
    assert result["year"] == "2026"
    assert result["sequence"] == "0042"


def test_parse_case_reference_short():
    """parse_case_reference returns raw value for short/invalid references."""
    result = parse_case_reference("INVALID")
    assert "raw" in result
    assert result["raw"] == "INVALID"


def test_sequential_numbering_with_db_insert(app):
    """After inserting a case into the DB, the next sequence increments."""
    with app.app_context():
        from fnid_portal.models import get_db

        ref1 = generate_case_reference(station_code="MAND")
        # Insert the first reference so the sequence tracker can find it
        conn = get_db()
        conn.execute("""
            INSERT INTO cases (
                case_id, registration_date, classification, oic_badge,
                oic_name, oic_rank, parish, offence_description,
                law_and_section, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ref1, "2026-01-01", "Firearms - Possession", "T001",
              "Test Officer", "Inspector", "Manchester", "Test offence",
              "s.5 Firearms Act", "Test Officer"))
        conn.commit()
        conn.close()

        ref2 = generate_case_reference(station_code="MAND")
        seq1 = int(ref1.rsplit("/", 1)[-1])
        seq2 = int(ref2.rsplit("/", 1)[-1])
        assert seq2 == seq1 + 1, f"Expected {seq1 + 1}, got {seq2}"


def test_dcrr_custom_station_code(app):
    """Custom station code is embedded in DCRR number."""
    with app.app_context():
        dcrr = generate_dcrr_number(station_code="BLKR")
        assert dcrr.startswith("DCRR/BLKR/")
