import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

// Fetch CSRF token on first load and attach to all mutating requests
let csrfToken: string | null = null;

async function ensureCsrfToken() {
  if (!csrfToken) {
    try {
      const res = await axios.get('/api/v1/csrf-token');
      csrfToken = res.data.csrf_token;
    } catch {
      // CSRF endpoint may not be available in dev
    }
  }
  return csrfToken;
}

api.interceptors.request.use(async (config) => {
  if (config.method && ['post', 'put', 'patch', 'delete'].includes(config.method)) {
    const token = await ensureCsrfToken();
    if (token) {
      config.headers['X-CSRFToken'] = token;
    }
  }
  return config;
});

export default api;
