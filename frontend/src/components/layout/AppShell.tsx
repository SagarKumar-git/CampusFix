/**
 * CampusFix AppShell Layout Component
 *
 * Provides the unified multi-tier layout:
 * - Fixed Topbar with role badge and user dropdown
 * - Responsive desktop Sidebar
 * - Mobile bottom navigation bar
 * - Accessible skip-to-content landmark link
 */

import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { MobileNav } from './MobileNav';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

export interface AppShellProps {
  children?: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  return (
    <div className="min-h-screen bg-neutral-50 flex flex-col font-sans text-neutral-800">
      {/* Accessible skip link */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-brand-600 focus:text-white focus:rounded-md focus:shadow-md"
      >
        Skip to main content
      </a>

      {/* Top Header */}
      <Topbar
        isMobileMenuOpen={isMobileMenuOpen}
        onToggleMobileMenu={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
      />

      {/* Main Container */}
      <div className="flex-1 flex max-w-7xl w-full mx-auto">
        {/* Desktop Sidebar */}
        <Sidebar />

        {/* Dynamic Page Content */}
        <main
          id="main-content"
          tabIndex={-1}
          className="flex-1 p-4 sm:p-6 lg:p-8 pb-24 md:pb-8 outline-none overflow-x-hidden"
        >
          {children || <Outlet />}
        </main>
      </div>

      {/* Mobile Sticky Bottom Navigation */}
      <MobileNav />
    </div>
  );
};

export default AppShell;
