"""
FNID Workflow Engine

Enforces proper data handoff between units and validates stage transitions
per JCF Case Management Policy (JCF/FW/PL/C&S/0001/2024).
"""

from .models import get_db

# Valid stage transitions per policy
VALID_TRANSITIONS = {
    "intake": {"appreciation", "vetting", "assignment"},
    "appreciation": {"vetting", "assignment"},
    "vetting": {"assignment", "suspended"},
    "assignment": {"investigation"},
    "investigation": {"follow_up", "review", "court_preparation", "suspended", "cleared"},
    "follow_up": {"review", "investigation", "court_preparation", "suspended", "cleared"},
    "review": {"investigation", "follow_up", "court_preparation", "suspended", "cleared", "closed"},
    "court_preparation": {"before_court", "investigation"},
    "before_court": {"cleared", "closed", "investigation"},
    "suspended": {"reopened", "closed", "cold_case"},
    "reopened": {"investigation"},
    "cold_case": {"reopened", "closed"},
    "cleared": {"closed"},
    "closed": set(),
}


# Required data points per stage for transition validation
STAGE_REQUIREMENTS = {
    "intake": {
        "required": ["offence_description", "law_and_section", "parish"],
        "legal_basis": "Case Management Policy s.9.1",
    },
    "appreciation": {
        "required": ["classification", "law_and_section"],
        "legal_basis": "Case Management Policy s.9.1",
    },
    "vetting": {
        "required": ["classification"],
        "legal_basis": "Case Management Policy s.9.2",
    },
    "assignment": {
        "required": ["assigned_io_badge", "oic_name"],
        "legal_basis": "Case Management Policy s.9.2.2",
    },
    "investigation": {
        "required": ["assigned_io_badge"],
        "legal_basis": "Case Management Policy s.9.3",
    },
    "court_preparation": {
        "required": ["court_type"],
        "legal_basis": "Bail Act 2023, Evidence Act, DPP Disclosure Protocol 2013",
    },
    "before_court": {
        "required": ["court_type", "next_court_date"],
        "legal_basis": "Gun Court Act 1974 (firearms cases)",
    },
    "suspended": {
        "required": ["suspended_reason"],
        "legal_basis": "Case Management Policy s.9.3.9",
    },
    "cleared": {
        "required": ["case_status"],
        "legal_basis": "Case Management Policy s.6.3.3",
    },
    "closed": {
        "required": ["closed_reason"],
        "legal_basis": "Case Management Policy s.6.3.4",
    },
}


def validate_stage_transition(case_id, from_stage, to_stage):
    """Validate whether a case can transition between stages.

    Returns (is_valid, errors) tuple.
    """
    errors = []

    # Check transition is valid
    allowed = VALID_TRANSITIONS.get(from_stage, set())
    if to_stage not in allowed:
        errors.append(f"Cannot transition from '{from_stage}' to '{to_stage}'.")
        return False, errors

    # Check required data for target stage
    requirements = STAGE_REQUIREMENTS.get(to_stage, {})
    required_fields = requirements.get("required", [])

    if required_fields:
        conn = get_db()
        try:
            case = conn.execute(
                "SELECT * FROM cases WHERE case_id = ?", (case_id,)
            ).fetchone()
            if not case:
                errors.append(f"Case {case_id} not found.")
                return False, errors

            for field in required_fields:
                val = case[field] if field in case.keys() else None
                if not val or val == "":
                    errors.append(
                        f"Missing required field '{field}' for stage '{to_stage}' "
                        f"(per {requirements.get('legal_basis', 'policy')})."
                    )
        finally:
            conn.close()

    return len(errors) == 0, errors


