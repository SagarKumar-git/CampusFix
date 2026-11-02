/**
 * CampusFix Topbar Component
 *
 * Implements 64px application header:
 * - Brand logo & high-contrast monogram
 * - Current user role badge
 * - Quick action primary button
 * - User profile menu with accessible logout trigger
 */

import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { RoleBadge } from '../ui/Badge';
import {
  ArrowLeftOnRectangleIcon,
  Bars3Icon,
  ChevronDownIcon,
  PlusIcon,
  UserIcon,
  XMarkIcon,
} from '../ui/icons';

export interface TopbarProps {
  onToggleMobileMenu?: () => void;
  isMobileMenuOpen?: boolean;
}

export const Topbar: React.FC<TopbarProps> = ({
  onToggleMobileMenu,
  isMobileMenuOpen = false,
}) => {
  const { user, logout, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  const handleLogout = async () => {
    setIsProfileOpen(false);
    await logout();
    navigate('/login');
  };

  return (
    <header className="sticky top-0 z-40 h-16 bg-white border-b border-neutral-200 shadow-xs">
      <div className="h-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between">
        {/* Left: Mobile Toggle & Brand Logo */}
        <div className="flex items-center gap-3">
          {isAuthenticated && onToggleMobileMenu && (
            <button
              type="button"
              onClick={onToggleMobileMenu}
              aria-label={isMobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
              aria-expanded={isMobileMenuOpen}
              className="md:hidden p-2 rounded-md text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            >
              {isMobileMenuOpen ? (
                <XMarkIcon className="w-6 h-6" />
              ) : (
                <Bars3Icon className="w-6 h-6" />
              )}
            </button>
          )}

          <Link
            to="/"
            className="flex items-center gap-2.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded-md p-1"
          >
            <div className="w-9 h-9 rounded-lg bg-brand-600 text-white flex items-center justify-center font-bold text-base shadow-xs" aria-hidden="true">
              CF
            </div>
            <span className="font-bold text-lg text-neutral-900 tracking-tight">
              CampusFix
            </span>
          </Link>

          {user && (
            <div className="hidden sm:block ml-2">
              <RoleBadge role={user.role} />
            </div>
          )}
        </div>

        {/* Right: Actions & User Menu */}
        <div className="flex items-center gap-3">
          {/* Quick Action CTA (Role specific) */}
          {user?.role === 'STUDENT' && (
            <Link
              to="/tickets/new"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-brand-600 text-white text-xs sm:text-sm font-medium rounded-md hover:bg-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-500 shadow-xs transition-colors min-h-[36px]"
            >
              <PlusIcon className="w-4 h-4" />
              <span>Report Issue</span>
            </Link>
          )}

          {user?.role === 'ADMINISTRATOR' && (
            <Link
              to="/admin/categories"
              className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 bg-brand-600 text-white text-xs sm:text-sm font-medium rounded-md hover:bg-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-500 shadow-xs transition-colors min-h-[36px]"
            >
              <PlusIcon className="w-4 h-4" />
              <span>Categories</span>
            </Link>
          )}

          {/* User Profile Dropdown */}
          {isAuthenticated && user ? (
            <div className="relative">
              <button
                type="button"
                onClick={() => setIsProfileOpen(!isProfileOpen)}
                aria-expanded={isProfileOpen}
                aria-haspopup="menu"
                aria-label={`User profile menu for ${user.full_name}`}
                className="flex items-center gap-2 p-1.5 rounded-full hover:bg-neutral-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 transition-colors"
              >
                <div className="w-8 h-8 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center font-semibold text-xs border border-brand-200">
                  {user.full_name.slice(0, 2).toUpperCase()}
                </div>
                <span className="hidden md:block text-xs font-medium text-neutral-700 max-w-[120px] truncate">
                  {user.full_name}
                </span>
                <ChevronDownIcon className="hidden md:block w-3.5 h-3.5 text-neutral-500" />
              </button>

              {isProfileOpen && (
                <>
                  <div
                    className="fixed inset-0 z-10"
                    onClick={() => setIsProfileOpen(false)}
                    aria-hidden="true"
                  />
                  <div
                    role="menu"
                    aria-label="User account actions"
                    className="absolute right-0 mt-2 w-56 rounded-md bg-white shadow-lg border border-neutral-200 py-1 z-20 focus:outline-none"
                  >
                    <div className="px-4 py-3 border-b border-neutral-100">
                      <p className="text-xs font-semibold text-neutral-900 truncate">
                        {user.full_name}
                      </p>
                      <p className="text-xs text-neutral-500 truncate">{user.email}</p>
                      <div className="mt-1.5 sm:hidden">
                        <RoleBadge role={user.role} />
                      </div>
                    </div>

                    <button
                      type="button"
                      role="menuitem"
                      onClick={handleLogout}
                      className="w-full text-left px-4 py-2.5 text-xs text-red-600 hover:bg-red-50 flex items-center gap-2 transition-colors focus:outline-none focus-visible:bg-red-50"
                    >
                      <ArrowLeftOnRectangleIcon className="w-4 h-4" />
                      <span>Sign Out</span>
                    </button>
                  </div>
                </>
              )}
            </div>
          ) : (
            <Link
              to="/login"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-neutral-300 text-xs sm:text-sm font-medium text-neutral-700 rounded-md hover:bg-neutral-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            >
              <UserIcon className="w-4 h-4" />
              <span>Sign In</span>
            </Link>
          )}
        </div>
      </div>
    </header>
  );
};

export default Topbar;
