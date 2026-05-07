import { useState, type FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { registerUser } from '../api/auth';
import Container from 'react-bootstrap/Container';
import Card from 'react-bootstrap/Card';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import Alert from 'react-bootstrap/Alert';

export default function RegisterPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }

    setSubmitting(true);
    try {
      const data = await registerUser(email, password, confirm);
      if (data.ok) {
        setSuccess(data.message || 'Account activated. Please sign in.');
        setTimeout(() => navigate('/app/login'), 3000);
      } else {
        setError(data.error || 'Registration failed.');
      }
    } catch (err: any) {
      setError(err.response?.data?.error || 'Registration failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Container className="d-flex justify-content-center align-items-center" style={{ minHeight: '100vh' }}>
      <Card className="shadow-lg border-0" style={{ maxWidth: 440, width: '100%' }}>
        <Card.Header className="text-center text-white py-4" style={{ backgroundColor: '#1F3864' }}>
          <i className="bi bi-shield-shaded fs-1 d-block mb-2"></i>
          <h3 className="fw-bold mb-0">Activate Account</h3>
          <small className="opacity-75">FNID Area 3 Personnel Only</small>
        </Card.Header>
        <Card.Body className="p-4">
          {error && <Alert variant="danger" dismissible onClose={() => setError(null)}>{error}</Alert>}
          {success && <Alert variant="success">{success}</Alert>}

          <Form onSubmit={handleSubmit}>
            <Form.Group className="mb-3">
              <Form.Label><i className="bi bi-envelope me-1"></i>JCF Email</Form.Label>
              <Form.Control
                type="email"
                placeholder="name@jcf.gov.jm"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
              <Form.Text className="text-muted">Must be your @jcf.gov.jm webmail address</Form.Text>
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label><i className="bi bi-lock me-1"></i>Choose Password</Form.Label>
              <Form.Control
                type="password"
                placeholder="Minimum 10 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={10}
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label><i className="bi bi-lock-fill me-1"></i>Confirm Password</Form.Label>
              <Form.Control
                type="password"
                placeholder="Re-enter your password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
              />
            </Form.Group>

            <Button variant="primary" type="submit" className="w-100 fw-bold py-2" disabled={submitting}
              style={{ backgroundColor: '#1F3864', borderColor: '#1F3864' }}>
              {submitting ? 'Activating...' : 'Activate Account'}
            </Button>
          </Form>
        </Card.Body>
        <Card.Footer className="text-center bg-light py-3">
          <small className="text-muted">
            Already activated? <Link to="/app/login" className="fw-bold">Sign In</Link>
          </small>
        </Card.Footer>
      </Card>
    </Container>
  );
}
