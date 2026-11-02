/**
 * CampusFix Mobile Bottom Navigation Component
 *
 * Implements sticky mobile navigation (< 768px):
 * - Minimum 48x48px touch targets for WCAG 2.1 AA mobile compliance
 * - Role-appropriate quick navigation destinations
 */

import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import {
  BuildingOfficeIcon,
  ClipboardDocumentListIcon,
  PlusIcon,
  TicketIcon,
  WrenchScrewdriverIcon,
} from '../ui/icons';

export const MobileNav: React.FC = () => {
  const { user } = useAuth();

  if (!user) return null;

  return (
    <nav
      role="navigation"
      aria-label="Mobile Bottom Navigation"
      className="md:hidden fixed bottom-0 left-0 right-0 z-40 h-16 bg-white border-t border-neutral-200 px-2 flex items-center justify-around shadow-lg"
    >
      {user.role === 'STUDENT' && (
        <>
          <NavLink
            to="/student/tickets"
            className={({ isActive }) =>
              `flex flex-col items-center justify-center min-w-[64px] min-h-[48px] px-2 rounded text-[11px] font-medium transition-colors ${
                isActive ? 'text-brand-600' : 'text-neutral-500 hover:text-neutral-900'
              }`
            }
          >
            <TicketIcon className="w-5 h-5 mb-0.5" />
            <span>My Tickets</span>
          </NavLink>

          <NavLink
            to="/tickets/new"
            className="flex flex-col items-center justify-center min-w-[64px] min-h-[48px] px-2 rounded text-[11px] font-medium text-brand-600"
          >
            <div className="w-10 h-10 rounded-full bg-brand-600 text-white flex items-center justify-center shadow-md -mt-5">
              <PlusIcon className="w-5 h-5" />
            </div>
            <span className="mt-1">Report</span>
          </NavLink>
        </>
      )}

      {user.role === 'STAFF' && (
        <NavLink
          to="/staff/queue"
          className={({ isActive }) =>
            `flex flex-col items-center justify-center min-w-[64px] min-h-[48px] px-2 rounded text-[11px] font-medium transition-colors ${
              isActive ? 'text-brand-600' : 'text-neutral-500 hover:text-neutral-900'
            }`
          }
        >
          <WrenchScrewdriverIcon className="w-5 h-5 mb-0.5" />
          <span>Queue</span>
        </NavLink>
      )}

      {user.role === 'ADMINISTRATOR' && (
        <>
          <NavLink
            to="/admin/dashboard"
            className={({ isActive }) =>
              `flex flex-col items-center justify-center min-w-[64px] min-h-[48px] px-2 rounded text-[11px] font-medium transition-colors ${
                isActive ? 'text-brand-600' : 'text-neutral-500 hover:text-neutral-900'
              }`
            }
          >
            <ClipboardDocumentListIcon className="w-5 h-5 mb-0.5" />
            <span>Dashboard</span>
          </NavLink>

          <NavLink
            to="/admin/categories"
            className={({ isActive }) =>
              `flex flex-col items-center justify-center min-w-[64px] min-h-[48px] px-2 rounded text-[11px] font-medium transition-colors ${
                isActive ? 'text-brand-600' : 'text-neutral-500 hover:text-neutral-900'
              }`
            }
          >
            <BuildingOfficeIcon className="w-5 h-5 mb-0.5" />
            <span>Categories</span>
          </NavLink>
        </>
      )}
    </nav>
  );
};

export default MobileNav;
