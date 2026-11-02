/**
 * CampusFix PaginationBar Component
 *
 * Implements accessible pagination navigation matching WCAG 2.1 AA standards.
 */

import React from 'react';
import { ChevronLeftIcon, ChevronRightIcon } from './icons';

export interface PaginationBarProps {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
  onPageChange: (newPage: number) => void;
  className?: string;
}

export const PaginationBar: React.FC<PaginationBarProps> = ({
  page,
  pageSize,
  total,
  totalPages,
  onPageChange,
  className = '',
}) => {
  const startItem = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, total);

  const canGoPrevious = page > 1;
  const canGoNext = page < totalPages;

  return (
    <nav
      role="navigation"
      aria-label="Pagination Navigation"
      className={`flex flex-col sm:flex-row items-center justify-between gap-4 border-t border-neutral-200 px-4 py-3 bg-white ${className}`}
    >
      <div className="text-xs text-neutral-600 font-normal">
        Showing <span className="font-semibold text-neutral-900">{startItem}</span> to{' '}
        <span className="font-semibold text-neutral-900">{endItem}</span> of{' '}
        <span className="font-semibold text-neutral-900">{total}</span> entries
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={!canGoPrevious}
          aria-label="Previous page"
          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md border border-neutral-300 text-xs font-medium text-neutral-700 bg-white hover:bg-neutral-50 active:bg-neutral-100 disabled:bg-neutral-100 disabled:text-neutral-400 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 transition-colors"
        >
          <ChevronLeftIcon className="w-3.5 h-3.5" />
          <span>Previous</span>
        </button>

        <span className="text-xs font-medium text-neutral-700 px-2">
          Page {page} of {Math.max(totalPages, 1)}
        </span>

        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={!canGoNext}
          aria-label="Next page"
          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md border border-neutral-300 text-xs font-medium text-neutral-700 bg-white hover:bg-neutral-50 active:bg-neutral-100 disabled:bg-neutral-100 disabled:text-neutral-400 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 transition-colors"
        >
          <span>Next</span>
          <ChevronRightIcon className="w-3.5 h-3.5" />
        </button>
      </div>
    </nav>
  );
};

export default PaginationBar;
