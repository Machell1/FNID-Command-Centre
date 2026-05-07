"""
Case Reference (CR) Form Management Routes

Digital handling for JCF Case Reference forms per Case Management Policy
(JCF/FW/PL/C&S/0001/2024 Section 11.0).

NB: All related forms must be referred to as Case Reference Form
(not Crime Reference Form) per policy.

Forms: CR 1 (Investigator's Worksheet), CR 2 (Action Sheet),
CR 3 (Witness Bio-Data), CR 4 (Stolen Property), CR 5 (Exhibit Chain of Custody),
CR 6 (Investigator Index Card), CR 7 (Morning Crime Report),
CR 8 (Q&A Suspect), CR 9 (Q&A Accused), CR 10 (Customer Reference Form),
CR 11 (Confession Statement), CR 12 (Major & Minor Case Report),
CR 13 (Court Case File Checklist), CR 14 (JCF Profile Form),
CR 15 (Application for Remand of Accused or Bail Conditions).

Field layouts are CONFIGURABLE — derived from JCF policy language.
"""

import json
from datetime import datetime

from flask import Blueprint, Response, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required

from ..case_numbers import generate_form_id
from ..models import get_db, log_audit
from ..official_cr_forms import (
    OFFICIAL_CR_FORM_DEFINITIONS,
    OFFICIAL_FORM_DIR,
    collect_form_data,
    get_form_layout,
    is_official_form,
    prefill_form_data,
    printable_field_rows,
    source_filename,
)
from ..pdf_export import pdf_base_css, pdf_header_html, render_pdf
from ..rbac import permission_required

bp = Blueprint("cr_forms", __name__)