def get_workflow_status(case_id):
    """Get comprehensive workflow status for a case."""
    conn = get_db()
    try:
        case = conn.execute(
            "SELECT * FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()
        if not case:
            return None

        current_stage = case["current_stage"] or "intake"
        allowed_next = VALID_TRANSITIONS.get(current_stage, set())

        # Check which transitions are possible (have required data)
        possible = {}
        for stage in allowed_next:
            is_valid, errors = validate_stage_transition(case_id, current_stage, stage)
            possible[stage] = {"valid": is_valid, "errors": errors}

        # Get lifecycle history
        lifecycle = conn.execute(
            "SELECT * FROM case_lifecycle WHERE case_id = ? ORDER BY entered_at",
            (case_id,)
        ).fetchall()

        # Count linked records
        linked = {
            "intel": conn.execute(
                "SELECT COUNT(*) FROM intel_reports WHERE linked_case_id = ?", (case_id,)
            ).fetchone()[0],
            "operations": conn.execute(
                "SELECT COUNT(*) FROM operations WHERE op_id IN "
                "(SELECT linked_op_id FROM cases WHERE case_id = ? AND linked_op_id IS NOT NULL)",
                (case_id,)
            ).fetchone()[0],
            "arrests": conn.execute(
                "SELECT COUNT(*) FROM arrests WHERE linked_case_id = ?", (case_id,)
            ).fetchone()[0],
            "firearm_seizures": conn.execute(
                "SELECT COUNT(*) FROM firearm_seizures WHERE linked_case_id = ?", (case_id,)
            ).fetchone()[0],
            "narcotics_seizures": conn.execute(
                "SELECT COUNT(*) FROM narcotics_seizures WHERE linked_case_id = ?", (case_id,)
            ).fetchone()[0],
            "exhibits": conn.execute(
                "SELECT COUNT(*) FROM chain_of_custody WHERE linked_case_id = ?", (case_id,)
            ).fetchone()[0],
            "lab_submissions": conn.execute(
                "SELECT COUNT(*) FROM lab_tracking WHERE linked_case_id = ?", (case_id,)
            ).fetchone()[0],
            "statements": conn.execute(
                "SELECT COUNT(*) FROM witness_statements WHERE linked_case_id = ?", (case_id,)
            ).fetchone()[0],
            "dpp_entries": conn.execute(
                "SELECT COUNT(*) FROM dpp_pipeline WHERE linked_case_id = ?", (case_id,)
            ).fetchone()[0],
            "sop_checklists": conn.execute(
                "SELECT COUNT(*) FROM sop_checklists WHERE linked_case_id = ?", (case_id,)
            ).fetchone()[0],
        }

        return {
            "case": case,
            "current_stage": current_stage,
            "possible_transitions": possible,
            "lifecycle": lifecycle,
            "linked_records": linked,
        }
    finally:
        conn.close()


def advance_case_stage(case_id, to_stage, officer_badge, officer_name, notes=None):
    """Advance a case to the next workflow stage.

    Returns (success, message) tuple.
    """
    conn = get_db()
    try:
        case = conn.execute(
            "SELECT * FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()
        if not case:
            return False, "Case not found."

        from_stage = case["current_stage"] or "intake"

        is_valid, errors = validate_stage_transition(case_id, from_stage, to_stage)
        if not is_valid:
            return False, "; ".join(errors)

        from datetime import datetime
        now = datetime.now().isoformat()

        # Close current lifecycle entry
        conn.execute("""
            UPDATE case_lifecycle
            SET exited_at = ?, exited_by = ?, outcome = ?
            WHERE case_id = ? AND exited_at IS NULL
        """, (now, officer_badge, f"Transitioned to {to_stage}", case_id))

        # Create new lifecycle entry
        conn.execute("""
            INSERT INTO case_lifecycle (case_id, stage, entered_at, entered_by, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (case_id, to_stage, now, officer_badge, notes or ""))

        # Update case current stage
        conn.execute("""
            UPDATE cases SET current_stage = ?, updated_at = ? WHERE case_id = ?
        """, (to_stage, now, case_id))

        conn.commit()

        from .models import log_audit
        log_audit("cases", case_id, "STAGE_TRANSITION", officer_badge, officer_name,
                  f"{from_stage} -> {to_stage}")

        return True, f"Case advanced from '{from_stage}' to '{to_stage}'."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()
