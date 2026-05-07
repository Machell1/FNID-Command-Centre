import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Row from 'react-bootstrap/Row';
import Col from 'react-bootstrap/Col';
import Card from 'react-bootstrap/Card';
import Alert from 'react-bootstrap/Alert';
import Spinner from 'react-bootstrap/Spinner';
import Badge from 'react-bootstrap/Badge';
import { useAuth } from '../hooks/useAuth';
import { fetchDashboard } from '../api/dashboard';
import type { DashboardData } from '../types/user';

const STAT_ICONS: Record<string, { icon: string; color: string; label: string }> = {
  cases: { icon: 'bi-folder2-open', color: '#1F3864', label: 'Total Cases' },
  intel: { icon: 'bi-eye', color: '#BF8F00', label: 'Intel Reports' },
  operations: { icon: 'bi-bullseye', color: '#C00000', label: 'Operations' },
  firearms: { icon: 'bi-crosshair', color: '#dc3545', label: 'Firearm Seizures' },
  narcotics: { icon: 'bi-capsule', color: '#00B0F0', label: 'Narcotics Seizures' },
  arrests: { icon: 'bi-person-badge', color: '#7030A0', label: 'Arrests' },
};

export default function HomePage() {
  const { user } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDashboard()
      .then(setData)
      .catch(() => setError('Failed to load dashboard data.'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="text-center py-5">
        <Spinner animation="border" variant="primary" />
        <p className="mt-2">Loading dashboard...</p>
      </div>
    );
  }

  if (error) {
    return <Alert variant="danger">{error}</Alert>;
  }

  if (!data) return null;

  return (
    <>
      {/* Welcome Banner */}
      <div className="rounded p-4 mb-4 text-white" style={{ backgroundColor: '#1F3864' }}>
        <Row className="align-items-center">
          <Col>
            <h4 className="mb-1">
              <i className="bi bi-shield-shaded me-2"></i>
              Welcome, {user?.rank} {user?.full_name}
            </h4>
            <p className="mb-0 opacity-75">
              FNID Area 3 Operational Portal — Firearms & Narcotics Investigation Division
            </p>
          </Col>
          <Col xs="auto" className="d-none d-md-block">
            <Badge bg="warning" text="dark" className="fs-6 px-3 py-2">
              {user?.role?.toUpperCase()}
            </Badge>
          </Col>
        </Row>
      </div>

      {/* Alerts */}
      {data.alerts.length > 0 && (
        <div className="mb-4">
          {data.alerts.map((alert) => (
            <Alert key={alert.id} variant={alert.severity === 'critical' ? 'danger' : 'warning'} dismissible>
              <strong>{alert.title}</strong> — {alert.message}
            </Alert>
          ))}
        </div>
      )}

      {/* Stats Cards */}
      <Row className="g-3 mb-4">
        {Object.entries(data.stats).map(([key, value]) => {
          const info = STAT_ICONS[key];
          return (
            <Col xs={6} md={4} lg={2} key={key}>
              <Card className="h-100 border-0 shadow-sm text-center">
                <Card.Body className="py-3">
                  <i className={`bi ${info.icon} fs-2`} style={{ color: info.color }}></i>
                  <h3 className="fw-bold mb-0 mt-1">{value.toLocaleString()}</h3>
                  <small className="text-muted">{info.label}</small>
                </Card.Body>
              </Card>
            </Col>
          );
        })}
      </Row>

      {/* Quick Actions */}
      <h5 className="mb-3"><i className="bi bi-lightning me-2"></i>Quick Actions</h5>
      <Row className="g-3 mb-4">
        <Col xs={6} md={3}>
          <Link to="/app/cases/new" className="text-decoration-none">
            <Card className="h-100 border-0 shadow-sm text-center hover-shadow">
              <Card.Body>
                <i className="bi bi-plus-circle fs-3 text-primary"></i>
                <p className="mb-0 mt-2 fw-bold text-dark">New Case</p>
              </Card.Body>
            </Card>
          </Link>
        </Col>
        <Col xs={6} md={3}>
          <Link to="/app/search" className="text-decoration-none">
            <Card className="h-100 border-0 shadow-sm text-center">
              <Card.Body>
                <i className="bi bi-search fs-3 text-success"></i>
                <p className="mb-0 mt-2 fw-bold text-dark">Search Cases</p>
              </Card.Body>
            </Card>
          </Link>
        </Col>
        <Col xs={6} md={3}>
          <Link to="/app/dashboard/command" className="text-decoration-none">
            <Card className="h-100 border-0 shadow-sm text-center">
              <Card.Body>
                <i className="bi bi-speedometer2 fs-3 text-warning"></i>
                <p className="mb-0 mt-2 fw-bold text-dark">Dashboard</p>
              </Card.Body>
            </Card>
          </Link>
        </Col>
        <Col xs={6} md={3}>
          <Link to="/app/dpp" className="text-decoration-none">
            <Card className="h-100 border-0 shadow-sm text-center">
              <Card.Body>
                <i className="bi bi-briefcase fs-3 text-info"></i>
                <p className="mb-0 mt-2 fw-bold text-dark">DPP Pipeline</p>
              </Card.Body>
            </Card>
          </Link>
        </Col>
      </Row>

      {/* Unit Portals */}
      <h5 className="mb-3"><i className="bi bi-grid-3x3-gap me-2"></i>Unit Portals</h5>
      <Row className="g-3 mb-4">
        {Object.entries(data.portals).map(([key, portal]) => (
          <Col xs={12} sm={6} lg={4} key={key}>
            <Link to={`/app/unit/${key}`} className="text-decoration-none">
              <Card className="h-100 border-0 shadow-sm border-start border-4" style={{ borderColor: portal.color + ' !important' }}>
                <Card.Body>
                  <div className="d-flex align-items-center">
                    <i className={`bi ${portal.icon} fs-3 me-3`} style={{ color: portal.color }}></i>
                    <div>
                      <h6 className="mb-0 text-dark fw-bold">{portal.name}</h6>
                      <small className="text-muted">{portal.description}</small>
                    </div>
                  </div>
                </Card.Body>
              </Card>
            </Link>
          </Col>
        ))}
      </Row>

      {/* Recent Activity */}
      <h5 className="mb-3"><i className="bi bi-clock-history me-2"></i>Recent Activity</h5>
      <Card className="border-0 shadow-sm mb-4">
        <Card.Body className="p-0">
          <div className="table-responsive">
            <table className="table table-hover mb-0">
              <thead className="table-light">
                <tr>
                  <th>Action</th>
                  <th>Officer</th>
                  <th className="d-none d-md-table-cell">Details</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_activity.length === 0 ? (
                  <tr><td colSpan={4} className="text-center text-muted py-3">No recent activity</td></tr>
                ) : (
                  data.recent_activity.map((item, idx) => (
                    <tr key={idx}>
                      <td><Badge bg="secondary">{item.action}</Badge></td>
                      <td>{item.name || item.badge}</td>
                      <td className="d-none d-md-table-cell"><small className="text-muted">{item.details}</small></td>
                      <td><small className="text-muted">{new Date(item.time).toLocaleString()}</small></td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card.Body>
      </Card>
    </>
  );
}
