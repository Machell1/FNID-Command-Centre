import { useState, type FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import Container from 'react-bootstrap/Container';
import Card from 'react-bootstrap/Card';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import Alert from 'react-bootstrap/Alert';
import InputGroup from 'react-bootstrap/InputGroup';

export default function LoginPage() {
  const { login, error, clearError, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [badge, setBadge] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  if (isAuthenticated) {
    navigate('/app/', { replace: true });
    return null;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    clearError();
    setSubmitting(true);
    try {
      const result = await login(badge, password);
      if (result.ok) {
        if (result.redirect === 'change_password') {
          navigate('/app/change-password');
        } else if (result.redirect === 'pending_verification') {
          navigate('/app/pending-verification');
        } else {
          navigate('/app/');
        }
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-page">
      <Container className="d-flex justify-content-center align-items-center" style={{ minHeight: '100vh' }}>
        <Card className="shadow-lg border-0" style={{ maxWidth: 440, width: '100%' }}>
          <Card.Header className="text-center text-white py-4" style={{ backgroundColor: '#1F3864' }}>
            <i className="bi bi-shield-shaded fs-1 d-block mb-2"></i>
            <h3 className="fw-bold mb-0">FNID AREA 3</h3>
            <small className="opacity-75">Case Management System</small>
            <div className="mt-2">
              <small className="opacity-50">Jamaica Constabulary Force</small>
            </div>
            <div>
              <small className="opacity-50">Firearms & Narcotics Investigation Division</small>
            </div>
          </Card.Header>
          <Card.Body className="p-4">
            <h5 className="text-center mb-3">Sign In</h5>

            {error && (
              <Alert variant="danger" dismissible onClose={clearError}>
                {error}
              </Alert>
            )}

            <Form onSubmit={handleSubmit}>
              <Form.Group className="mb-3">
                <Form.Label>
                  <i className="bi bi-person-badge me-1"></i>Badge Number
                </Form.Label>
                <Form.Control
                  type="text"
                  placeholder="e.g. JCF-4455"
                  value={badge}
                  onChange={(e) => setBadge(e.target.value)}
                  required
                  autoFocus
                  autoComplete="username"
                />
              </Form.Group>

              <Form.Group className="mb-3">
                <Form.Label>
                  <i className="bi bi-lock me-1"></i>Password
                </Form.Label>
                <InputGroup>
                  <Form.Control
                    type={showPassword ? 'text' : 'password'}
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    autoComplete="current-password"
                  />
                  <Button
                    variant="outline-secondary"
                    onClick={() => setShowPassword(!showPassword)}
                    type="button"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    <i className={`bi ${showPassword ? 'bi-eye-slash' : 'bi-eye'}`}></i>
                  </Button>
                </InputGroup>
              </Form.Group>

              <Button
                variant="primary"
                type="submit"
                className="w-100 fw-bold py-2"
                disabled={submitting}
                style={{ backgroundColor: '#1F3864', borderColor: '#1F3864' }}
              >
                {submitting ? (
                  <>
                    <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                    Signing In...
                  </>
                ) : (
                  <>
                    <i className="bi bi-box-arrow-in-right me-2"></i>Sign In
                  </>
                )}
              </Button>
            </Form>
          </Card.Body>
          <Card.Footer className="text-center bg-light py-3">
            <small className="text-muted">
              New officer? <Link to="/app/register" className="fw-bold">Activate your account</Link>
            </small>
          </Card.Footer>
        </Card>
      </Container>

      <div className="text-center text-muted py-3" style={{ position: 'fixed', bottom: 0, width: '100%' }}>
        <small>RESTRICTED - Official Use Only | Manchester | St. Elizabeth | Clarendon</small>
      </div>
    </div>
  );
}
