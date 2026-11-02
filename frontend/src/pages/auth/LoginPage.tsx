/**
 * CampusFix SCR-01: Authentication Portal — Login Page
 *
 * Implements:
 * - Email and password credentials submission
 * - Accessible validation and API error alert banner
 * - In-memory access token storage via AuthContext
 * - Automatic role-based redirect upon successful authentication
 */

import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { AlertBanner } from '../../components/ui/AlertBanner';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const validate = (): boolean => {
    const errors: { email?: string; password?: string } = {};

    const cleanEmail = email.trim();
    if (!cleanEmail) {
      errors.email = 'Email address is required.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail)) {
      errors.email = 'Please enter a valid email address (e.g. user@university.edu).';
    }

    if (!password) {
      errors.password = 'Password is required.';
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setApiError(null);

    if (!validate()) {
      return;
    }

    setIsSubmitting(true);
    try {
      const user = await login({ email: email.trim(), password });

      // Determine redirect destination
      const fromPath = (location.state as { from?: { pathname?: string } })?.from?.pathname;
      if (fromPath && fromPath !== '/login' && fromPath !== '/register') {
        navigate(fromPath, { replace: true });
        return;
      }

      let home = '/student/tickets';
      if (user.role === 'STAFF') home = '/staff/queue';
      if (user.role === 'ADMINISTRATOR') home = '/admin/dashboard';
      navigate(home, { replace: true });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Invalid email or password.';
      setApiError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 sm:p-6 bg-neutral-50">
      <div className="max-w-md w-full bg-white border border-neutral-200 rounded-lg p-6 sm:p-8 shadow-sm">
        {/* Monogram Branding */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-brand-600 text-white font-bold text-xl mb-3 shadow-xs">
            CF
          </div>
          <h1 className="text-2xl font-bold text-neutral-900 tracking-tight">
            Sign in to CampusFix
          </h1>
          <p className="text-sm text-neutral-600 mt-1">
            University Facility Issue Reporting & Triage Platform
          </p>
        </div>

        {/* Global API Error Alert */}
        {apiError && (
          <div className="mb-4">
            <AlertBanner
              variant="error"
              title="Authentication Failed"
              onDismiss={() => setApiError(null)}
            >
              {apiError}
            </AlertBanner>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          <Input
            id="login-email"
            type="email"
            label="Institutional Email"
            placeholder="student@university.edu"
            autoComplete="email"
            required
            value={email}
            error={fieldErrors.email}
            onChange={(e) => {
              setEmail(e.target.value);
              if (fieldErrors.email) setFieldErrors({ ...fieldErrors, email: undefined });
            }}
          />

          <Input
            id="login-password"
            type="password"
            label="Password"
            placeholder="••••••••"
            autoComplete="current-password"
            required
            value={password}
            error={fieldErrors.password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (fieldErrors.password) setFieldErrors({ ...fieldErrors, password: undefined });
            }}
          />

          <Button
            type="submit"
            className="w-full mt-2"
            isLoading={isSubmitting}
            loadingText="Signing in..."
          >
            Sign In
          </Button>
        </form>

        {/* Register CTA Link */}
        <div className="mt-6 pt-4 border-t border-neutral-100 text-center text-xs text-neutral-600">
          <span>New student reporting an issue? </span>
          <Link
            to="/register"
            className="font-semibold text-brand-600 hover:text-brand-700 underline underline-offset-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded"
          >
            Register Student Account
          </Link>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
