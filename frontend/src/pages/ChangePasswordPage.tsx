import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { changePassword } from '../api/auth';
import Container from 'react-bootstrap/Container';
import Card from 'react-bootstrap/Card';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import Alert from 'react-bootstrap/Alert';

export default function ChangePasswordPage() {
  const navigate = useNavigate();
  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (newPw !== confirmPw) {
      setError('New passwords do not match.');
      return;
    }

    setSubmitting(true);
    try {
      const data = await changePassword(currentPw, newPw, confirmPw);
      if (data.ok) {
        navigate('/app/');
      } else {
        setError(data.error || 'Password change failed.');
      }
    } catch (err: any) {
      setError(err.response?.data?.error || 'Password change failed.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Container className="py-4" style={{ maxWidth: 500 }}>
      <Card className="shadow">
        <Card.Header className="text-white" style={{ backgroundColor: '#1F3864' }}>
          <h5 className="mb-0"><i className="bi bi-key me-2"></i>Change Password</h5>
        </Card.Header>
        <Card.Body>
          {error && <Alert variant="danger" dismissible onClose={() => setError(null)}>{error}</Alert>}
          <Form onSubmit={handleSubmit}>
            <Form.Group className="mb-3">
              <Form.Label>Current Password</Form.Label>
              <Form.Control type="password" value={currentPw} onChange={(e) => setCurrentPw(e.target.value)} />
            </Form.Group>
            <Form.Group className="mb-3">
              <Form.Label>New Password</Form.Label>
              <Form.Control type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} required minLength={10} />
            </Form.Group>
            <Form.Group className="mb-3">
              <Form.Label>Confirm New Password</Form.Label>
              <Form.Control type="password" value={confirmPw} onChange={(e) => setConfirmPw(e.target.value)} required />
            </Form.Group>
            <Button variant="primary" type="submit" className="w-100" disabled={submitting}
              style={{ backgroundColor: '#1F3864', borderColor: '#1F3864' }}>
              {submitting ? 'Changing...' : 'Change Password'}
            </Button>
          </Form>
        </Card.Body>
      </Card>
    </Container>
  );
}
