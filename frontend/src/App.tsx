/**
 * CampusFix Primary Application Shell & Route Configuration
 *
 * Implements:
 * - Public routes: /login, /register
 * - Protected application shell: /student/tickets, /tickets/new, /tickets/:id
 * - In-memory authentication state via AuthProvider
 * - Server-authoritative route and role protection
 */

import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { PublicOnlyRoute } from './components/auth/PublicOnlyRoute';
import { RoleRoute } from './components/auth/RoleRoute';
import { AppShell } from './components/layout/AppShell';
import { AuthProvider, useAuth } from './context';
import LoginPage from './pages/auth/LoginPage';
import RegisterPage from './pages/auth/RegisterPage';
import StudentTicketsPage from './pages/student/StudentTicketsPage';
import StaffQueuePage from './pages/staff/StaffQueuePage';
import CategoryManagementPage from './pages/admin/CategoryManagementPage';
import TicketCreatePage from './pages/tickets/TicketCreatePage';
import TicketDetailPage from './pages/tickets/TicketDetailPage';

// Root redirect determining initial user landing
export const RootRedirect: React.FC = () => {
  const { user, isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="min-h-screen flex items-center justify-center p-6 bg-neutral-50"
      >
        <div className="w-8 h-8 border-4 border-brand-200 border-t-brand-600 rounded-full animate-spin" />
        <span className="sr-only">Loading application...</span>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  if (user.role === 'STAFF') return <Navigate to="/staff/queue" replace />;
  if (user.role === 'ADMINISTRATOR') return <Navigate to="/admin/categories" replace />;
  return <Navigate to="/student/tickets" replace />;
};

export const AppContent: React.FC = () => {
  return (
    <Routes>
      {/* Root redirect */}
      <Route path="/" element={<RootRedirect />} />

      {/* Public Authentication Routes */}
      <Route element={<PublicOnlyRoute />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      {/* Protected Application Routes within AppShell */}
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          {/* Student Portal & Ticket Creation */}
          <Route element={<RoleRoute allowedRoles={['STUDENT', 'ADMINISTRATOR']} />}>
            <Route path="/student/tickets" element={<StudentTicketsPage />} />
            <Route path="/tickets/new" element={<TicketCreatePage />} />
          </Route>

          {/* Staff Workbench Queue */}
          <Route element={<RoleRoute allowedRoles={['STAFF']} />}>
            <Route path="/staff/queue" element={<StaffQueuePage />} />
          </Route>

          {/* Administrator Category Management Console */}
          <Route element={<RoleRoute allowedRoles={['ADMINISTRATOR']} />}>
            <Route path="/admin/categories" element={<CategoryManagementPage />} />
            <Route path="/admin/dashboard" element={<Navigate to="/admin/categories" replace />} />
          </Route>

          {/* Ticket Detail View (all authenticated roles) */}
          <Route path="/tickets/:id" element={<TicketDetailPage />} />
        </Route>
      </Route>

      {/* Fallback not-found redirect */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;
