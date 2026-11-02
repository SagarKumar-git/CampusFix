/**
 * CampusFix Sidebar Navigation Component
 *
 * Implements role-segregated desktop navigation:
 * - Student: My Tickets, Report Issue
 * - Staff: Workbench Queue
 * - Admin: Operations Overview, Facility Categories, User Directory
 */

import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import {
  BuildingOfficeIcon,
  ClipboardDocumentListIcon,
  PlusIcon,
  TicketIcon,
  UserIcon,
  WrenchScrewdriverIcon,
} from '../ui/icons';

export interface NavItem {
  label: string;
  path: string;
  icon: React.ReactNode;
}

export const Sidebar: React.FC = () => {
  const { user } = useAuth();

  if (!user) return null;

  const getNavItems = (): NavItem[] => {
    switch (user.role) {
      case 'STUDENT':
        return [
          {
            label: 'My Tickets',
            path: '/student/tickets',
            icon: <TicketIcon className="w-5 h-5" />,
          },
          {
            label: 'Report New Issue',
            path: '/tickets/new',
            icon: <PlusIcon className="w-5 h-5" />,
          },
        ];

      case 'STAFF':
        return [
          {
            label: 'Workbench Queue',
            path: '/staff/queue',
            icon: <WrenchScrewdriverIcon className="w-5 h-5" />,
          },
        ];

      case 'ADMINISTRATOR':
        return [
          {
            label: 'Operations Overview',
            path: '/admin/dashboard',
            icon: <ClipboardDocumentListIcon className="w-5 h-5" />,
          },
          {
            label: 'Facility Categories',
            path: '/admin/categories',
            icon: <BuildingOfficeIcon className="w-5 h-5" />,
          },
          {
            label: 'User Directory',
            path: '/admin/users',
            icon: <UserIcon className="w-5 h-5" />,
          },
        ];

      default:
        return [];
    }
  };

  const navItems = getNavItems();

  return (
    <aside
      aria-label="Sidebar Navigation"
      className="hidden md:flex flex-col w-64 border-r border-neutral-200 bg-white min-h-[calc(100vh-4rem)] p-4 space-y-6 shrink-0"
    >
      <div>
        <p className="px-3 text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-2">
          Workspace
        </p>
        <nav className="space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
                  isActive
                    ? 'bg-brand-50 text-brand-700 font-semibold shadow-2xs'
                    : 'text-neutral-600 hover:text-neutral-900 hover:bg-neutral-50'
                }`
              }
            >
              {item.icon}
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </div>
    </aside>
  );
};

export default Sidebar;
