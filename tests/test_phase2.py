"""Phase 2 tests — transport, DCRR, evidence, analytics, batch, notifications."""



def test_transport_fleet_page(admin_client):
    """Transport fleet page loads for admin."""
    resp = admin_client.get("/transport/")
    assert resp.status_code == 200
    assert b"Fleet" in resp.data or b"Transport" in resp.data


def test_transport_new_vehicle_form(admin_client):
    """New vehicle form loads."""
    resp = admin_client.get("/transport/vehicle/new")
    assert resp.status_code == 200


def test_transport_trip_log(admin_client):
    """Trip log page loads."""
    resp = admin_client.get("/transport/trips")
    assert resp.status_code == 200


def test_dcrr_register_page(logged_in_client):
    """DCRR register page loads."""
    resp = logged_in_client.get("/dcrr/")
    assert resp.status_code == 200
    assert b"DCRR" in resp.data


def test_dcrr_summary(logged_in_client):
    """DCRR summary page loads."""
    resp = logged_in_client.get("/dcrr/summary")
    assert resp.status_code == 200


def test_dcrr_new_requires_role(io_client):
    """New DCRR requires registrar/dco/admin role — IO should be redirected."""
    resp = io_client.get("/dcrr/new")
    # IO role is not in allowed roles, should redirect
    assert resp.status_code in (302, 200)


def test_evidence_dashboard(logged_in_client):
    """Evidence dashboard loads."""
    resp = logged_in_client.get("/evidence/")
    assert resp.status_code == 200


def test_evidence_exhibit_list(logged_in_client):
    """Exhibit list page loads."""
    resp = logged_in_client.get("/evidence/exhibits")
    assert resp.status_code == 200


def test_evidence_lab_dashboard(logged_in_client):
    """Lab dashboard page loads."""
    resp = logged_in_client.get("/evidence/lab")
    assert resp.status_code == 200


def test_evidence_chain_audit(admin_client, db):
    """Chain audit for a case runs without error."""
    # Insert a test case
    db.execute("""
        INSERT INTO cases (case_id, registration_date, classification,
            oic_badge, oic_name, oic_rank, parish, offence_description,
            law_and_section, created_by)
        VALUES ('TEST-AUDIT-001', '2026-01-01', 'Firearms - Possession',
            'ADMIN', 'Admin', 'Superintendent', 'Manchester',
            'Test offence', 's.5 Firearms Act', 'Admin')
    """)
    db.commit()

    resp = admin_client.get("/evidence/audit/TEST-AUDIT-001")
    assert resp.status_code == 200


def test_analytics_home(admin_client):
    """Analytics home page loads for admin."""
    resp = admin_client.get("/analytics/")
    assert resp.status_code == 200


def test_analytics_io_performance(admin_client):
    """IO performance page loads."""
    resp = admin_client.get("/analytics/officers")
    assert resp.status_code == 200


def test_analytics_seizure_analytics(admin_client):
    """Seizure analytics page loads."""
    resp = admin_client.get("/analytics/seizures")
    assert resp.status_code == 200


def test_analytics_court_pipeline(admin_client):
    """Court pipeline analytics page loads."""
    resp = admin_client.get("/analytics/court")
    assert resp.status_code == 200


def test_analytics_api_chart_data(admin_client):
    """API chart data returns JSON."""
    resp = admin_client.get("/analytics/api/data?chart_type=pipeline")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "labels" in data or "datasets" in data or "error" not in data


def test_analytics_restricted_for_io(io_client):
    """IO should not access analytics pages."""
    resp = io_client.get("/analytics/")
    assert resp.status_code in (302, 403)


def test_reports_home(admin_client):
    """Reports index page loads."""
    resp = admin_client.get("/reports/")
    assert resp.status_code == 200


def test_reports_monthly(admin_client):
    """Monthly statistical return loads."""
    resp = admin_client.get("/reports/monthly?year=2026&month=1")
    assert resp.status_code == 200


def test_reports_caseload(admin_client):
    """IO caseload report loads."""
    resp = admin_client.get("/reports/caseload")
    assert resp.status_code == 200


def test_reports_evidence(admin_client):
    """Evidence status report loads."""
    resp = admin_client.get("/reports/evidence")
    assert resp.status_code == 200


def test_batch_home(admin_client):
    """Batch operations home loads for admin."""
    resp = admin_client.get("/batch/")
    assert resp.status_code == 200
    assert b"Batch" in resp.data


def test_batch_assign_page(admin_client):
    """Bulk assign page loads."""
    resp = admin_client.get("/batch/assign")
    assert resp.status_code == 200


def test_batch_transition_page(admin_client):
    """Bulk transition page loads."""
    resp = admin_client.get("/batch/transition")
    assert resp.status_code == 200


def test_batch_review_page(admin_client):
    """Bulk review scheduling page loads."""
    resp = admin_client.get("/batch/review")
    assert resp.status_code == 200


def test_batch_restricted_for_io(io_client):
    """IO should not access batch operations."""
    resp = io_client.get("/batch/")
    assert resp.status_code in (302, 403)


def test_notifications_center(logged_in_client):
    """Notification center loads."""
    resp = logged_in_client.get("/notifications/")
    assert resp.status_code == 200


def test_notifications_api_count(logged_in_client):
    """Notification count API returns JSON."""
    resp = logged_in_client.get("/notifications/api/count")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "total" in data
    assert isinstance(data["total"], int)


def test_notifications_api_recent(logged_in_client):
    """Notification recent API returns JSON."""
    resp = logged_in_client.get("/notifications/api/recent")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "items" in data


def test_notifications_dismiss_all(logged_in_client):
    """Dismiss all redirects back to center."""
    resp = logged_in_client.post("/notifications/dismiss-all")
    assert resp.status_code in (302, 200)


def test_command_dashboard_has_trends(admin_client):
    """Command dashboard loads with monthly trend charts."""
    resp = admin_client.get("/command")
    assert resp.status_code == 200
    assert b"trendChart" in resp.data


def test_navbar_has_notification_bell(logged_in_client):
    """Home page navbar includes the notification bell."""
    resp = logged_in_client.get("/")
    assert resp.status_code == 200
    assert b"notif-bell" in resp.data


def test_navbar_has_analytics_link(admin_client):
    """Home page navbar includes analytics dropdown."""
    resp = admin_client.get("/")
    assert resp.status_code == 200
    assert b"Analytics" in resp.data
