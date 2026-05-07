import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import MainLayout from './components/layout/MainLayout';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import ChangePasswordPage from './pages/ChangePasswordPage';
import HomePage from './pages/HomePage';
import CommandDashboard from './pages/CommandDashboard';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public routes */}
            <Route path="/app/login" element={<LoginPage />} />
            <Route path="/app/register" element={<RegisterPage />} />

            {/* Protected routes with layout */}
            <Route path="/app" element={
              <ProtectedRoute>
                <MainLayout />
              </ProtectedRoute>
            }>
              <Route index element={<HomePage />} />
              <Route path="change-password" element={<ChangePasswordPage />} />
              <Route path="dashboard/command" element={<CommandDashboard />} />

              {/* Placeholder routes for future module conversion */}
              <Route path="cases" element={<PlaceholderPage title="Cases" icon="bi-folder2-open" />} />
              <Route path="cases/new" element={<PlaceholderPage title="New Case Intake" icon="bi-plus-circle" />} />
              <Route path="search" element={<PlaceholderPage title="Advanced Search" icon="bi-funnel" />} />
              <Route path="dpp" element={<PlaceholderPage title="DPP Pipeline" icon="bi-briefcase" />} />
              <Route path="sop" element={<PlaceholderPage title="SOP Checklists" icon="bi-clipboard-check" />} />
              <Route path="unit/:unitId" element={<PlaceholderPage title="Unit Portal" icon="bi-grid-3x3-gap" />} />
              <Route path="admin" element={<PlaceholderPage title="Admin Dashboard" icon="bi-gear" />} />
            </Route>

            {/* Redirect root to app */}
            <Route path="/" element={<Navigate to="/app/" replace />} />
            <Route path="*" element={<Navigate to="/app/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

function PlaceholderPage({ title, icon }: { title: string; icon: string }) {
  return (
    <div className="text-center py-5">
      <i className={`bi ${icon} display-1 text-muted`}></i>
      <h3 className="mt-3">{title}</h3>
      <p className="text-muted">
        This module is being converted to React. <br />
        <a href={`/${title.toLowerCase().replace(/\s+/g, '-')}`} className="btn btn-outline-primary mt-2">
          Use Classic View
        </a>
      </p>
    </div>
  );
}
