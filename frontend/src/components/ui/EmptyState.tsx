/**
 * CampusFix EmptyState Component
 *
 * Implements context-aware guidance with actionable primary CTAs.
 */

import React from 'react';
import { ClipboardDocumentListIcon } from './icons';

export interface EmptyStateProps {
  title: string;
  description: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon,
  action,
  className = '',
}) => {
  return (
    <div
      className={`flex flex-col items-center justify-center p-8 sm:p-12 text-center rounded-lg border border-dashed border-neutral-300 bg-neutral-25 ${className}`}
    >
      <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-neutral-100 text-neutral-500 mb-4" aria-hidden="true">
        {icon || <ClipboardDocumentListIcon className="w-6 h-6" />}
      </div>
      <h3 className="text-base font-semibold text-neutral-900 mb-1">{title}</h3>
      <p className="text-sm text-neutral-600 max-w-sm mb-6">{description}</p>
      {action && <div className="inline-flex">{action}</div>}
    </div>
  );
};

export default EmptyState;
