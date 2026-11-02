import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { AppShell } from '../../src/components/layout/AppShell';
import { MobileNav } from '../../src/components/layout/MobileNav';
import { Sidebar } from '../../src/components/layout/Sidebar';
import { Topbar } from '../../src/components/layout/Topbar';
import { AuthContext, type AuthContextType } from '../../src/context/AuthContext';
import type { User } from '../../src/types';

describe('Navigation Layout Components', () => {
  const createMockAuth = (user: User | null): AuthContextType => ({
    user,
    accessToken: user ? 'mock-token' : null,
    isLoading: false,
    isAuthenticated: Boolean(user),
    login: async () => ({} as User),
    register: async () => ({} as User),
    logout: vi.fn(),
    refreshSession: async () => false,
  });

  const studentUser: User = {
    id: 'student-1',
    email: 'student@university.edu',
    full_name: 'Jane Student',
    role: 'STUDENT',
    is_active: true,
    created_at: '2026-11-01T00:00:00Z',
  };

  const staffUser: User = {
    id: 'staff-1',
    email: 'tech@university.edu',
    full_name: 'Alex Technician',
    role: 'STAFF',
    is_active: true,
    created_at: '2026-11-01T00:00:00Z',
  };

  const adminUser: User = {
    id: 'admin-1',
    email: 'admin@university.edu',
    full_name: 'Admin Director',
    role: 'ADMINISTRATOR',
    is_active: true,
    created_at: '2026-11-01T00:00:00Z',
  };

  describe('Topbar', () => {
    it('renders brand monogram, title, and sign in button when unauthenticated', () => {
      render(
        <MemoryRouter>
          <AuthContext.Provider value={createMockAuth(null)}>
            <Topbar />
          </AuthContext.Provider>
        </MemoryRouter>
      );

      expect(screen.getByText('CampusFix')).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /sign in/i })).toBeInTheDocument();
    });

    it('renders role badge, report CTA, and user menu for authenticated student', async () => {
      const user = userEvent.setup();
      const mockAuth = createMockAuth(studentUser);

      render(
        <MemoryRouter>
          <AuthContext.Provider value={mockAuth}>
            <Topbar />
          </AuthContext.Provider>
        </MemoryRouter>
      );

      expect(screen.getByText('Student')).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /report issue/i })).toBeInTheDocument();

      // Open profile menu
      const profileBtn = screen.getByRole('button', {
        name: /user profile menu for jane student/i,
      });
      await user.click(profileBtn);

      expect(screen.getByText('student@university.edu')).toBeInTheDocument();
      const signOutBtn = screen.getByRole('menuitem', { name: /sign out/i });
      expect(signOutBtn).toBeInTheDocument();

      await user.click(signOutBtn);
      expect(mockAuth.logout).toHaveBeenCalled();
    });
  });

  describe('Sidebar', () => {
    it('renders student navigation items for STUDENT role', () => {
      render(
        <MemoryRouter>
          <AuthContext.Provider value={createMockAuth(studentUser)}>
            <Sidebar />
          </AuthContext.Provider>
        </MemoryRouter>
      );

      expect(screen.getByRole('link', { name: /my tickets/i })).toHaveAttribute(
        'href',
        '/student/tickets'
      );
      expect(
        screen.getByRole('link', { name: /report new issue/i })
      ).toHaveAttribute('href', '/tickets/new');
    });

    it('renders staff workbench queue for STAFF role', () => {
      render(
        <MemoryRouter>
          <AuthContext.Provider value={createMockAuth(staffUser)}>
            <Sidebar />
          </AuthContext.Provider>
        </MemoryRouter>
      );

      expect(
        screen.getByRole('link', { name: /workbench queue/i })
      ).toHaveAttribute('href', '/staff/queue');
    });

    it('renders administrative links for ADMINISTRATOR role', () => {
      render(
        <MemoryRouter>
          <AuthContext.Provider value={createMockAuth(adminUser)}>
            <Sidebar />
          </AuthContext.Provider>
        </MemoryRouter>
      );

      expect(
        screen.getByRole('link', { name: /operations overview/i })
      ).toHaveAttribute('href', '/admin/dashboard');
      expect(
        screen.getByRole('link', { name: /facility categories/i })
      ).toHaveAttribute('href', '/admin/categories');
      expect(
        screen.getByRole('link', { name: /user directory/i })
      ).toHaveAttribute('href', '/admin/users');
    });
  });

  describe('MobileNav', () => {
    it('renders mobile navigation links with accessible touch targets', () => {
      render(
        <MemoryRouter>
          <AuthContext.Provider value={createMockAuth(studentUser)}>
            <MobileNav />
          </AuthContext.Provider>
        </MemoryRouter>
      );

      const nav = screen.getByRole('navigation', {
        name: /mobile bottom navigation/i,
      });
      expect(nav).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /my tickets/i })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /report/i })).toBeInTheDocument();
    });
  });

  describe('AppShell', () => {
    it('renders accessible skip-to-content landmark link and main content area', () => {
      render(
        <MemoryRouter>
          <AuthContext.Provider value={createMockAuth(studentUser)}>
            <AppShell>
              <div>Dashboard Page Content</div>
            </AppShell>
          </AuthContext.Provider>
        </MemoryRouter>
      );

      expect(
        screen.getByRole('link', { name: /skip to main content/i })
      ).toHaveAttribute('href', '#main-content');
      expect(screen.getByText('Dashboard Page Content')).toBeInTheDocument();
    });
  });
});
