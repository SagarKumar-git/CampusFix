/**
 * CampusFix Skeleton Placeholder Component
 *
 * Implements layout-preserving loading placeholders with aria-hidden="true"
 * and accessible role="status" announcements.
 */

import React from 'react';

export type SkeletonVariant = 'text' | 'circle' | 'rect' | 'card' | 'table-row';

export interface SkeletonProps {
  variant?: SkeletonVariant;
  className?: string;
  width?: string | number;
  height?: string | number;
  count?: number;
}

export const Skeleton: React.FC<SkeletonProps> = ({
  variant = 'text',
  className = '',
  width,
  height,
  count = 1,
}) => {
  const baseClasses = 'animate-pulse bg-neutral-200';

  const renderSingle = (key: number) => {
    switch (variant) {
      case 'circle':
        return (
          <div
            key={key}
            className={`rounded-full ${baseClasses} ${className}`}
            style={{ width: width || 40, height: height || 40 }}
            aria-hidden="true"
          />
        );

      case 'card':
        return (
          <div
            key={key}
            className={`p-4 rounded-lg border border-neutral-200 bg-white space-y-3 ${className}`}
            aria-hidden="true"
          >
            <div className={`h-4 w-1/3 rounded ${baseClasses}`} />
            <div className={`h-6 w-3/4 rounded ${baseClasses}`} />
            <div className={`h-4 w-1/2 rounded ${baseClasses}`} />
          </div>
        );

      case 'table-row':
        return (
          <tr key={key} className="border-b border-neutral-100" aria-hidden="true">
            <td className="p-4" colSpan={6}>
              <div className="flex items-center space-x-4">
                <div className={`h-4 w-24 rounded ${baseClasses}`} />
                <div className={`h-4 flex-1 rounded ${baseClasses}`} />
                <div className={`h-4 w-20 rounded ${baseClasses}`} />
                <div className={`h-4 w-28 rounded ${baseClasses}`} />
              </div>
            </td>
          </tr>
        );

      case 'rect':
        return (
          <div
            key={key}
            className={`rounded-md ${baseClasses} ${className}`}
            style={{ width: width || '100%', height: height || 120 }}
            aria-hidden="true"
          />
        );

      case 'text':
      default:
        return (
          <div
            key={key}
            className={`h-4 rounded ${baseClasses} ${className}`}
            style={{ width: width || '100%', height: height || undefined }}
            aria-hidden="true"
          />
        );
    }
  };

  return (
    <div role="status" aria-label="Loading content..." className="w-full">
      {Array.from({ length: count }, (_, idx) => renderSingle(idx))}
      <span className="sr-only">Loading...</span>
    </div>
  );
};

export default Skeleton;
