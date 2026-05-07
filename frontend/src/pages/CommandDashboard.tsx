import { useEffect, useState } from 'react';
import Row from 'react-bootstrap/Row';
import Col from 'react-bootstrap/Col';
import Card from 'react-bootstrap/Card';
import Spinner from 'react-bootstrap/Spinner';
import Alert from 'react-bootstrap/Alert';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts';
import { fetchCommandDashboard } from '../api/dashboard';
import type { CommandDashboardData } from '../types/user';

const PIE_COLORS = ['#1F3864', '#C00000', '#BF8F00', '#538135', '#7030A0', '#00B0F0', '#8B4513', '#dc3545', '#6c757d', '#198754'];

export default function CommandDashboard() {
  const [data, setData] = useState<CommandDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCommandDashboard()
      .then(setData)
      .catch(() => setError('Failed to load command dashboard.'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="text-center py-5">
        <Spinner animation="border" variant="primary" />
      </div>
    );
  }

  if (error) return <Alert variant="danger">{error}</Alert>;
  if (!data) return null;

  const seizureData = [
    { name: 'Firearms', value: data.seizure_types.firearms },
    { name: 'Narcotics', value: data.seizure_types.narcotics },
  ];

  return (
    <>
      <div className="d-flex align-items-center mb-4">
        <i className="bi bi-speedometer2 fs-3 me-2" style={{ color: '#1F3864' }}></i>
        <h4 className="mb-0">Command Dashboard</h4>
      </div>

      {/* Seizure Overview Cards */}
      <Row className="g-3 mb-4">
        <Col xs={6} md={3}>
          <Card className="border-0 shadow-sm text-center">
            <Card.Body>
              <i className="bi bi-crosshair fs-2 text-danger"></i>
              <h3 className="fw-bold">{data.seizure_types.firearms}</h3>
              <small className="text-muted">Firearm Seizures</small>
            </Card.Body>
          </Card>
        </Col>
        <Col xs={6} md={3}>
          <Card className="border-0 shadow-sm text-center">
            <Card.Body>
              <i className="bi bi-capsule fs-2" style={{ color: '#00B0F0' }}></i>
              <h3 className="fw-bold">{data.seizure_types.narcotics}</h3>
              <small className="text-muted">Narcotics Seizures</small>
            </Card.Body>
          </Card>
        </Col>
        <Col xs={6} md={3}>
          <Card className="border-0 shadow-sm text-center">
            <Card.Body>
              <i className="bi bi-folder2-open fs-2" style={{ color: '#1F3864' }}></i>
              <h3 className="fw-bold">{data.monthly_cases.reduce((s, m) => s + m.count, 0)}</h3>
              <small className="text-muted">Total Cases (12mo)</small>
            </Card.Body>
          </Card>
        </Col>
        <Col xs={6} md={3}>
          <Card className="border-0 shadow-sm text-center">
            <Card.Body>
              <i className="bi bi-graph-up fs-2 text-success"></i>
              <h3 className="fw-bold">{data.case_status.length}</h3>
              <small className="text-muted">Status Categories</small>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Charts */}
      <Row className="g-3 mb-4">
        {/* Monthly Cases Bar Chart */}
        <Col xs={12} lg={8}>
          <Card className="border-0 shadow-sm">
            <Card.Header className="bg-white fw-bold">
              <i className="bi bi-bar-chart me-2"></i>Monthly Case Volume
            </Card.Header>
            <Card.Body>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={[...data.monthly_cases].reverse()}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="count" fill="#1F3864" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card.Body>
          </Card>
        </Col>

        {/* Seizure Type Pie */}
        <Col xs={12} lg={4}>
          <Card className="border-0 shadow-sm">
            <Card.Header className="bg-white fw-bold">
              <i className="bi bi-pie-chart me-2"></i>Seizure Breakdown
            </Card.Header>
            <Card.Body>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie data={seizureData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                    outerRadius={100} label>
                    <Cell fill="#C00000" />
                    <Cell fill="#00B0F0" />
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Case Status Distribution */}
      <Row className="g-3">
        <Col xs={12}>
          <Card className="border-0 shadow-sm">
            <Card.Header className="bg-white fw-bold">
              <i className="bi bi-list-check me-2"></i>Case Status Distribution
            </Card.Header>
            <Card.Body>
              <ResponsiveContainer width="100%" height={Math.max(250, data.case_status.length * 30)}>
                <BarChart data={data.case_status} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" />
                  <YAxis dataKey="status" type="category" width={250} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {data.case_status.map((_, index) => (
                      <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </>
  );
}
