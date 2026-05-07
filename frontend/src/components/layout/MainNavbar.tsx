import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Navbar from 'react-bootstrap/Navbar';
import Nav from 'react-bootstrap/Nav';
import NavDropdown from 'react-bootstrap/NavDropdown';
import Container from 'react-bootstrap/Container';
import Button from 'react-bootstrap/Button';
import Badge from 'react-bootstrap/Badge';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import { useAuth } from '../../hooks/useAuth';
import { fetchNotificationCount } from '../../api/dashboard';

export default function MainNavbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [notifCount, setNotifCount] = useState(0);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    async function poll() {
      try {
        const data = await fetchNotificationCount();
        setNotifCount(data.total);
      } catch { /* ignore */ }
    }
    poll();
    interval = setInterval(poll, 60000);
    return () => clearInterval(interval);
  }, []);

  // Keyboard shortcut: Ctrl+K to focus search
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        document.getElementById('global-search-spa')?.focus();
      }
    }
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  async function handleLogout() {
    await logout();
    navigate('/app/login');
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (searchQuery.trim()) {
      // Search will navigate to search results (future implementation)
      setSearchQuery('');
    }
  }

  const isAdmin = user?.role === 'admin' || user?.role === 'dco';
  const isSupervisor = ['admin', 'dco', 'ddi', 'station_mgr'].includes(user?.role || '');

  return (
    <Navbar
      expand="lg"
      variant="dark"
      sticky="top"
      expanded={expanded}
      onToggle={setExpanded}
      style={{ backgroundColor: '#1F3864' }}
    >
      <Container fluid>
        {/* Brand */}
        <Navbar.Brand as={Link} to="/app/" className="d-flex align-items-center">
          <i className="bi bi-shield-shaded me-2 fs-4"></i>
          <div>
            <span className="fw-bold">FNID</span>
            <small className="d-none d-md-inline text-white-50 ms-2">Area 3 Case Management</small>
          </div>
        </Navbar.Brand>

        <Navbar.Toggle aria-controls="main-nav-spa" />

        <Navbar.Collapse id="main-nav-spa">
          <Nav className="me-auto">
            {/* Cases */}
            <NavDropdown title={<><i className="bi bi-folder2-open me-1"></i>Cases</>} id="nav-cases">
              <NavDropdown.Item as={Link} to="/app/cases" onClick={() => setExpanded(false)}>
                <i className="bi bi-list-ul me-2"></i>All Cases
              </NavDropdown.Item>
              <NavDropdown.Item as={Link} to="/app/cases/new" onClick={() => setExpanded(false)}>
                <i className="bi bi-plus-circle me-2"></i>New Case Intake
              </NavDropdown.Item>
              <NavDropdown.Divider />
              <NavDropdown.Item as={Link} to="/app/search" onClick={() => setExpanded(false)}>
                <i className="bi bi-funnel me-2"></i>Advanced Search
              </NavDropdown.Item>
              <NavDropdown.Divider />
              <NavDropdown.Item as={Link} to="/app/dpp" onClick={() => setExpanded(false)}>
                <i className="bi bi-briefcase me-2"></i>DPP Pipeline
              </NavDropdown.Item>
              <NavDropdown.Item as={Link} to="/app/sop" onClick={() => setExpanded(false)}>
                <i className="bi bi-clipboard-check me-2"></i>SOP Checklists
              </NavDropdown.Item>
            </NavDropdown>

            {/* Portals */}
            <NavDropdown title={<><i className="bi bi-grid-3x3-gap me-1"></i>Portals</>} id="nav-portals">
              <NavDropdown.Item as={Link} to="/app/unit/intel" onClick={() => setExpanded(false)}>
                <i className="bi bi-eye me-2" style={{ color: '#BF8F00' }}></i>Intelligence Unit
              </NavDropdown.Item>
              <NavDropdown.Item as={Link} to="/app/unit/operations" onClick={() => setExpanded(false)}>
                <i className="bi bi-bullseye me-2" style={{ color: '#C00000' }}></i>Operations Unit
              </NavDropdown.Item>
              <NavDropdown.Item as={Link} to="/app/unit/seizures" onClick={() => setExpanded(false)}>
                <i className="bi bi-shield-lock me-2" style={{ color: '#00B0F0' }}></i>Seizures Unit
              </NavDropdown.Item>
              <NavDropdown.Item as={Link} to="/app/unit/arrests" onClick={() => setExpanded(false)}>
                <i className="bi bi-person-badge me-2" style={{ color: '#7030A0' }}></i>Arrests & Court
              </NavDropdown.Item>
              <NavDropdown.Item as={Link} to="/app/unit/forensics" onClick={() => setExpanded(false)}>
                <i className="bi bi-fingerprint me-2" style={{ color: '#538135' }}></i>Forensics & Evidence
              </NavDropdown.Item>
              <NavDropdown.Item as={Link} to="/app/unit/registry" onClick={() => setExpanded(false)}>
                <i className="bi bi-journal-check me-2" style={{ color: '#8B4513' }}></i>Case Registry
              </NavDropdown.Item>
            </NavDropdown>

            {/* Analytics (supervisor+) */}
            {isSupervisor && (
              <NavDropdown title={<><i className="bi bi-bar-chart-line me-1"></i>Analytics</>} id="nav-analytics">
                <NavDropdown.Item as={Link} to="/app/dashboard/command" onClick={() => setExpanded(false)}>
                  <i className="bi bi-speedometer2 me-2"></i>Command Dashboard
                </NavDropdown.Item>
              </NavDropdown>
            )}

            {/* Admin (admin/dco only) */}
            {isAdmin && (
              <NavDropdown title={<><i className="bi bi-gear me-1"></i>Admin</>} id="nav-admin">
                <NavDropdown.Item as={Link} to="/app/admin" onClick={() => setExpanded(false)}>
                  <i className="bi bi-speedometer2 me-2"></i>Dashboard
                </NavDropdown.Item>
              </NavDropdown>
            )}
          </Nav>

          {/* Search bar */}
          <Form className="d-flex me-lg-3 my-2 my-lg-0" onSubmit={handleSearch} role="search">
            <InputGroup size="sm">
              <Form.Control
                type="text"
                id="global-search-spa"
                placeholder="Search cases... (Ctrl+K)"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                aria-label="Search cases"
                style={{ minWidth: 180 }}
              />
              <Button variant="outline-light" type="submit" aria-label="Search">
                <i className="bi bi-search"></i>
              </Button>
            </InputGroup>
          </Form>

          {/* Right side: notifications + user menu + SIGN OUT */}
          <div className="d-flex align-items-center flex-wrap gap-2">
            {/* Notification Bell */}
            <Button variant="link" className="text-white position-relative p-1" title="Notifications">
              <i className="bi bi-bell fs-5"></i>
              {notifCount > 0 && (
                <Badge bg="danger" pill className="position-absolute top-0 start-100 translate-middle">
                  {notifCount > 99 ? '99+' : notifCount}
                </Badge>
              )}
            </Button>

            {/* User dropdown with profile + sign out */}
            <NavDropdown
              title={
                <span>
                  <Badge bg="warning" text="dark" className="me-1">
                    <i className="bi bi-person-badge me-1"></i>
                    {user?.full_name} <small>({user?.role})</small>
                  </Badge>
                </span>
              }
              id="nav-user-menu"
              align="end"
            >
              <NavDropdown.Header>
                <strong>{user?.rank} {user?.full_name}</strong>
                <br />
                <small className="text-muted">{user?.section}</small>
                <br />
                <small className="text-muted">Badge: {user?.badge_number}</small>
              </NavDropdown.Header>
              <NavDropdown.Divider />
              <NavDropdown.Item as={Link} to="/app/change-password" onClick={() => setExpanded(false)}>
                <i className="bi bi-key me-2"></i>Change Password
              </NavDropdown.Item>
              <NavDropdown.Divider />
              <NavDropdown.Item onClick={handleLogout} className="text-danger fw-bold">
                <i className="bi bi-box-arrow-right me-2"></i>Sign Out
              </NavDropdown.Item>
            </NavDropdown>

            {/* ===== PROMINENT SIGN OUT BUTTON (always visible) ===== */}
            <Button
              variant="outline-danger"
              size="sm"
              onClick={handleLogout}
              className="fw-bold d-flex align-items-center"
              title="Sign Out"
              style={{ borderWidth: 2 }}
            >
              <i className="bi bi-box-arrow-right me-1"></i>
              <span>Sign Out</span>
            </Button>
          </div>

          {/* Mobile-only: extra prominent sign out at bottom of menu */}
          <div className="d-lg-none border-top border-secondary mt-3 pt-3 pb-2">
            <Button
              variant="danger"
              className="w-100 fw-bold py-2"
              onClick={handleLogout}
            >
              <i className="bi bi-box-arrow-right me-2"></i>Sign Out
            </Button>
          </div>
        </Navbar.Collapse>
      </Container>
    </Navbar>
  );
}
