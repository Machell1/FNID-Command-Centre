"""
FNID Command Centre v2.0 - Audit Service
WORM (Write Once Read Many) Compliance
SOP Section 4.2, 4.4, 7.4.4
"""
import hashlib
import json
from datetime import datetime, timedelta
from sqlalchemy import text
from .. import db

class AuditService:
    @staticmethod
    def log_action(officer, action, table_name, record_id, old_values=None, new_values=None, change_reason=None):
        """Log action to WORM audit table."""

        # Build audit record
        audit_data = {
            'officer_reg_number': officer.reg_number if officer else None,
            'officer_ip': '127.0.0.1',  # Should be extracted from request
            'officer_device_fingerprint': None,
            'action': action,
            'table_name': table_name,
            'record_id': str(record_id),
            'old_values': json.dumps(old_values) if old_values else None,
            'new_values': json.dumps(new_values) if new_values else None,
            'change_reason': change_reason,
            'action_at': datetime.utcnow().isoformat(),
            'retention_until': (datetime.utcnow() + timedelta(days=365*7)).isoformat()
        }

        # Calculate hash
        hash_input = json.dumps(audit_data, sort_keys=True)
        audit_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        # Get previous hash for chain
        prev_hash = None
        try:
            result = db.session.execute(text(
                "SELECT audit_hash FROM audit_log ORDER BY audit_id DESC LIMIT 1"
            )).fetchone()
            if result:
                prev_hash = result[0]
        except:
            pass

        # Insert via raw SQL to bypass any ORM restrictions
        db.session.execute(text("
            INSERT INTO audit_log (
                officer_reg_number, officer_ip, officer_device_fingerprint,
                action, table_name, record_id, old_values, new_values,
                change_reason, action_at, audit_hash, previous_audit_hash, retention_until
            ) VALUES (
                :officer_reg_number, :officer_ip, :officer_device_fingerprint,
                :action, :table_name, :record_id, :old_values, :new_values,
                :change_reason, :action_at, :audit_hash, :previous_audit_hash, :retention_until
            )
        "), {
            **audit_data,
            'audit_hash': audit_hash,
            'previous_audit_hash': prev_hash
        })

        db.session.commit()
        return audit_hash
