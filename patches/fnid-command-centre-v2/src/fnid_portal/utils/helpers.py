"""
FNID Command Centre v2.0 - Utility Functions
"""
import hashlib
import json
from datetime import datetime

def hash_narrative(narrative: str, officer_reg: str, timestamp: datetime) -> str:
    """Generate SHA-256 hash of investigation narrative for tamper evidence."""
    data = f"{narrative}|{officer_reg}|{timestamp.isoformat()}"
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def format_cr_number_dcr(cons_num: int, date_str: str, station_code: str, diary_type: str, entry_num: int, division_code: str) -> str:
    """Format DCRR CR# per SOP 9.1.13.1."""
    return f"{cons_num}_{date_str}/{station_code}/{diary_type}{entry_num}/{division_code}"

def format_cr_number_station(cons_num: int, entry_num: int, date_str: str, station_code: str) -> str:
    """Format Station Register CR# per SOP 9.1.13.2."""
    return f"{cons_num}_/{entry_num}/{date_str}/{station_code}"

def calculate_review_schedule(crime_category: str, is_homicide: bool = False) -> dict:
    """Calculate review dates per SOP 9.3.3."""
    now = datetime.utcnow()
    if is_homicide:
        return {
            'first_review': now,  # Immediate
            'second_review': now + timedelta(hours=72),
            'follow_up': now + timedelta(days=14),
            'ongoing': now + timedelta(days=28)
        }
    elif crime_category in ['MAJOR', 'FIREARMS', 'NARCOTICS']:
        return {
            'first_review': now + timedelta(days=7),
            'follow_up': now + timedelta(days=14),
            'ongoing': now + timedelta(days=28)
        }
    else:
        return {
            'first_review': now + timedelta(days=7),
            'ongoing': now + timedelta(days=28)
        }

from datetime import timedelta
