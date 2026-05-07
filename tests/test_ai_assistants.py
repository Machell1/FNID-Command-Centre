"""Internal AI assistant harness tests."""

from fnid_portal.ai_assistant_engine import (
    _external_context_for_ai,
    _outbound_block_reason,
    seed_agent_profiles,
)
from fnid_portal.secret_keys import get_secret, has_secret


def _create_case(db, case_id="FNID/SD/A3/FNID/2026/7701"):
    db.execute(
        """
        INSERT INTO cases (case_id, registration_date, classification,
            oic_badge, oic_name, oic_rank, parish, offence_description,
            law_and_section, suspect_name, suspect_dob, suspect_address,
            victim_name, victim_address, created_by)
        VALUES (?, '2026-05-04', 'Firearms - Possession',
            'ADMIN', 'Admin Officer', 'Inspector', 'Manchester',
            'Assistant harness test case', 's.35 Firearms Act',
            'Redacted Suspect', '1990-01-01', 'Manchester',
            'Redacted Complainant', 'Manchester', 'Admin')
        """,
        (case_id,),
    )
    db.commit()
    return case_id


def _enable_assistant(db, agent_key="dcr_vetting"):
    seed_agent_profiles(db, "ADMIN")
    db.execute(
        "UPDATE system_settings SET value = 'true' WHERE key = 'ai_assistants_global_enabled'"
    )
    db.execute(
        """
        UPDATE assistant_agent_profiles
        SET enabled = 1, automation_mode = 'assistive', requires_human_approval = 1
        WHERE agent_key = ?
        """,
        (agent_key,),
    )
    db.commit()


def test_assistant_dashboard_and_workstation_load(admin_client):
    resp = admin_client.get("/assistants/")
    assert resp.status_code == 200
    assert b"AI Work Assistants" in resp.data

    workstation = admin_client.get("/assistants/workstation")
    assert workstation.status_code == 200
    assert b"Registry Continuous Vetting Queue" in workstation.data


def test_assistant_run_is_blocked_until_enabled(admin_client, db):
    case_id = _create_case(db)

    resp = admin_client.post(
        "/assistants/run/dcr_vetting",
        data={"case_id": case_id, "guidance": "Run a controlled vetting scan."},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert b"AI assistants are globally disabled" in resp.data


def test_assistant_proposes_registry_task_and_supports_rollback(admin_client, db):
    case_id = _create_case(db)
    _enable_assistant(db)

    resp = admin_client.post(
        "/assistants/run/dcr_vetting",
        data={"case_id": case_id, "guidance": "Check registry pipeline readiness."},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert b"Proposed And Applied Actions" in resp.data

    action = db.execute(
        """
        SELECT * FROM assistant_actions
        WHERE case_id = ? AND action_type = 'create_registry_task'
        ORDER BY id LIMIT 1
        """,
        (case_id,),
    ).fetchone()
    assert action is not None
    assert action["status"] == "proposed"

    apply_resp = admin_client.post(
        f"/assistants/actions/{action['id']}/apply",
        data={"approval_note": "Approved in harness test."},
        follow_redirects=True,
    )
    assert apply_resp.status_code == 200
    assert b"Assistant action applied" in apply_resp.data

    card = db.execute(
        "SELECT * FROM investigator_cards WHERE case_id = ? AND assignment_type = 'assistant_task'",
        (case_id,),
    ).fetchone()
    assert card is not None
    assert card["status"] == "Active"

    rollback_resp = admin_client.post(
        f"/assistants/actions/{action['id']}/rollback",
        data={"rollback_notes": "Rollback in harness test."},
        follow_redirects=True,
    )
    assert rollback_resp.status_code == 200
    assert b"rolled back" in rollback_resp.data

    rolled_back = db.execute(
        "SELECT status FROM investigator_cards WHERE id = ?",
        (card["id"],),
    ).fetchone()
    assert rolled_back["status"] == "Rolled Back"


def test_external_ai_context_is_metadata_only():
    context = {
        "case_id": "FNID/SD/A3/FNID/2026/7701",
        "primary_register_number": "DCRR/FNID/2026/0001",
        "primary_register_type": "dcrr",
        "classification": "Firearms - Possession",
        "current_stage": "intake",
        "case_status": "Open - Active Investigation",
        "suspect_name": "Sensitive Suspect",
        "victim_name": "Sensitive Victim",
        "notes": "Sensitive operational notes",
        "forms": [{"form_type": "CR1", "status": "Draft", "created_by": "ADMIN"}],
        "reviews": [{"review_type": "14-Day Review", "scheduled_date": "2026-05-20", "status": "Scheduled"}],
    }

    external = _external_context_for_ai(context)
    text = str(external)

    assert external["case_reference"] == "[redacted]"
    assert "Sensitive Suspect" not in text
    assert "Sensitive Victim" not in text
    assert "Sensitive operational notes" not in text
    assert "FNID/SD/A3/FNID/2026/7701" not in text
    assert "DCRR/FNID/2026/0001" not in text
    assert not _outbound_block_reason({"messages": [{"content": str(external)}]})


def test_outbound_guard_blocks_internal_identifiers():
    reason = _outbound_block_reason({
        "messages": [{
            "content": '{"case_id": "FNID/SD/A3/FNID/2026/7701", "suspect_name": "X"}'
        }]
    })

    assert "blocked sensitive key" in reason


def test_local_secret_loader_reads_jobsy_style_files(tmp_path, monkeypatch):
    secret_dir = tmp_path / "Jobsy resources"
    secret_dir.mkdir()
    (secret_dir / "Tavily API.txt").write_text("tvly-test-secret\n", encoding="utf-8")

    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setenv("FNID_LOCAL_SECRET_DIR", str(secret_dir))

    assert has_secret("TAVILY_API_KEY")
    assert get_secret("TAVILY_API_KEY") == "tvly-test-secret"
