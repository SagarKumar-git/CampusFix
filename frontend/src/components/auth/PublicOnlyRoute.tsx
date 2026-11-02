/**
 * PublicOnlyRoute Component
 *
 * For routes such as /login and /register.
 * If the user is already authenticated, redirects them automatically to their role home:
 * - STUDENT -> /student/tickets
 * - STAFF -> /staff/queue
 * - ADMINISTRATOR -> /admin/dashboard
 */

import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

export interface PublicOnlyRouteProps {
  children?: React.ReactNode;
}

export const PublicOnlyRoute: React.FC<PublicOnlyRouteProps> = ({ children }) => {
  const { user, isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="min-h-screen flex flex-col items-center justify-center p-6 bg-neutral-50"
      >
        <div className="w-8 h-8 border-4 border-brand-200 border-t-brand-600 rounded-full animate-spin mb-4" />
        <p className="text-sm font-medium text-neutral-600">Loading...</p>
      </div>
    );
  }

  if (isAuthenticated && user) {
    let target = '/student/tickets';
    if (user.role === 'STAFF') target = '/staff/queue';
    if (user.role === 'ADMINISTRATOR') target = '/admin/dashboard';

    return <Navigate to={target} replace />;
  }

  return children ? <>{children}</> : <Outlet />;
};

export default PublicOnlyRoute;