# Case Reference (CR) Form definitions — per JCF Case Management Policy
# JCF/FW/PL/C&S/0001/2024 Section 11.0
# NB: Forms are Case Reference Forms (not Crime Reference Forms)
CR_FORM_DEFINITIONS = {
    "CR1": {
        "name": "Investigator's Worksheet",
        "description": "Investigator's Worksheet (Appendix 9) - tracks investigator actions and case progress",
        "sections": [
            {"title": "Report Details", "fields": [
                {"name": "report_date", "label": "Date of Report", "type": "date", "required": True},
                {"name": "report_time", "label": "Time of Report", "type": "time"},
                {"name": "station", "label": "Station", "type": "text", "required": True},
                {"name": "diary_number", "label": "Station Diary Number", "type": "text"},
                {"name": "offence_date", "label": "Date of Offence", "type": "date", "required": True},
                {"name": "offence_time", "label": "Time of Offence", "type": "time"},
                {"name": "offence_location", "label": "Location of Offence", "type": "text", "required": True},
                {"name": "parish", "label": "Parish", "type": "select", "options": "ALL_PARISHES"},
            ]},
            {"title": "Offence Classification", "fields": [
                {"name": "classification", "label": "Classification",
                 "type": "select", "options": "CASE_CLASSIFICATIONS"},
                {"name": "offence", "label": "Offence", "type": "select", "options": "ALL_OFFENCES"},
                {"name": "law_section", "label": "Law & Section", "type": "text"},
                {"name": "crime_type", "label": "Crime Type", "type": "select",
                 "options_list": ["Major", "Minor"]},
            ]},
            {"title": "Complainant/Victim", "fields": [
                {"name": "complainant_name", "label": "Complainant Name", "type": "text"},
                {"name": "complainant_address", "label": "Address", "type": "text"},
                {"name": "complainant_phone", "label": "Telephone", "type": "text"},
                {"name": "complainant_occupation", "label": "Occupation", "type": "text"},
            ]},
            {"title": "Suspect Details", "fields": [
                {"name": "suspect_name", "label": "Suspect Name", "type": "text"},
                {"name": "suspect_alias", "label": "Alias", "type": "text"},
                {"name": "suspect_dob", "label": "Date of Birth", "type": "date"},
                {"name": "suspect_address", "label": "Address", "type": "text"},
                {"name": "suspect_description", "label": "Description", "type": "textarea"},
            ]},
            {"title": "Particulars of Offence", "fields": [
                {"name": "particulars", "label": "Particulars of Offence", "type": "textarea", "required": True},
                {"name": "stolen_property", "label": "Stolen Property Description", "type": "textarea"},
                {"name": "property_value", "label": "Estimated Value (JMD)", "type": "number"},
                {"name": "weapons_used", "label": "Weapons Used", "type": "text"},
                {"name": "modus_operandi", "label": "Modus Operandi", "type": "textarea"},
            ]},
            {"title": "Investigating Officer", "fields": [
                {"name": "oic_name", "label": "OIC Name", "type": "text"},
                {"name": "oic_rank", "label": "OIC Rank", "type": "select", "options": "JCF_RANKS"},
                {"name": "oic_badge", "label": "OIC Badge No.", "type": "text"},
            ]},
        ],
    },
    "CR2": {
        "name": "Action Sheet",
        "description": "Action Sheet (Appendix 10) - tasks generated during vetting, reviews and conferences",
        "sections": [
            {"title": "Supplementary Details", "fields": [
                {"name": "supplement_date", "label": "Date", "type": "date", "required": True},
                {"name": "supplement_number", "label": "Supplement Number", "type": "number"},
                {"name": "additional_info", "label": "Additional Information", "type": "textarea", "required": True},
                {"name": "new_evidence", "label": "New Evidence Discovered", "type": "textarea"},
                {"name": "new_witnesses", "label": "New Witnesses Identified", "type": "textarea"},
                {"name": "suspect_update", "label": "Suspect Update", "type": "textarea"},
                {"name": "prepared_by", "label": "Prepared By", "type": "text"},
            ]},
        ],
    },
    "CR3": {
        "name": "Witness Bio-Data Form",
        "description": (
            "Witness Bio-Data Form (Appendix 8) - completed for all"
            " major crimes and attached to front of statement"
        ),
        "sections": [
            {"title": "Statement Details", "fields": [
                {"name": "statement_date", "label": "Date", "type": "date", "required": True},
                {"name": "statement_time", "label": "Time", "type": "time"},
                {"name": "deponent_name", "label": "Name of Deponent", "type": "text", "required": True},
                {"name": "deponent_address", "label": "Address", "type": "text"},
                {"name": "deponent_occupation", "label": "Occupation", "type": "text"},
                {"name": "deponent_age", "label": "Age", "type": "number"},
                {"name": "statement_type", "label": "Type", "type": "select",
                 "options_list": ["Witness", "Complainant", "Suspect (under caution)", "Expert"]},
                {"name": "cautioned", "label": "Cautioned (if suspect)", "type": "select",
                 "options_list": ["N/A", "Yes", "No"]},
                {"name": "statement_body", "label": "Statement", "type": "textarea", "required": True},
                {"name": "taken_by", "label": "Statement Taken By", "type": "text"},
                {"name": "signed", "label": "Signed by Deponent", "type": "select",
                 "options_list": ["Yes", "No"]},
            ]},
        ],
    },
    "CR4": {
        "name": "Stolen Property Form",
        "description": "Stolen Property Form (Appendix 7) - completed in triplicate for all stolen/recovered property",
        "sections": [
            {"title": "Exhibit Details", "fields": [
                {"name": "exhibit_number", "label": "Exhibit Number", "type": "text", "required": True},
                {"name": "exhibit_description", "label": "Description", "type": "textarea", "required": True},
                {"name": "exhibit_type", "label": "Type", "type": "select", "options": "EXHIBIT_TYPES"},
                {"name": "quantity", "label": "Quantity", "type": "number"},
                {"name": "seized_from", "label": "Seized From (person/location)", "type": "text"},
                {"name": "seizure_date", "label": "Date of Seizure", "type": "date"},
                {"name": "seized_by", "label": "Seized By", "type": "text"},
                {"name": "witness_officer", "label": "Witness Officer", "type": "text"},
                {"name": "seal_number", "label": "Seal Number", "type": "text"},
                {"name": "storage_location", "label": "Storage Location", "type": "text"},
                {"name": "condition", "label": "Condition", "type": "text"},
                {"name": "photos_taken", "label": "Photographs Taken", "type": "select",
                 "options_list": ["Yes", "No"]},
            ]},
        ],
    },
    "CR5": {
        "name": "Exhibit Chain of Custody Schedule",
        "description": "Exhibit Chain of Custody Schedule (Appendix 16) - documents exhibit handling and transfers",
        "sections": [
            {"title": "Diary Entry", "fields": [
                {"name": "entry_date", "label": "Date", "type": "date", "required": True},
                {"name": "entry_time", "label": "Time", "type": "time"},
                {"name": "activity", "label": "Activity/Action Taken", "type": "textarea", "required": True},
                {"name": "persons_contacted", "label": "Persons Contacted", "type": "textarea"},
                {"name": "locations_visited", "label": "Locations Visited", "type": "text"},
                {"name": "evidence_obtained", "label": "Evidence Obtained", "type": "textarea"},
                {"name": "next_steps", "label": "Next Steps Planned", "type": "textarea"},
                {"name": "hours_spent", "label": "Hours Spent", "type": "number"},
            ]},
        ],
    },
    "CR6": {
        "name": "Investigator Index Card",
        "description": "Investigator Index Card (Appendix 17) - records IO information and assigned cases",
        "sections": [
            {"title": "Investigator Information", "fields": [
                {"name": "officer_name", "label": "Name of Investigator", "type": "text", "required": True},
                {"name": "officer_rank", "label": "Rank", "type": "select", "options": "JCF_RANKS"},
                {"name": "officer_reg", "label": "Reg. No.", "type": "text", "required": True},
                {"name": "station", "label": "Station", "type": "text", "required": True},
            ]},
            {"title": "Assigned Cases", "fields": [
                {"name": "case_ref_no", "label": "Case Ref. No.", "type": "text"},
                {"name": "offence_and_date", "label": "Offence(s) & Date Committed", "type": "textarea"},
                {"name": "complainant_name", "label": "Complainant's Name", "type": "text"},
                {"name": "accused_name", "label": "Name of Accused", "type": "text"},
                {"name": "status_of_case", "label": "Status of Case", "type": "select",
                 "options_list": ["C - Closed", "O - Open", "S - Suspended", "CC - Cold Case"]},
            ]},
        ],
    },
    "CR7": {
        "name": "Morning Crime Report",
        "description": "Daily crime summary (typically auto-generated by MCR engine)",
        "sections": [
            {"title": "MCR Summary", "fields": [
                {"name": "mcr_date", "label": "Report Date", "type": "date", "required": True},
                {"name": "window_start", "label": "Period From", "type": "text"},
                {"name": "window_end", "label": "Period To", "type": "text"},
                {"name": "total_matters", "label": "Total Matters", "type": "number"},
                {"name": "fnid_matters", "label": "FNID-Relevant Matters", "type": "number"},
                {"name": "firearms_seized", "label": "Firearms Seized", "type": "number"},
                {"name": "narcotics_seized", "label": "Narcotics Seized", "type": "text"},
                {"name": "arrests_made", "label": "Arrests Made", "type": "number"},
                {"name": "summary_narrative", "label": "Summary Narrative", "type": "textarea", "required": True},
                {"name": "lead_items", "label": "Lead Items for Follow-Up", "type": "textarea"},
                {"name": "compiled_by", "label": "Compiled By", "type": "text"},
            ]},
        ],
    },
    "CR8": {
        "name": "Question & Answer (Suspect/Witness Interview) Form",
        "description": "Question & Answer (Suspect/Witness Interview) Form (Appendix 18) - CR 8",
        "sections": [
            {"title": "Question & Answer of Suspect", "fields": [
                {"name": "suspect_name", "label": "Name of Suspect", "type": "text", "required": True},
                {"name": "suspect_age", "label": "Age", "type": "number"},
                {"name": "suspect_occupation", "label": "Occupation", "type": "text"},
                {"name": "interviewer_name", "label": "Name of Interviewer", "type": "text", "required": True},
                {"name": "place_of_interview", "label": "Place of Interview", "type": "text", "required": True},
                {"name": "date_of_interview", "label": "Date of Interview", "type": "date", "required": True},
                {"name": "start_time", "label": "Start Time", "type": "time", "required": True},
                {"name": "end_time", "label": "End Time", "type": "time"},
                {"name": "person_arrested", "label": "Person Arrested", "type": "select",
                 "options_list": ["Yes", "No"]},
            ]},
            {"title": "Caution (Judges Rule 3a)", "fields": [
                {"name": "caution_administered", "label": "Caution Administered", "type": "select",
                 "options_list": ["Yes", "No"], "required": True},
                {"name": "caution_signature", "label": "Signature or Mark of Suspect", "type": "text"},
                {"name": "caution_date", "label": "Date", "type": "date"},
                {"name": "caution_witnessed_by", "label": "Witnessed By", "type": "text"},
                {"name": "status", "label": "Status", "type": "text"},
            ]},
            {"title": "Questions and Answers", "fields": [
                {"name": "questions_answers", "label": "Questions and Answers", "type": "textarea", "required": True},
                {"name": "interviewee_signature", "label": "Signature of Interviewee", "type": "text"},
                {"name": "interviewee_sign_date", "label": "Date", "type": "date"},
                {"name": "interview_witnessed_by", "label": "Witnessed By", "type": "text"},
            ]},
            {"title": "Maker's Certificate", "fields": [
                {"name": "maker_cert_questions_asked",
                 "label": "Questions were asked of me and I answered",
                 "type": "select", "options_list": ["Yes", "No"]},
                {"name": "maker_cert_right_informed",
                 "label": "Informed of right to make additions/alterations/corrections",
                 "type": "select", "options_list": ["Yes", "No"]},
                {"name": "maker_cert_answers_free_will",
                 "label": "Answers given of own free will",
                 "type": "select", "options_list": ["Yes", "No"]},
                {"name": "maker_cert_read_over",
                 "label": "Questions and answers read over/invited to read",
                 "type": "select", "options_list": ["Yes", "No"]},
                {"name": "maker_signature", "label": "Maker Signature", "type": "text"},
                {"name": "maker_date", "label": "Date", "type": "date"},
            ]},
            {"title": "Recorder's Certificate", "fields": [
                {"name": "recorder_cert_questions_asked_by",
                 "label": "All questions asked by", "type": "text"},
                {"name": "recorder_cert_suspect_informed",
                 "label": "Suspect informed of right to make additions/alterations",
                 "type": "select", "options_list": ["Yes", "No"]},
                {"name": "recorder_cert_read_by_letter",
                 "label": ("Statement read by him/her/read over to him/her"
                           " and he/she was invited to make corrections"),
                 "type": "select", "options_list": ["Yes", "No"]},
                {"name": "recorder_signature", "label": "Recorder Signature", "type": "text"},
                {"name": "recorder_date", "label": "Date", "type": "date"},
                {"name": "number_of_pages", "label": "Number of Pages", "type": "number"},
            ]},
        ],
    },
    "CR9": {
        "name": "Question & Answer (Accused Written Interview) Form",
        "description": "Question & Answer (Accused Written Interview) Form (Appendix 19) - CR 9",
        "sections": [
            {"title": "Question & Answer of Accused", "fields": [
                {"name": "accused_name", "label": "Name of Accused", "type": "text", "required": True},
                {"name": "accused_age_dob", "label": "Age/DOB", "type": "text"},
                {"name": "station", "label": "Station", "type": "text"},
                {"name": "interviewer_name", "label": "Name of Interviewer", "type": "text", "required": True},
                {"name": "interviewer_rank", "label": "Rank", "type": "select", "options": "JCF_RANKS"},
                {"name": "place_of_interview", "label": "Place of Interview", "type": "text", "required": True},
                {"name": "date_of_interview", "label": "Date of Interview", "type": "date", "required": True},
                {"name": "start_time", "label": "Start Time", "type": "time", "required": True},
                {"name": "end_time", "label": "End Time", "type": "time"},
                {"name": "charge", "label": "Charge(s)", "type": "textarea", "required": True},
            ]},
            {"title": "Caution (Judges Rule 3a)", "fields": [
                {"name": "caution_administered", "label": "Caution Administered", "type": "select",
                 "options_list": ["Yes", "No"], "required": True},
                {"name": "caution_signature", "label": "Signature or Mark of Accused", "type": "text"},
                {"name": "caution_date", "label": "Date", "type": "date"},
                {"name": "caution_witnessed_by", "label": "Witnessed By", "type": "text"},
                {"name": "status", "label": "Status", "type": "text"},
            ]},
            {"title": "Questions and Answers", "fields": [
                {"name": "questions_answers", "label": "Questions and Answers", "type": "textarea", "required": True},
                {"name": "interviewee_signature", "label": "Signature of Interviewee", "type": "text"},
                {"name": "interviewee_sign_date", "label": "Date", "type": "date"},
                {"name": "interview_witnessed_by", "label": "Witnessed By", "type": "text"},
            ]},
            {"title": "Maker's Certificate", "fields": [
                {"name": "maker_cert_questions_asked",
                 "label": "Questions were asked of me and I answered",
                 "type": "select", "options_list": ["Yes", "No"]},
                {"name": "maker_cert_right_informed",
                 "label": "Informed of right to make additions/alterations/corrections",
                 "type": "select", "options_list": ["Yes", "No"]},
                {"name": "maker_cert_answers_free_will",
                 "label": "Answers given of own free will",
                 "type": "select", "options_list": ["Yes", "No"]},
                {"name": "maker_cert_read_over",
                 "label": "Questions and answers read over/invited to read",
                 "type": "select", "options_list": ["Yes", "No"]},
                {"name": "maker_signature", "label": "Maker Signature", "type": "text"},
                {"name": "maker_date", "label": "Date", "type": "date"},
            ]},
            {"title": "Recorder's Certificate", "fields": [
                {"name": "recorder_cert_questions_asked_by",
                 "label": "All questions asked by", "type": "text"},
                {"name": "recorder_cert_accused_informed",
                 "label": "Accused informed of right to make additions/alterations",
                 "type": "select", "options_list": ["Yes", "No"]},
                {"name": "recorder_cert_read_by_letter",
                 "label": ("Statement read by him/her/read over"
                           " and invited to make corrections"),
                 "type": "select", "options_list": ["Yes", "No"]},
                {"name": "recorder_signature", "label": "Recorder Signature", "type": "text"},
                {"name": "recorder_date", "label": "Date", "type": "date"},
                {"name": "number_of_pages", "label": "Number of Pages", "type": "number"},
            ]},
        ],
    },
    "CR10": {
        "name": "Customer Reference Form",
        "description": "Customer Reference Form (Appendix 6) - issued to complainant upon making a report",
        "sections": [
            {"title": "Customer Reference Details", "fields": [
                {"name": "customer_name", "label": "Name", "type": "text", "required": True},
                {"name": "customer_address", "label": "Address", "type": "text"},
                {"name": "customer_tel", "label": "Tel.", "type": "text"},
                {"name": "customer_email", "label": "Email", "type": "text"},
                {"name": "police_station", "label": "Police Station", "type": "text", "required": True},
                {"name": "station_tel", "label": "Station's Tel. # (876)", "type": "text"},
                {"name": "station_email", "label": "Station's Email", "type": "text"},
                {"name": "date_of_report", "label": "Date of Report", "type": "date", "required": True},
                {"name": "time_of_report", "label": "Time of Report", "type": "time"},
                {"name": "nature_of_report", "label": "Nature of Report", "type": "textarea", "required": True},
                {"name": "diary_entry", "label": "D/E #", "type": "text"},
                {"name": "crime_ref", "label": "Crime Ref.#", "type": "text"},
                {"name": "recording_officer", "label": "Name of Recording Officer", "type": "text"},
                {"name": "officer_rank", "label": "Rank", "type": "select", "options": "JCF_RANKS"},
                {"name": "officer_reg", "label": "Reg.#", "type": "text"},
                {"name": "recording_officer_signature", "label": "Signature of Recording Officer", "type": "text"},
            ]},
        ],
    },
    "CR11": {
        "name": "Confession Statement of Suspect/Accused",
        "description": "Confession Statement Form (Appendix 20) - CR 11, per Section 9.3.4",
        "sections": [
            {"title": "Confession Statement of Suspect/Accused", "fields": [
                {"name": "suspect_name", "label": "Name of Suspect/Accused", "type": "text", "required": True},
                {"name": "suspect_occupation", "label": "Occupation", "type": "text"},
                {"name": "place_arrested", "label": "Place Arrested", "type": "text"},
            ]},
            {"title": "Caution", "fields": [
                {"name": "caution_administered", "label": "Caution Administered", "type": "select",
                 "options_list": ["Yes", "No"], "required": True},
                {"name": "caution_signature", "label": "Signature or Mark", "type": "text"},
                {"name": "caution_date", "label": "Date", "type": "date"},
                {"name": "caution_witnessed_by", "label": "Witnessed By", "type": "text"},
            ]},
            {"title": "Certification of Statement", "fields": [
                {"name": "cert_wish_to_make_statement",
                 "label": "I wish to make a statement (confirmed)",
                 "type": "select",
                 "options_list": ["Yes", "No"], "required": True},
                {"name": "cert_told_not_obliged",
                 "label": "Told that need not say anything unless wishes to do so",
                 "type": "select", "options_list": ["Yes", "No"]},
                {"name": "cert_whatever_given_evidence",
                 "label": "Whatever I say may be given in evidence",
                 "type": "select", "options_list": ["Yes", "No"]},
            ]},
            {"title": "Confession Statement", "fields": [
                {"name": "confession_body", "label": "Statement Body", "type": "textarea", "required": True},
                {"name": "statement_status", "label": "Status", "type": "text"},
                {"name": "interviewee_signature", "label": "Signature of Interviewee", "type": "text"},
                {"name": "interviewee_sign_date", "label": "Date", "type": "date"},
                {"name": "interview_witnessed_by", "label": "Witnessed By", "type": "text"},
            ]},
            {"title": "Certificate of the Recorder (where applicable)", "fields": [
                {"name": "recorder_cert_statement_read",
                 "label": "Above statement was read over to/by the accused",
                 "type": "select", "options_list": ["Yes", "No"]},
                {"name": "recorder_cert_no_additions",
                 "label": "No additions/alterations/corrections (or noted)",
                 "type": "select",
                 "options_list": ["Yes - no changes", "Changes noted"]},
                {"name": "recorder_cert_read_by_letter",
                 "label": ("Statement read by him/her/read over to"
                           " him/her and invited to make corrections"),
                 "type": "select", "options_list": ["Yes", "No"]},
                {"name": "recorder_signature", "label": "Recorder Signature", "type": "text"},
                {"name": "recorder_date", "label": "Date", "type": "date"},
                {"name": "number_of_pages", "label": "Number of Pages", "type": "number"},
            ]},
        ],
    },
    "CR12": {
        "name": "Major and Minor Case Report Form",
        "description": "Major and Minor Case Report Form (Appendix 21) - CR 12",
        "sections": [
            {"title": "Accused / Case Information", "fields": [
                {"name": "accused_name", "label": "Name of Accused", "type": "text", "required": True},
                {"name": "accused_dob", "label": "Date of Birth", "type": "date"},
                {"name": "division_region", "label": "Division or Region", "type": "text"},
                {"name": "case_ref_id", "label": "Case Ref ID", "type": "text", "required": True},
                {"name": "complainant_victim", "label": "Complainant/Victim", "type": "text"},
                {"name": "date_of_offence", "label": "Date of Offence", "type": "date"},
            ]},
            {"title": "Summary of Evidence in Brief", "fields": [
                {"name": "summary_of_evidence",
                 "label": "Summary of Evidence in Brief",
                 "type": "textarea", "required": True},
                {"name": "number_of_witnesses", "label": "Number of Witnesses", "type": "number"},
                {"name": "number_of_exhibits", "label": "Number of Exhibits", "type": "number"},
                {"name": "exhibit_1", "label": "Exhibit 1 (listing)", "type": "text"},
                {"name": "exhibit_2", "label": "Exhibit 2 (listing)", "type": "text"},
                {"name": "exhibit_3", "label": "Exhibit 3 (listing)", "type": "text"},
                {"name": "exhibit_4", "label": "Exhibit 4 (listing)", "type": "text"},
            ]},
            {"title": "Aggravating Factors", "fields": [
                {"name": "aggravating_factors", "label": "Aggravating Factors", "type": "textarea"},
            ]},
            {"title": "Details of Evidence: Witness(es) or Defendant - Not Including in Witness Data", "fields": [
                {"name": "evidence_details", "label": "Details of Evidence", "type": "textarea"},
            ]},
            {"title": "Outstanding Work", "fields": [
                {"name": "outstanding_task_1", "label": "Task 1", "type": "text"},
                {"name": "outstanding_est_date_1", "label": "Estimated Date for Completion 1", "type": "date"},
                {"name": "outstanding_task_2", "label": "Task 2", "type": "text"},
                {"name": "outstanding_est_date_2", "label": "Estimated Date for Completion 2", "type": "date"},
                {"name": "outstanding_task_3", "label": "Task 3", "type": "text"},
                {"name": "outstanding_est_date_3", "label": "Estimated Date for Completion 3", "type": "date"},
            ]},
            {"title": "Post-Charge Tests & Obligations", "fields": [
                {"name": "forensic_certificate", "label": "Forensic Certificate", "type": "select",
                 "options_list": ["Yes", "No", "N/A"]},
                {"name": "forensic_cert_1st_party",
                 "label": "Forensic Cert - 1st Party (Scenes and Exhibits/Toxicology)",
                 "type": "text"},
                {"name": "forensic_cert_overdue_reason", "label": "Overdue Reason", "type": "text"},
                {"name": "forensic_cert_est_due_date", "label": "Est. Due Date", "type": "date"},
                {"name": "ballistic_certificate", "label": "Ballistic Certificate", "type": "select",
                 "options_list": ["Yes", "No", "N/A"]},
                {"name": "ballistic_cert_1st_party",
                 "label": "Ballistic Cert - Forensic Science and Ballistic Section",
                 "type": "text"},
                {"name": "post_mortem_report", "label": "Post Mortem Report", "type": "select",
                 "options_list": ["Yes", "No", "N/A"]},
                {"name": "post_mortem_1st_party", "label": "Post Mortem - Legal Medicine (contract)", "type": "text"},
                {"name": "medical_report", "label": "Medical Report", "type": "select",
                 "options_list": ["Yes", "No", "N/A"]},
                {"name": "medical_certificate", "label": "Medical Certificate", "type": "select",
                 "options_list": ["Yes", "No", "N/A"]},
                {"name": "medical_institution_officer",
                 "label": "Statement (Medical Institution/Medical Officer)",
                 "type": "text"},
                {"name": "documents_pub",
                 "label": "Documents (e.g. NIC/ID, PIN, TRN, Driver's Licence etc.)",
                 "type": "text"},
                {"name": "claim_of_records", "label": "Claim of Records (if Transported/Deceased)", "type": "text"},
                {"name": "claim_records_party", "label": "Claim Records - Criminal Records Office", "type": "text"},
            ]},
            {"title": "Biographical Information", "fields": [
                {"name": "bio_info",
                 "label": ("Biographical Information (This section should only"
                           " be used if all the persons indicated have been charged)"),
                 "type": "textarea"},
            ]},
            {"title": "Investigator's Summary", "fields": [
                {"name": "inv_bio_rank_name_station",
                 "label": "Rank, Name and Station of Investigator",
                 "type": "text"},
                {"name": "inv_statement_deposed",
                 "label": "Investigator's Statement (Statement Deposed)",
                 "type": "textarea"},
                {"name": "inv_statement_date", "label": "Date", "type": "date"},
                {"name": "mode_of_apprehension",
                 "label": "Mode and Conclusion of Apprehension (e.g. bail/remand/PDR)",
                 "type": "textarea"},
                {"name": "apprehension_date", "label": "Date", "type": "date"},
                {"name": "apprehension_reference", "label": "Reference", "type": "text"},
            ]},
        ],
    },
    "CR13": {
        "name": "Court Case File Checklist",
        "description": (
            "Court Case File Checklist (Appendix 22) - CR 13,"
            " ensures all documents accompany case file to court"
        ),
        "sections": [
            {"title": "Case Information", "fields": [
                {"name": "case_ref", "label": "Case Ref.", "type": "text", "required": True},
            ]},
            {"title": "1. Report", "fields": [
                {"name": "complaint", "label": "Complaint", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "complaint_date_completed", "label": "Complaint - Date Completed", "type": "date"},
                {"name": "complaint_date_submitted", "label": "Complaint - Date Submitted", "type": "date"},
                {"name": "summary_of_charge", "label": "Summary of Charge", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "fingerprint_cards", "label": "Fingerprint Cards", "type": "select",
                 "options_list": ["AMT", "N/A"]},
            ]},
            {"title": "2. Crime Scene", "fields": [
                {"name": "crime_scene_csi", "label": "Crime Scene (CSI)", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "crime_scene_sketch", "label": "Crime Scene Sketch/Drawing", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "crime_scene_record", "label": "Crime Scene Record", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "witness_corroboration_tag",
                 "label": "Witness Corroboration & Tag No./Ticket",
                 "type": "select",
                 "options_list": ["AMT", "N/A"]},
            ]},
            {"title": "3. Investigation", "fields": [
                {"name": "control_log", "label": "Control Log", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "investigators_diary", "label": "Investigator's Diary", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "evidence_receipt_bail", "label": "Evidence Receipt (Bail copy)", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "notice_of_risk", "label": "Notice of Risk", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "risk_assessment", "label": "Risk Assessment Suitability", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "diary", "label": "Diary", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "general_procedure", "label": "General Procedure", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "inv_officer_statement", "label": "Investigation Officer Statement", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "medical_evidence", "label": "Medical Evidence", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "police_expert_csi", "label": "Police Expert Form CSI", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "finger_report_copy", "label": "Finger Report Copy", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "post_mortem", "label": "Post Mortem", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "statement_identifying_body",
                 "label": "Statement of person identifying the body (in case of death)",
                 "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "antecedent_report", "label": "Antecedent Report", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "worksheet_ri", "label": "Worksheet (R.I.)", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "warning_list", "label": "Warning List", "type": "select",
                 "options_list": ["AMT", "N/A"]},
            ]},
            {"title": "4. Arrest/Charge", "fields": [
                {"name": "arresting_officer", "label": "Arresting/Apprehending Officer", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "details", "label": "Details", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "bail_forms", "label": "Bail Forms", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "accused_statement", "label": "Accused's Statement", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "further_statement_inv", "label": "Further Statement of Investigators", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "statement_victim_witness", "label": "Statement of (Victim/Witness)", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "mobile_data_extraction", "label": "Mobile Data Extraction", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "warrant", "label": "Warrant", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "identification_notes", "label": "Identification Notes", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "sif_statements", "label": "(S.I.F) Statement(s)", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "qa_all_standard", "label": "Q & A (All Standard)", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "first_information_report", "label": "First Information Report", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "caution_statement", "label": "Caution Statement", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "supplementary", "label": "Supplementary", "type": "select",
                 "options_list": ["AMT", "N/A"]},
            ]},
            {"title": "5. VII - Complainant", "fields": [
                {"name": "complainant_docs", "label": "Complainant Documents", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "complainant_date_completed", "label": "Date Completed", "type": "date"},
                {"name": "complainant_date_submitted", "label": "Date Submitted", "type": "date"},
            ]},
            {"title": "6. VIII - Warrant", "fields": [
                {"name": "warrant_docs", "label": "Warrant Documents", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "warrant_date_completed", "label": "Date Completed", "type": "date"},
                {"name": "warrant_date_submitted", "label": "Date Submitted", "type": "date"},
            ]},
            {"title": "7. IX - Exhibits", "fields": [
                {"name": "exhibits_docs", "label": "Exhibits Documentation", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "exhibits_date_completed", "label": "Date Completed", "type": "date"},
                {"name": "exhibits_date_submitted", "label": "Date Submitted", "type": "date"},
            ]},
            {"title": "8. X - Miscellaneous", "fields": [
                {"name": "informants_info", "label": "Informants Information", "type": "select",
                 "options_list": ["AMT", "N/A"]},
                {"name": "notes_paper_clippings", "label": "Notes/Paper Clippings", "type": "select",
                 "options_list": ["AMT", "N/A"]},
            ]},
            {"title": "Other Witness Statements", "fields": [
                {"name": "other_witness_no", "label": "No.", "type": "number"},
                {"name": "other_witness_name", "label": "Name of Witness(es)", "type": "textarea"},
                {"name": "other_witness_date_completed", "label": "Date Completed", "type": "date"},
                {"name": "other_witness_date_submitted", "label": "Date Submitted", "type": "date"},
                {"name": "other_witness_remarks", "label": "Remarks", "type": "textarea"},
            ]},
        ],
    },
    "CR14": {
        "name": "JCF Profile Form",
        "description": "JCF Profile Form (Appendix 24) - CR 14, completed by arresting/investigating officer",
        "sections": [
            {"title": "Status & Case Information", "fields": [
                {"name": "status_wanted", "label": "Wanted", "type": "checkbox"},
                {"name": "status_suspect", "label": "Suspect", "type": "checkbox"},
                {"name": "status_person_charged", "label": "Person Charged", "type": "checkbox"},
                {"name": "status_convicted", "label": "Convicted", "type": "checkbox"},
                {"name": "offence_crime", "label": "Offence/Crime", "type": "text", "required": True},
                {"name": "date", "label": "Date", "type": "date"},
                {"name": "diary_number", "label": "Diary Number", "type": "text"},
                {"name": "investigating_officer", "label": "Investigating Officer", "type": "text"},
                {"name": "referred_to", "label": "Referred to...", "type": "text"},
                {"name": "referred_date", "label": "Date", "type": "date"},
            ]},
            {"title": "Circumstances of Persons Committed", "fields": [
                {"name": "circumstances",
                 "label": ("Circumstances of Persons Committed"
                           " (give date & full details of the arrest/conviction)"),
                 "type": "textarea"},
            ]},
            {"title": "Personal Information", "fields": [
                {"name": "surname", "label": "Surname", "type": "text", "required": True},
                {"name": "first_names", "label": "First Name(s)", "type": "text", "required": True},
                {"name": "contact_name", "label": "Contact Name", "type": "text"},
                {"name": "alias", "label": "Alias", "type": "text"},
                {"name": "middle_name", "label": "Middle Name", "type": "text"},
                {"name": "contact_number", "label": "Contact Number", "type": "text"},
                {"name": "occupation", "label": "Occupation", "type": "text"},
                {"name": "permanent_address", "label": "Permanent Address", "type": "text"},
                {"name": "workplace", "label": "Workplace(s)", "type": "text"},
                {"name": "email", "label": "E-mail", "type": "text"},
                {"name": "gender", "label": "Gender", "type": "select",
                 "options_list": ["M", "F"]},
                {"name": "nationality", "label": "Nationality", "type": "text"},
                {"name": "resident_status", "label": "Resident Status", "type": "select",
                 "options_list": ["Tourist", "Resident", "Foreign National/Birth parent"]},
                {"name": "foreign_student", "label": "Foreign Student", "type": "select",
                 "options_list": ["Yes", "No"]},
                {"name": "repeat_offender", "label": "Repeat Offender", "type": "select",
                 "options_list": ["Yes", "No"]},
                {"name": "repeat_offender_count", "label": "Repeat Offender Count (0-10)", "type": "number"},
                {"name": "repeat_offender_age", "label": "Age", "type": "number"},
                {"name": "deportee", "label": "Deportee", "type": "select",
                 "options_list": ["Yes", "No"]},
                {"name": "deportee_details", "label": "If 'yes', date/country deported from and date", "type": "text"},
                {"name": "dob", "label": "Date of Birth", "type": "date"},
            ]},
            {"title": "Family Information", "fields": [
                {"name": "mother_name_surname", "label": "Mother's Name/Surname", "type": "text"},
                {"name": "mother_first_name", "label": "Mother's First Name(s)", "type": "text"},
                {"name": "mother_tel", "label": "Mother Tel#", "type": "text"},
                {"name": "mother_mobile", "label": "Mother Mobile", "type": "text"},
                {"name": "mother_place_of_birth", "label": "Mother Place of Birth", "type": "text"},
                {"name": "father_name_surname", "label": "Father's Name/Surname", "type": "text"},
                {"name": "father_first_name", "label": "Father's First Name(s)", "type": "text"},
                {"name": "father_tel", "label": "Father Probably/Tel", "type": "text"},
                {"name": "father_mobile", "label": "Father Mobile", "type": "text"},
                {"name": "father_place_of_birth", "label": "Father Place of Birth", "type": "text"},
            ]},
            {"title": "Description of Person", "fields": [
                {"name": "height", "label": "Height", "type": "text"},
                {"name": "build", "label": "Build", "type": "select",
                 "options_list": ["Solid", "Slight", "Medium", "Other"]},
                {"name": "complexion", "label": "Complexion", "type": "select",
                 "options_list": ["Dark", "Light", "Medium", "Other"]},
                {"name": "hair_length", "label": "Hair", "type": "select",
                 "options_list": ["Short", "Long", "Bald", "Medium", "Other"]},
                {"name": "hair_colour", "label": "Hair Colour", "type": "select",
                 "options_list": ["Black", "Brown", "Green", "Other"]},
                {"name": "eye_colour", "label": "Eye Colour", "type": "select",
                 "options_list": ["Black", "Brown", "Hazel", "Chinned", "Crooked", "Buckled"]},
                {"name": "teeth", "label": "Teeth", "type": "text"},
                {"name": "beards", "label": "Beards", "type": "select",
                 "options_list": ["Yes", "No"]},
                {"name": "marks_dist", "label": "Marks, dist. marks", "type": "text"},
                {"name": "vision", "label": "Vision", "type": "select",
                 "options_list": ["High Pitched", "Low", "Other Impediment"]},
                {"name": "scars", "label": "Scars", "type": "text"},
                {"name": "face", "label": "Face", "type": "select",
                 "options_list": ["Oval", "Other"]},
                {"name": "tattoos", "label": "Tattoos (location and description)", "type": "textarea"},
                {"name": "hair_style", "label": "Hair Style", "type": "select",
                 "options_list": ["Straight", "Scruffy", "Eyes"]},
                {"name": "face_shape", "label": "Face Shape", "type": "select",
                 "options_list": ["Oval", "Triangular", "Roundly", "Square", "Other"]},
                {"name": "face_colour_condition",
                 "label": "Face Colour/Condition (e.g. freckled, lined, pimply, etc.)",
                 "type": "text"},
                {"name": "group_ethnicity", "label": "Group/Ethnicity", "type": "select",
                 "options_list": ["Oriental", "Other"]},
                {"name": "beard_style", "label": "Beard Style", "type": "select",
                 "options_list": ["Blend (shaved & bald)", "Short (clipped & shaped)", "Long (shaped and sculpted)"]},
                {"name": "face_length", "label": "Face Length", "type": "text"},
            ]},
            {"title": "Weapons", "fields": [
                {"name": "weapon_1_description", "label": "Weapon 1 Description", "type": "text"},
                {"name": "weapon_1_type", "label": "Weapon 1 Type", "type": "text"},
                {"name": "weapon_2_description", "label": "Weapon 2 Description", "type": "text"},
                {"name": "weapon_2_type", "label": "Weapon 2 Type", "type": "text"},
                {"name": "weapon_3_description", "label": "Weapon 3 Description", "type": "text"},
                {"name": "weapon_3_type", "label": "Weapon 3 Type", "type": "text"},
            ]},
            {"title": "Equipment", "fields": [
                {"name": "equip_1_description", "label": "Equipment 1 Description", "type": "text"},
                {"name": "equip_1_type", "label": "Equipment 1 Type", "type": "text"},
                {"name": "equip_2_description", "label": "Equipment 2 Description", "type": "text"},
                {"name": "equip_2_type", "label": "Equipment 2 Type", "type": "text"},
            ]},
            {"title": "Vehicles", "fields": [
                {"name": "vehicle_colour", "label": "Colour", "type": "text"},
                {"name": "vehicle_make", "label": "Make", "type": "text"},
                {"name": "vehicle_licence_plate", "label": "Licence Plate", "type": "text"},
                {"name": "vehicle_body_type", "label": "Body Type", "type": "text"},
                {"name": "vehicle_model", "label": "Model", "type": "text"},
                {"name": "vehicle_engine_no", "label": "Engine No.", "type": "text"},
                {"name": "vehicle_chassis_no", "label": "Chassis No.", "type": "text"},
                {"name": "vehicle_year", "label": "Year", "type": "text"},
                {"name": "vehicle_condition", "label": "Condition", "type": "text"},
            ]},
            {"title": "Address", "fields": [
                {"name": "address_line_1", "label": "Address Line 1", "type": "text"},
                {"name": "address_line_2", "label": "Address Line 2", "type": "text"},
                {"name": "address_parish", "label": "Parish", "type": "select", "options": "ALL_PARISHES"},
                {"name": "address_residence", "label": "Residence", "type": "select",
                 "options_list": ["Rented", "Family/Relatives", "Squatter", "Other"]},
                {"name": "address_phone", "label": "Phone", "type": "text"},
                {"name": "address_nearby_landmark", "label": "Nearby Landmark", "type": "text"},
                {"name": "address_how_to_confirm", "label": "How to Confirm", "type": "text"},
            ]},
            {"title": "Surgical Implants", "fields": [
                {"name": "surgical_hip", "label": "Hip Tool", "type": "checkbox"},
                {"name": "surgical_body_scan", "label": "Body Scan", "type": "checkbox"},
                {"name": "surgical_foreign_implant", "label": "Foreign Implant", "type": "checkbox"},
                {"name": "surgical_duplicate_key", "label": "Duplicate Key", "type": "checkbox"},
                {"name": "surgical_other", "label": "Other", "type": "text"},
            ]},
            {"title": ("Criminal Information - particulars of past etc."
                       " (search at library, injuries, bullets or implications)"),
             "fields": [
                {"name": "criminal_info", "label": "Criminal Information", "type": "textarea"},
            ]},
            {"title": "Full Details of Methods Used in Committing Offences", "fields": [
                {"name": "methods_used", "label": "Full Details of Methods Used", "type": "textarea"},
            ]},
            {"title": "Names and Addresses of Children (where applicable)", "fields": [
                {"name": "children_details", "label": "Names and Addresses of Children", "type": "textarea"},
            ]},
            {"title": "Mode of Travelling", "fields": [
                {"name": "mode_of_travelling", "label": "Mode of Travelling", "type": "textarea"},
            ]},
            {"title": "Names and Addresses of Persons who Stand Surety for Accused under Bail(s)", "fields": [
                {"name": "surety_persons", "label": "Names and Addresses of Surety Persons", "type": "textarea"},
            ]},
            {"title": "Head Inspection", "fields": [
                {"name": "head_inspection", "label": "Head Inspection", "type": "textarea"},
            ]},
            {"title": "Commander and Notes Prepared by Suspect", "fields": [
                {"name": "commander_notes", "label": "Commander and Notes Prepared by Suspect", "type": "textarea"},
            ]},
            {"title": "Specimens of Handwriting", "fields": [
                {"name": "handwriting_specimens", "label": "Specimens of Handwriting", "type": "textarea"},
                {"name": "authority_to_detain",
                 "label": ("Authority to detain a person wanted"
                           " (Rank of IO and above) Signature"),
                 "type": "text"},
            ]},
            {"title": "Photograph", "fields": [
                {"name": "photo_attached", "label": "Photo(s) Attached", "type": "select",
                 "options_list": ["Yes", "No"]},
                {"name": "photo_description", "label": "Photo Description", "type": "text"},
            ]},
        ],
    },
    "CR15": {
        "name": "Application for Remand of Accused or Bail Conditions",
        "description": (
            "Application for Remand of Accused or Bail Conditions"
            " (Appendix 25) - CR 15. NB: A copy of this form must be"
            " attached to each case file."
        ),
        "sections": [
            {"title": "Accused Information", "fields": [
                {"name": "case_ref_no", "label": "1. Case Ref. No.", "type": "text", "required": True},
                {"name": "accused_name", "label": "2. Name of Accused", "type": "text", "required": True},
                {"name": "accused_dob", "label": "3. Date of Birth", "type": "date"},
                {"name": "accused_address", "label": "4. Address(es) of Accused", "type": "textarea"},
                {"name": "offence_charged", "label": "5. Offence(s) Charged", "type": "textarea", "required": True},
                {"name": "date_charged", "label": "6. Date Charged", "type": "date"},
                {"name": "previous_charges_convictions",
                 "label": ("7. Previous charge(s)/conviction(s)"
                           " or violation of bail conditions"),
                 "type": "textarea"},
            ]},
            {"title": "8. Application is for (tick one box only)", "fields": [
                {"name": "application_type", "label": "Application Type", "type": "select",
                 "options_list": ["Remand in custody", "Bail with conditions", "Unconditional Bail"],
                 "required": True},
            ]},
            {"title": "9. Reasons for Opposing Bail", "fields": [
                {"name": "reasons_opposing_bail",
                 "label": ("Reasons for opposing bail include previous"
                           " conditions and/or order such as violent"
                           " nature, HIV status etc. (See Bail Act)"),
                 "type": "textarea"},
            ]},
            {"title": "10. Substantial Grounds (if granted bail, defendant(s) likely to)", "fields": [
                {"name": "grounds_details",
                 "label": ("There are substantial Grounds that if granted"
                           " bail defendant(s) likely to:"),
                 "type": "textarea"},
                {"name": "offences_while_on_bail",
                 "label": "11. Offence(s) committed while on bail",
                 "type": "textarea"},
            ]},
            {"title": "12. Suggested Conditions of Bail", "fields": [
                {"name": "bail_surety", "label": "Surety (ies)", "type": "text"},
                {"name": "bail_surrender_travel", "label": "Surrender of Travel Documents", "type": "select",
                 "options_list": ["Yes", "No", "N/A"]},
                {"name": "bail_reporting_conditions", "label": "Reporting Conditions", "type": "text"},
                {"name": "bail_curfew_order", "label": "Curfew Order", "type": "text"},
                {"name": "bail_electronic_monitoring", "label": "Electronic Monitoring/Tag", "type": "select",
                 "options_list": ["Yes", "No", "N/A"]},
                {"name": "bail_stop_order", "label": "Stop Order", "type": "select",
                 "options_list": ["Yes", "No", "N/A"]},
                {"name": "bail_deportee_status", "label": "Deportee Status", "type": "select",
                 "options_list": ["Yes", "No"]},
                {"name": "deportee_year", "label": "State the year deported", "type": "text"},
                {"name": "deportee_offence_reason",
                 "label": "State offence/reason for which deported",
                 "type": "textarea"},
            ]},
            {"title": "13. Co-Defendant Details", "fields": [
                {"name": "co_defendant_details",
                 "label": ("14. Details of Co-Defendant(s) (Name, Court,"
                           " Date, relate to other outstanding cases)"),
                 "type": "textarea"},
            ]},
            {"title": "Investigator & Court Officer", "fields": [
                {"name": "investigator_name_rank", "label": "15. Name & Rank of Investigator", "type": "text"},
                {"name": "dri_court_liaison_signature",
                 "label": "16. Signature of DRI or Court Liaison Officer",
                 "type": "text"},
                {"name": "officer_sign_date", "label": "Date", "type": "date"},
            ]},
            {"title": "17. Dissemination of Court Information", "fields": [
                {"name": "dissemination_details",
                 "label": ("When conditional bail is granted, note details"
                           " of any conditions (include contact address and"
                           " contacts of sureties, reporting times, documents"
                           " to be surrendered). Persons or places the accused"
                           " must not contact or visit, address to which"
                           " curfew order applies."),
                 "type": "textarea"},
            ]},
            {"title": "18. Appearances Before Court on Application for Bail", "fields": [
                {"name": "appearance_1_date", "label": "Date of 1st Appearance", "type": "date"},
                {"name": "appearance_1_reason_denied", "label": "Reason for Denying Bail (1st)", "type": "text"},
                {"name": "appearance_2_date", "label": "Date of 2nd Appearance", "type": "date"},
                {"name": "appearance_2_reason_denied", "label": "Reason for Denying Bail (2nd)", "type": "text"},
                {"name": "appearance_3_date", "label": "Date of 3rd Appearance", "type": "date"},
                {"name": "appearance_3_reason_denied", "label": "Reason for Denying Bail (3rd)", "type": "text"},
                {"name": "appearance_4_date", "label": "Date of 4th Appearance", "type": "date"},
                {"name": "appearance_4_reason_denied", "label": "Reason for Denying Bail (4th)", "type": "text"},
                {"name": "appearance_5_date", "label": "Date of 5th Appearance", "type": "date"},
                {"name": "appearance_5_reason_denied", "label": "Reason for Denying Bail (5th)", "type": "text"},
            ]},
            {"title": "19. Officer Present in Court", "fields": [
                {"name": "officer_present_details", "label": "Details of Officer Present in Court", "type": "text"},
                {"name": "officer_present_date", "label": "20. Date", "type": "date"},
                {"name": "officer_present_contact", "label": "21. Contact", "type": "text"},
            ]},
            {"title": "22. Distribution", "fields": [
                {"name": "dist_prosecutor", "label": "a. Prosecutor", "type": "checkbox"},
                {"name": "dist_case_file_station", "label": "b. Case File at Station", "type": "checkbox"},
                {"name": "dist_dri_nir", "label": "c. DRI / NIR", "type": "checkbox"},
                {"name": "dist_station_other",
                 "label": "d. Station/other associated report (attached photograph)",
                 "type": "checkbox"},
                {"name": "photograph_attached", "label": "Photograph Attached", "type": "select",
                 "options_list": ["Yes", "No"]},
            ]},
        ],
    },
    "CFSR": {
        "name": "Case File Submission Register for Court",
        "description": "Case File Submission Register for Court (Appendix 23) - tracks case file submissions to court",
        "sections": [
            {"title": "Case File Submission Register for Court", "fields": [
                {"name": "case_no", "label": "Case No.", "type": "text", "required": True},
                {"name": "court", "label": "Court", "type": "select", "options": "COURT_TYPES"},
                {"name": "date", "label": "Date", "type": "date", "required": True},
                {"name": "offence", "label": "Offence (r)", "type": "text", "required": True},
                {"name": "complainant", "label": "Complainant", "type": "text"},
                {"name": "accused", "label": "Accused", "type": "text", "required": True},
                {"name": "checklist_attached", "label": "Checklist Attached (reviewed)", "type": "select",
                 "options_list": ["Yes", "No"]},
                {"name": "court_date", "label": "Court Date", "type": "date"},
                {"name": "court_staff_name_signature",
                 "label": "Name & Signature of Court Staff Receiving",
                 "type": "text"},
                {"name": "type_of_case", "label": "Type of Case", "type": "select",
                 "options_list": ["Major", "Minor"]},
                {"name": "remand_bail", "label": "Remand/Bail", "type": "select",
                 "options_list": ["Remand", "Bail"]},
            ]},
        ],
    },
}

