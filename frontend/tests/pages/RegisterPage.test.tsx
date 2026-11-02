import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthContext, type AuthContextType } from '../../src/context/AuthContext';
import RegisterPage from '../../src/pages/auth/RegisterPage';
import type { User } from '../../src/types';

describe('SCR-01: RegisterPage', () => {
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

  const renderRegisterPage = (authContext = createMockAuth()) => {
    return render(
      <MemoryRouter initialEntries={['/register']}>
        <AuthContext.Provider value={authContext}>
          <Routes>
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/student/tickets" element={<div>Student Tickets Dashboard</div>} />
            <Route path="/login" element={<div>Login Page View</div>} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>
    );
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders registration form elements cleanly', () => {
    renderRegisterPage();

    expect(
      screen.getByRole('heading', { name: /register student account/i })
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/institutional email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /create student account/i })
    ).toBeInTheDocument();
  });

  it('validates empty inputs and blocks submission', async () => {
    const user = userEvent.setup();
    renderRegisterPage();

    await user.click(screen.getByRole('button', { name: /create student account/i }));

    expect(screen.getByText('Full name is required.')).toBeInTheDocument();
    expect(screen.getByText('Institutional email is required.')).toBeInTheDocument();
    expect(screen.getByText('Password is required.')).toBeInTheDocument();
  });

  it('enforces password complexity constraints (min 8 chars, 1 uppercase, 1 lowercase, 1 number)', async () => {
    const user = userEvent.setup();
    renderRegisterPage();

    await user.type(screen.getByLabelText(/full name/i), 'Jane Doe');
    await user.type(screen.getByLabelText(/institutional email/i), 'jane.doe@university.edu');

    // Weak password without uppercase or numbers
    await user.type(screen.getByLabelText(/password/i), 'weakpass');
    await user.click(screen.getByRole('button', { name: /create student account/i }));

    expect(
      screen.getByText(/password must contain.*uppercase.*number/i)
    ).toBeInTheDocument();
  });

  it('handles successful registration and logs the student in', async () => {
    const user = userEvent.setup();
    const mockStudent: User = {
      id: 'student-new-1',
      email: 'jane.doe@university.edu',
      full_name: 'Jane Doe',
      role: 'STUDENT',
      is_active: true,
      created_at: '2026-11-01T12:00:00Z',
    };

    const mockAuth = createMockAuth({
      register: vi.fn().mockResolvedValue(mockStudent),
      login: vi.fn().mockResolvedValue(mockStudent),
    });

    renderRegisterPage(mockAuth);

    await user.type(screen.getByLabelText(/full name/i), 'Jane Doe');
    await user.type(screen.getByLabelText(/institutional email/i), 'jane.doe@university.edu');
    await user.type(screen.getByLabelText(/password/i), 'StrongPass123!');
    await user.click(screen.getByRole('button', { name: /create student account/i }));

    expect(mockAuth.register).toHaveBeenCalledWith({
      full_name: 'Jane Doe',
      email: 'jane.doe@university.edu',
      password: 'StrongPass123!',
    });

    expect(mockAuth.login).toHaveBeenCalledWith({
      email: 'jane.doe@university.edu',
      password: 'StrongPass123!',
    });

    await waitFor(() => {
      expect(screen.getByText('Student Tickets Dashboard')).toBeInTheDocument();
    });
  });

  it('displays API error alert when email already exists', async () => {
    const user = userEvent.setup();
    const mockAuth = createMockAuth({
      register: vi
        .fn()
        .mockRejectedValue(new Error('An account with this email address already exists.')),
    });

    renderRegisterPage(mockAuth);

    await user.type(screen.getByLabelText(/full name/i), 'Jane Doe');
    await user.type(screen.getByLabelText(/institutional email/i), 'jane.doe@university.edu');
    await user.type(screen.getByLabelText(/password/i), 'StrongPass123!');
    await user.click(screen.getByRole('button', { name: /create student account/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(
        screen.getByText('An account with this email address already exists.')
      ).toBeInTheDocument();
    });
  });
});
