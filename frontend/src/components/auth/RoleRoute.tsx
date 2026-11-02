/**
 * RoleRoute Component
 *
 * Enforces role-based route access on the client presentation layer.
 * Authoritative role verification is always strictly enforced on backend endpoints.
 *
 * If authenticated user does not have an allowed role, renders a high-contrast
 * accessible 403 Forbidden alert with role guidance.
 */

import React from 'react';
import { Link, Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import type { UserRole } from '../../types';

export interface RoleRouteProps {
  allowedRoles: UserRole[];
  children?: React.ReactNode;
}

export const RoleRoute: React.FC<RoleRouteProps> = ({ allowedRoles, children }) => {
  const { user, isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="min-h-screen flex flex-col items-center justify-center p-6 bg-neutral-50"
      >
        <div className="w-8 h-8 border-4 border-brand-200 border-t-brand-600 rounded-full animate-spin mb-4" />
        <p className="text-sm font-medium text-neutral-600">Checking permissions...</p>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!allowedRoles.includes(user.role)) {
    // Determine user's authorized home path
    let homePath = '/student/tickets';
    if (user.role === 'STAFF') homePath = '/staff/queue';
    if (user.role === 'ADMINISTRATOR') homePath = '/admin/dashboard';

    return (
      <main className="min-h-screen flex items-center justify-center p-6 bg-neutral-50">
        <div
          role="alert"
          className="max-w-md w-full bg-white border border-neutral-200 rounded-lg p-6 shadow-sm text-center"
        >
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-red-50 text-red-600 mb-4">
            <svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <h1 className="text-xl font-bold text-neutral-900 mb-2">Access Restricted</h1>
          <p className="text-sm text-neutral-600 mb-6">
            Your account ({user.role}) is not authorized to access this section.
          </p>
          <Link
            to={homePath}
            className="inline-flex items-center justify-center px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-md hover:bg-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-500"
          >
            Return to Dashboard
          </Link>
        </div>
      </main>
    );
  }

  return children ? <>{children}</> : <Outlet />;
};

export default RoleRoute;