# Only the Word templates supplied with the project are active official clones.
# CR10/CFSR remain unavailable until authoritative source templates are added.
CR_FORM_DEFINITIONS = OFFICIAL_CR_FORM_DEFINITIONS


def _load_form_record(conn, case_id, form_id):
    """Load a form by database row id or official form_id string."""
    if str(form_id).isdigit():
        return conn.execute(
            "SELECT * FROM cr_forms WHERE id = ? AND case_id = ?",
            (int(form_id), case_id),
        ).fetchone()
    return conn.execute(
        "SELECT * FROM cr_forms WHERE form_id = ? AND case_id = ?",
        (form_id, case_id),
    ).fetchone()


def _json_form_data(row):
    """Decode stored JSON form data defensively."""
    if not row or not row["form_data"]:
        return {}
    try:
        return json.loads(row["form_data"])
    except (TypeError, json.JSONDecodeError):
        return {}


def _safe_filename_part(value):
    """Return a Windows/browser-safe filename component."""
    return (
        str(value)
        .replace("/", "-")
        .replace("\\", "-")
        .replace(":", "-")
        .replace("*", "-")
        .replace("?", "-")
        .replace('"', "")
        .replace("<", "-")
        .replace(">", "-")
        .replace("|", "-")
    )


@bp.route("/cases/<path:case_id>/forms/new/<form_type>/docx")
@login_required
@permission_required("cr_forms", "read")
def form_word_template(case_id, form_type):
    """Download the exact uploaded Word template for a case workflow."""
    form_type = form_type.upper()
    if not is_official_form(form_type):
        flash(f"Unknown form type: {form_type}", "danger")
        return redirect(url_for("cr_forms.form_list", case_id=case_id))

    return send_from_directory(
        str(OFFICIAL_FORM_DIR),
        source_filename(form_type),
        as_attachment=True,
        download_name=f"{form_type}_{_safe_filename_part(case_id)}_official_template.docx",
    )


