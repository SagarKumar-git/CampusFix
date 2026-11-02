import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthContext, type AuthContextType } from '../../src/context/AuthContext';
import LoginPage from '../../src/pages/auth/LoginPage';
import type { User } from '../../src/types';

describe('SCR-01: LoginPage', () => {
  const createMockAuth = (overrides?: Partial<AuthContextType>): AuthContextType => ({
    user: null,
    accessToken: null,
    isLoading: false,
    isAuthenticated: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshSession: vi.fn(),
    ...overrides,
  });

  const renderLoginPage = (authContext = createMockAuth(), initialEntry = '/login') => {
    return render(
      <MemoryRouter initialEntries={[initialEntry]}>
        <AuthContext.Provider value={authContext}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/student/tickets" element={<div>Student Tickets Page</div>} />
            <Route path="/staff/queue" element={<div>Staff Queue Page</div>} />
            <Route path="/admin/dashboard" element={<div>Admin Dashboard Page</div>} />
            <Route path="/register" element={<div>Register Page View</div>} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    );
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders login form elements cleanly', () => {
    renderLoginPage();

    expect(screen.getByRole('heading', { name: /sign in to campusfix/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/institutional email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /register student account/i })).toBeInTheDocument();
  });

  it('displays client-side validation errors when submitting empty form', async () => {
    const user = userEvent.setup();
    renderLoginPage();

    await user.click(screen.getByRole('button', { name: /sign in/i }));

    expect(screen.getByText('Email address is required.')).toBeInTheDocument();
    expect(screen.getByText('Password is required.')).toBeInTheDocument();
  });

  it('validates email format before submission', async () => {
    const user = userEvent.setup();
    renderLoginPage();

    await user.type(screen.getByLabelText(/institutional email/i), 'invalid-email');
    await user.type(screen.getByLabelText(/password/i), 'Password123');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    expect(screen.getByText(/please enter a valid email address/i)).toBeInTheDocument();
  });

  it('displays error banner when authentication API rejects credentials', async () => {
    const user = userEvent.setup();
    const mockAuth = createMockAuth({
      login: vi.fn().mockRejectedValue(new Error('Invalid email or password.')),
    });

    renderLoginPage(mockAuth);

    await user.type(screen.getByLabelText(/institutional email/i), 'student@university.edu');
    await user.type(screen.getByLabelText(/password/i), 'WrongPassword123');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Invalid email or password.')).toBeInTheDocument();
    });
  });

  it('redirects student to /student/tickets upon successful authentication', async () => {
    const user = userEvent.setup();
    const studentUser: User = {
      id: 'student-1',
      email: 'student@university.edu',
      full_name: 'Student Name',
      role: 'STUDENT',
      is_active: true,
      created_at: '2026-11-01T00:00:00Z',
    };

    const mockAuth = createMockAuth({
      login: vi.fn().mockResolvedValue(studentUser),
    });

    renderLoginPage(mockAuth);

    await user.type(screen.getByLabelText(/institutional email/i), 'student@university.edu');
    await user.type(screen.getByLabelText(/password/i), 'Password123');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText('Student Tickets Page')).toBeInTheDocument();
    });
  });

  it('redirects staff to /staff/queue upon successful authentication', async () => {
    const user = userEvent.setup();
    const staffUser: User = {
      id: 'staff-1',
      email: 'tech@university.edu',
      full_name: 'Staff Tech',
      role: 'STAFF',
      is_active: true,
      created_at: '2026-11-01T00:00:00Z',
    };

    const mockAuth = createMockAuth({
      login: vi.fn().mockResolvedValue(staffUser),
    });

    renderLoginPage(mockAuth);

    await user.type(screen.getByLabelText(/institutional email/i), 'tech@university.edu');
    await user.type(screen.getByLabelText(/password/i), 'Password123');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText('Staff Queue Page')).toBeInTheDocument();
    });
  });
});
