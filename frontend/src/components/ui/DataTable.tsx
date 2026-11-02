/**
 * CampusFix Responsive DataTable Component
 *
 * Implements:
 * - Semantic <table>, <thead>, <tbody> markup on desktop
 * - Responsive stacked card transformation for mobile viewports (< 768px)
 * - Accessible loading skeletons and empty states
 */

import React from 'react';
import { EmptyState } from './EmptyState';
import { Skeleton } from './Skeleton';

export interface Column<T> {
  id: string;
  header: string;
  accessor?: keyof T;
  render?: (row: T) => React.ReactNode;
  className?: string;
  headerClassName?: string;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyField: keyof T | ((row: T) => string);
  isLoading?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: React.ReactNode;
  className?: string;
  onRowClick?: (row: T) => void;
}

export function DataTable<T>({
  columns,
  data,
  keyField,
  isLoading = false,
  emptyTitle = 'No records found',
  emptyDescription = 'There are no items to display at this time.',
  emptyAction,
  className = '',
  onRowClick,
}: DataTableProps<T>) {
  const getRowKey = (row: T, index: number): string => {
    if (typeof keyField === 'function') {
      return keyField(row);
    }
    const val = row[keyField];
    return val !== undefined && val !== null ? String(val) : `row-${index}`;
  };

  if (isLoading) {
    return (
      <div className={`w-full overflow-hidden rounded-lg border border-neutral-200 bg-white ${className}`}>
        <div className="hidden md:block">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-neutral-50 border-b border-neutral-200">
                {columns.map((col) => (
                  <th
                    key={col.id}
                    className={`px-4 py-3 text-xs font-semibold uppercase tracking-wider text-neutral-600 ${
                      col.headerClassName || ''
                    }`}
                  >
                    {col.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 4 }).map((_, idx) => (
                <tr key={idx} className="border-b border-neutral-100">
                  {columns.map((col) => (
                    <td key={col.id} className="px-4 py-3.5">
                      <Skeleton variant="text" width={col.id === 'title' ? '80%' : '60%'} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="md:hidden p-4 space-y-4">
          <Skeleton variant="card" count={3} />
        </div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className={`w-full rounded-lg border border-neutral-200 bg-white ${className}`}>
        <EmptyState
          title={emptyTitle}
          description={emptyDescription}
          action={emptyAction}
        />
      </div>
    );
  }

  return (
    <div className={`w-full overflow-hidden rounded-lg border border-neutral-200 bg-white ${className}`}>
      {/* Desktop Table View (>= 768px) */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-neutral-50 border-b border-neutral-200 text-xs font-semibold uppercase tracking-wider text-neutral-600">
              {columns.map((col) => (
                <th
                  key={col.id}
                  scope="col"
                  className={`px-4 py-3 ${col.headerClassName || ''}`}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100 text-sm">
            {data.map((row, index) => {
              const key = getRowKey(row, index);
              const isClickable = Boolean(onRowClick);

              return (
                <tr
                  key={key}
                  onClick={() => onRowClick?.(row)}
                  tabIndex={isClickable ? 0 : undefined}
                  onKeyDown={(e) => {
                    if (isClickable && (e.key === 'Enter' || e.key === ' ')) {
                      e.preventDefault();
                      onRowClick?.(row);
                    }
                  }}
                  className={`transition-colors ${
                    isClickable
                      ? 'cursor-pointer hover:bg-neutral-50/80 focus:outline-none focus-visible:bg-brand-50'
                      : 'hover:bg-neutral-50/50'
                  }`}
                >
                  {columns.map((col) => {
                    const content = col.render
                      ? col.render(row)
                      : col.accessor
                      ? String(row[col.accessor] ?? '')
                      : null;

                    return (
                      <td
                        key={col.id}
                        className={`px-4 py-3.5 text-neutral-800 ${col.className || ''}`}
                      >
                        {content}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile Card List View (< 768px) */}
      <div className="md:hidden divide-y divide-neutral-200">
        {data.map((row, index) => {
          const key = getRowKey(row, index);
          const isClickable = Boolean(onRowClick);

          return (
            <div
              key={key}
              onClick={() => onRowClick?.(row)}
              tabIndex={isClickable ? 0 : undefined}
              onKeyDown={(e) => {
                if (isClickable && (e.key === 'Enter' || e.key === ' ')) {
                  e.preventDefault();
                  onRowClick?.(row);
                }
              }}
              className={`p-4 space-y-2 text-sm ${
                isClickable
                  ? 'cursor-pointer active:bg-neutral-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500'
                  : ''
              }`}
            >
              {columns.map((col) => {
                const content = col.render
                  ? col.render(row)
                  : col.accessor
                  ? String(row[col.accessor] ?? '')
                  : null;

                return (
                  <div key={col.id} className="flex items-start justify-between gap-2">
                    <span className="text-xs font-semibold text-neutral-500 uppercase tracking-wider shrink-0">
                      {col.header}
                    </span>
                    <div className="text-right text-neutral-800 font-medium">
                      {content}
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default DataTable;