@bp.route("/cases/<path:case_id>/forms")
@login_required
@permission_required("cr_forms", "read")
def form_list(case_id):
    """List all CR forms for a case."""
    conn = get_db()
    try:
        case = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if not case:
            flash("Case not found.", "danger")
            return redirect(url_for("cases.case_list"))

        forms = conn.execute(
            "SELECT * FROM cr_forms WHERE case_id = ? ORDER BY form_type, created_at",
            (case_id,)
        ).fetchall()

        return render_template("cr_forms/form_list.html",
                             case=case, forms=forms,
                             form_definitions=CR_FORM_DEFINITIONS)
    finally:
        conn.close()


@bp.route("/cases/<path:case_id>/forms/new/<form_type>", methods=["GET", "POST"])
@login_required
@permission_required("cr_forms", "create")
def form_new(case_id, form_type):
    """Create a new CR form."""
    form_type = form_type.upper()
    if not is_official_form(form_type):
        flash(f"Unknown form type: {form_type}", "danger")
        return redirect(url_for("cr_forms.form_list", case_id=case_id))
    form_def = CR_FORM_DEFINITIONS[form_type]
    layout = get_form_layout(form_type)

    conn = get_db()
    try:
        case = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if not case:
            flash("Case not found.", "danger")
            return redirect(url_for("cases.case_list"))

        if request.method == "POST":
            form_id = generate_form_id(form_type, case_id)
            form_data = collect_form_data(form_type, request.form)

            status = request.form.get("form_status", "Draft")
            name = current_user.full_name
            now = datetime.now().isoformat()

            conn.execute("""
                INSERT INTO cr_forms (form_id, case_id, form_type, form_data,
                                      status, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (form_id, case_id, form_type, json.dumps(form_data),
                  status, name, now, now))

            if status == "Submitted":
                conn.execute("""
                    UPDATE cr_forms SET submitted_by = ?, submitted_at = ?
                    WHERE form_id = ?
                """, (name, now, form_id))

            conn.commit()
            log_audit("cr_forms", form_id, "CREATE", current_user.badge_number,
                     name, f"{form_type} for case {case_id}")
            flash(f"{form_def['name']} ({form_id}) created.", "success")
            return redirect(url_for("cr_forms.form_list", case_id=case_id))

        form_data = prefill_form_data(form_type, case)
        return render_template("cr_forms/form_edit.html",
                             case=case, form_type=form_type,
                             form_def=form_def, form_data=form_data,
                             layout=layout, mode="edit",
                             is_new=True)
    finally:
        conn.close()


@bp.route("/cases/<path:case_id>/forms/<path:form_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("cr_forms", "update")
def form_edit(case_id, form_id):
    """Edit an existing CR form."""
    conn = get_db()
    try:
        form_rec = _load_form_record(conn, case_id, form_id)
        if not form_rec:
            flash("Form not found.", "danger")
            return redirect(url_for("cr_forms.form_list", case_id=case_id))

        case = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        form_type = form_rec["form_type"]
        if not is_official_form(form_type):
            flash(f"Unknown form type: {form_type}", "danger")
            return redirect(url_for("cr_forms.form_list", case_id=case_id))
        form_def = CR_FORM_DEFINITIONS[form_type]
        layout = get_form_layout(form_type)

        existing_data = _json_form_data(form_rec)

        if request.method == "POST":
            form_data = collect_form_data(form_type, request.form)

            status = request.form.get("form_status", "Draft")
            now = datetime.now().isoformat()
            name = current_user.full_name

            conn.execute("""
                UPDATE cr_forms SET form_data = ?, status = ?, updated_at = ?
                WHERE id = ?
            """, (json.dumps(form_data), status, now, form_rec["id"]))

            if status == "Submitted" and not form_rec["submitted_by"]:
                conn.execute("""
                    UPDATE cr_forms SET submitted_by = ?, submitted_at = ?
                    WHERE id = ?
                """, (name, now, form_rec["id"]))

            conn.commit()
            log_audit("cr_forms", form_id, "UPDATE", current_user.badge_number, name)
            flash("Form updated.", "success")
            return redirect(url_for("cr_forms.form_list", case_id=case_id))

        form_data = prefill_form_data(form_type, case, existing_data)
        return render_template("cr_forms/form_edit.html",
                             case=case, form_type=form_type,
                             form_def=form_def, form_data=form_data,
                             layout=layout, mode="edit",
                             form_rec=form_rec, is_new=False)
    finally:
        conn.close()


@bp.route("/cases/<path:case_id>/forms/<path:form_id>/pdf")
@login_required
@permission_required("cr_forms", "export_pdf")
def form_pdf(case_id, form_id):
    """Export a CR form as PDF."""
    conn = get_db()
    try:
        form_rec = _load_form_record(conn, case_id, form_id)
        if not form_rec:
            flash("Form not found.", "danger")
            return redirect(url_for("cr_forms.form_list", case_id=case_id))

        case = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        form_type = form_rec["form_type"]
        form_def = CR_FORM_DEFINITIONS.get(form_type, {})
        form_data = prefill_form_data(form_type, case, _json_form_data(form_rec))

        # Build HTML for PDF
        html = f"""<!DOCTYPE html><html><head>{pdf_base_css()}</head><body>
        {pdf_header_html(f'{form_def.get("name", form_type)} ({form_type})', case_id, form_id)}
        """

        for section in form_def.get("sections", []):
            html += f'<div class="section"><div class="section-title">{section["title"]}</div>'
            html += '<table>'
            for field in section["fields"]:
                val = form_data.get(field["name"], "—")
                html += f'<tr><td class="field-label" style="width:35%">{field["label"]}</td>'
                html += f'<td class="field-value">{val}</td></tr>'
            html += '</table></div>'

        html += '<div class="section"><div class="section-title">Official CR Form Values</div><table>'
        for row in printable_field_rows(form_type, form_data):
            val = row["value"] or "N/A"
            html += f'<tr><td class="field-label" style="width:35%">{row["label"]}</td>'
            html += f'<td class="field-value">{val}</td></tr>'
        html += '</table></div>'

        html += f"""
        <div class="footer">
            Form ID: {form_id} | Status: {form_rec['status']} |
            Created by: {form_rec['created_by']} | Date: {form_rec['created_at']}
        </div>
        </body></html>"""

        pdf_buffer = render_pdf(html)
        if pdf_buffer:
            log_audit("cr_forms", form_id, "EXPORT_PDF",
                     current_user.badge_number, current_user.full_name)
            safe_case_id = case_id.replace("/", "-").replace("\\", "-")
            return Response(
                pdf_buffer.read(),
                mimetype="application/pdf",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="{form_type}_{safe_case_id}.pdf"'
                    )
                }
            )
        else:
            flash("PDF generation unavailable. Showing print view.", "warning")
            return redirect(url_for("cr_forms.form_print", case_id=case_id, form_id=form_id))
    finally:
        conn.close()


@bp.route("/cases/<path:case_id>/forms/<path:form_id>/print")
@login_required
@permission_required("cr_forms", "read")
def form_print(case_id, form_id):
    """Print-optimized view of a CR form."""
    conn = get_db()
    try:
        form_rec = _load_form_record(conn, case_id, form_id)
        if not form_rec:
            flash("Form not found.", "danger")
            return redirect(url_for("cr_forms.form_list", case_id=case_id))

        case = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        form_type = form_rec["form_type"]
        form_def = CR_FORM_DEFINITIONS.get(form_type, {})
        form_data = prefill_form_data(form_type, case, _json_form_data(form_rec))
        layout = get_form_layout(form_type)

        return render_template("cr_forms/form_print.html",
                             case=case, form_rec=form_rec,
                             form_def=form_def, form_data=form_data,
                             layout=layout, mode="print")
    finally:
        conn.close()
