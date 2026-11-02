/**
 * CampusFix SCR-01: Authentication Portal — Student Registration Page
 *
 * Implements:
 * - Student self-registration (strictly creates STUDENT role)
 * - Strict password complexity validation (min 8 chars, >=1 upper, >=1 lower, >=1 number)
 * - Accessible validation feedback and API error handling
 * - Automatic seamless login upon successful creation
 */

import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { AlertBanner } from '../../components/ui/AlertBanner';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';

export const RegisterPage: React.FC = () => {
  const { register, login } = useAuth();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState<{
    fullName?: string;
    email?: string;
    password?: string;
  }>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const validate = (): boolean => {
    const errors: { fullName?: string; email?: string; password?: string } = {};

    const cleanName = fullName.trim();
    if (!cleanName) {
      errors.fullName = 'Full name is required.';
    } else if (cleanName.length < 2) {
      errors.fullName = 'Full name must be at least 2 characters.';
    }

    const cleanEmail = email.trim();
    if (!cleanEmail) {
      errors.email = 'Institutional email is required.';
    } else if (!/^[a-zA-Z0-9_.+-]+@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$/.test(cleanEmail)) {
      errors.email = 'Please provide a valid university email address (user@domain.tld).';
    }

    if (!password) {
      errors.password = 'Password is required.';
    } else {
      const issues: string[] = [];
      if (password.length < 8) issues.push('at least 8 characters');
      if (!/[A-Z]/.test(password)) issues.push('one uppercase letter (A-Z)');
      if (!/[a-z]/.test(password)) issues.push('one lowercase letter (a-z)');
      if (!/\d/.test(password)) issues.push('one number (0-9)');

      if (issues.length > 0) {
        errors.password = `Password must contain ${issues.join(', ')}.`;
      }
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
      await register({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
      });

      // Automatically sign in the student after successful registration
      await login({
        email: email.trim(),
        password,
      });

      navigate('/student/tickets', { replace: true });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Registration failed. Please try again.';
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
            Register Student Account
          </h1>
          <p className="text-sm text-neutral-600 mt-1">
            Report and track university campus facility work orders
          </p>
        </div>

        {/* Global API Error Alert */}
        {apiError && (
          <div className="mb-4">
            <AlertBanner
              variant="error"
              title="Registration Failed"
              onDismiss={() => setApiError(null)}
            >
              {apiError}
            </AlertBanner>
          </div>
        )}

        {/* Registration Form */}
        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          <Input
            id="register-name"
            type="text"
            label="Full Name"
            placeholder="Jane Doe"
            autoComplete="name"
            required
            value={fullName}
            error={fieldErrors.fullName}
            onChange={(e) => {
              setFullName(e.target.value);
              if (fieldErrors.fullName) setFieldErrors({ ...fieldErrors, fullName: undefined });
            }}
          />

          <Input
            id="register-email"
            type="email"
            label="Institutional Email"
            placeholder="jane.doe@university.edu"
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
            id="register-password"
            type="password"
            label="Password"
            placeholder="Min 8 chars with uppercase, lowercase & digit"
            autoComplete="new-password"
            required
            value={password}
            error={fieldErrors.password}
            helperText="At least 8 characters, 1 uppercase, 1 lowercase, 1 number."
            onChange={(e) => {
              setPassword(e.target.value);
              if (fieldErrors.password) setFieldErrors({ ...fieldErrors, password: undefined });
            }}
          />

          <Button
            type="submit"
            className="w-full mt-2"
            isLoading={isSubmitting}
            loadingText="Creating account..."
          >
            Create Student Account
          </Button>
        </form>

        {/* Login Link */}
        <div className="mt-6 pt-4 border-t border-neutral-100 text-center text-xs text-neutral-600">
          <span>Already have an account? </span>
          <Link
            to="/login"
            className="font-semibold text-brand-600 hover:text-brand-700 underline underline-offset-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded"
          >
            Sign In
          </Link>
        </div>
      </div>
    </div>
  );
};

export default RegisterPage;
