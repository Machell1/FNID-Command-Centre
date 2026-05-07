"""Tests for the FNID Role-Based Access Control module."""

from fnid_portal.auth import User
from fnid_portal.rbac import can_access, can_view_sensitive, is_supervisor


def _make_user(role):
    """Helper to create a User with a given role."""
    return User(
        badge_number="TEST",
        full_name="Test User",
        rank="Inspector",
        section="HQ",
        role=role,
    )


def test_admin_can_access_everything(app):
    """Admin role has access to every resource and action."""
    with app.app_context():
        admin = _make_user("admin")
        assert can_access(admin, "cases", "create") is True
        assert can_access(admin, "cases", "delete") is True
        assert can_access(admin, "intel", "targets") is True
        assert can_access(admin, "admin", "users") is True
        assert can_access(admin, "file_movement", "checkout_original") is True


def test_io_can_create_read_update_cases(app):
    """IO can create, read, and update cases but not delete."""
    with app.app_context():
        io = _make_user("io")
        assert can_access(io, "cases", "create") is True
        assert can_access(io, "cases", "read") is True
        assert can_access(io, "cases", "update") is True
        assert can_access(io, "cases", "delete") is False


def test_viewer_read_only(app):
    """Viewer can only read, not create/update/delete."""
    with app.app_context():
        viewer = _make_user("viewer")
        assert can_access(viewer, "cases", "read") is True
        assert can_access(viewer, "cases", "create") is False
        assert can_access(viewer, "cases", "update") is False
        assert can_access(viewer, "cases", "delete") is False


def test_registrar_file_movement_access(app):
    """Registrar has file_movement create, read, and update access."""
    with app.app_context():
        registrar = _make_user("registrar")
        assert can_access(registrar, "file_movement", "create") is True
        assert can_access(registrar, "file_movement", "read") is True
        assert can_access(registrar, "file_movement", "update") is True
        assert can_access(registrar, "file_movement", "checkout_original") is True


def test_intel_officer_intel_access(app):
    """Intel officer can access intel targets and link analysis."""
    with app.app_context():
        intel = _make_user("intel_officer")
        assert can_access(intel, "intel", "targets") is True
        assert can_access(intel, "intel", "link_analysis") is True
        assert can_access(intel, "intel", "create") is True
        assert can_access(intel, "intel", "read") is True


def test_unauthenticated_user_denied(app):
    """An unauthenticated (None) user is always denied access."""
    with app.app_context():
        assert can_access(None, "cases", "read") is False


def test_is_supervisor(app):
    """is_supervisor returns True for admin, dco, ddi, station_mgr."""
    with app.app_context():
        for role in ("admin", "dco", "ddi", "station_mgr"):
            user = _make_user(role)
            assert is_supervisor(user) is True, f"{role} should be a supervisor"

        for role in ("io", "viewer", "registrar", "intel_officer"):
            user = _make_user(role)
            assert is_supervisor(user) is False, f"{role} should not be a supervisor"


def test_can_view_sensitive(app):
    """can_view_sensitive returns True for admin, dco, ddi, intel_officer."""
    with app.app_context():
        for role in ("admin", "dco", "ddi", "intel_officer"):
            user = _make_user(role)
            assert can_view_sensitive(user) is True, f"{role} should view sensitive"

        for role in ("io", "viewer", "registrar", "station_mgr"):
            user = _make_user(role)
            assert can_view_sensitive(user) is False, f"{role} should not view sensitive"


def test_role_required_redirects_unauthorized(client, app):
    """Routes protected by role_required redirect unauthenticated users."""
    # Admin panel requires admin or dco role.
    # An unauthenticated request should redirect to login.
    resp = client.get("/admin/")
    assert resp.status_code in (302, 308)
    assert "/login" in resp.headers.get("Location", "")


def test_role_required_allows_admin(admin_client, app):
    """Admin client can access admin-protected routes."""
    resp = admin_client.get("/admin/")
    # Should get 200 (admin dashboard) or at least not a redirect to login
    assert resp.status_code == 200


def test_io_cannot_access_admin_routes(io_client, app):
    """IO client should be redirected away from /admin/."""
    resp = io_client.get("/admin/")
    assert resp.status_code in (302, 303)
    location = resp.headers.get("Location", "")
    # Should redirect to home, not to admin dashboard
    assert "/admin/" not in location or "/login" in location
