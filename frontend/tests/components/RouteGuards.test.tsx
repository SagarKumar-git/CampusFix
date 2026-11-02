import { render, screen } from '@testing-library/react';
import React from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { ProtectedRoute } from '../../src/components/auth/ProtectedRoute';
import { PublicOnlyRoute } from '../../src/components/auth/PublicOnlyRoute';
import { RoleRoute } from '../../src/components/auth/RoleRoute';
import { AuthContext, type AuthContextType } from '../../src/context/AuthContext';
import type { User } from '../../src/types';

describe('Route Guard Components', () => {
  const createMockAuthContext = (overrides?: Partial<AuthContextType>): AuthContextType => ({
    user: null,
    accessToken: null,
    isLoading: false,
    isAuthenticated: false,
    login: async () => ({} as User),
    register: async () => ({} as User),
    logout: async () => {},
    refreshSession: async () => false,
    ...overrides,
  });

  const renderWithRouter = (ui: React.ReactElement, initialEntries = ['/']) => {
    return render(
      <MemoryRouter initialEntries={initialEntries}>
        {ui}
      </MemoryRouter>
    );
  };

  describe('ProtectedRoute', () => {
    it('renders accessible loading indicator while auth is loading', () => {
      const mockAuth = createMockAuthContext({ isLoading: true });

      renderWithRouter(
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route element={<ProtectedRoute />}>
              <Route path="/" element={<div>Protected Content</div>} />
            </Route>
          </Routes>
        </AuthContext.Provider>
      );

      expect(screen.getByRole('status')).toBeInTheDocument();
      expect(screen.getByText(/verifying session/i)).toBeInTheDocument();
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });

    it('redirects unauthenticated users to /login', () => {
      const mockAuth = createMockAuthContext({ isAuthenticated: false, isLoading: false });

      renderWithRouter(
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route element={<ProtectedRoute />}>
              <Route path="/student/tickets" element={<div>Protected Student Content</div>} />
            </Route>
            <Route path="/login" element={<div>Login Page View</div>} />
          </Routes>
        </AuthContext.Provider>,
        ['/student/tickets']
      );

      expect(screen.getByText('Login Page View')).toBeInTheDocument();
      expect(screen.queryByText('Protected Student Content')).not.toBeInTheDocument();
    });

    it('renders protected content when authenticated', () => {
      const mockAuth = createMockAuthContext({
        isAuthenticated: true,
        isLoading: false,
        user: {
          id: 'user-1',
          email: 'student@university.edu',
          full_name: 'Student Name',
          role: 'STUDENT',
          is_active: true,
          created_at: '2026-11-01T00:00:00Z',
        },
      });

      renderWithRouter(
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route element={<ProtectedRoute />}>
              <Route path="/student/tickets" element={<div>Protected Student Content</div>} />
            </Route>
          </Routes>
        </AuthContext.Provider>,
        ['/student/tickets']
      );

      expect(screen.getByText('Protected Student Content')).toBeInTheDocument();
    });
  });

  describe('RoleRoute', () => {
    it('allows access when user possesses an authorized role', () => {
      const mockAuth = createMockAuthContext({
        isAuthenticated: true,
        isLoading: false,
        user: {
          id: 'staff-1',
          email: 'tech@university.edu',
          full_name: 'Staff Tech',
          role: 'STAFF',
          is_active: true,
          created_at: '2026-11-01T00:00:00Z',
        },
      });

      renderWithRouter(
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route element={<RoleRoute allowedRoles={['STAFF', 'ADMINISTRATOR']} />}>
              <Route path="/staff/queue" element={<div>Staff Queue Workbench</div>} />
            </Route>
          </Routes>
        </AuthContext.Provider>,
        ['/staff/queue']
      );

      expect(screen.getByText('Staff Queue Workbench')).toBeInTheDocument();
    });

    it('renders accessible 403 alert when user lacks authorized role', () => {
      const mockAuth = createMockAuthContext({
        isAuthenticated: true,
        isLoading: false,
        user: {
          id: 'student-1',
          email: 'student@university.edu',
          full_name: 'Student User',
          role: 'STUDENT',
          is_active: true,
          created_at: '2026-11-01T00:00:00Z',
        },
      });

      renderWithRouter(
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route element={<RoleRoute allowedRoles={['STAFF', 'ADMINISTRATOR']} />}>
              <Route path="/staff/queue" element={<div>Staff Queue Workbench</div>} />
            </Route>
          </Routes>
        </AuthContext.Provider>,
        ['/staff/queue']
      );

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Access Restricted')).toBeInTheDocument();
      expect(
        screen.getByText(/Your account \(STUDENT\) is not authorized/i)
      ).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /return to dashboard/i })).toHaveAttribute(
        'href',
        '/student/tickets'
      );
      expect(screen.queryByText('Staff Queue Workbench')).not.toBeInTheDocument();
    });
  });

  describe('PublicOnlyRoute', () => {
    it('renders public content for unauthenticated users', () => {
      const mockAuth = createMockAuthContext({ isAuthenticated: false, isLoading: false });

      renderWithRouter(
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route element={<PublicOnlyRoute />}>
              <Route path="/login" element={<div>Public Login Page</div>} />
            </Route>
          </Routes>
        </AuthContext.Provider>,
        ['/login']
      );

      expect(screen.getByText('Public Login Page')).toBeInTheDocument();
    });

    it('redirects authenticated student to /student/tickets', () => {
      const mockAuth = createMockAuthContext({
        isAuthenticated: true,
        isLoading: false,
        user: {
          id: 'student-1',
          email: 'student@university.edu',
          full_name: 'Student User',
          role: 'STUDENT',
          is_active: true,
          created_at: '2026-11-01T00:00:00Z',
        },
      });

      renderWithRouter(
        <AuthContext.Provider value={mockAuth}>
          <Routes>
            <Route element={<PublicOnlyRoute />}>
              <Route path="/login" element={<div>Public Login Page</div>} />
            </Route>
            <Route path="/student/tickets" element={<div>Student Portal View</div>} />
          </Routes>
        </AuthContext.Provider>,
        ['/login']
      );

      expect(screen.getByText('Student Portal View')).toBeInTheDocument();
      expect(screen.queryByText('Public Login Page')).not.toBeInTheDocument();
    });
  });
});
