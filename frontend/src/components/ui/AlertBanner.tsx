/**
 * CampusFix AlertBanner Component
 *
 * Implements:
 * - WCAG 2.1 AA accessible feedback banners
 * - Semantic roles: role="alert" for errors/warnings, role="status" for success/info
 * - Dismissible callbacks with accessible close buttons
 */

import React from 'react';
import {
  CheckIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
} from './icons';

export type AlertVariant = 'error' | 'warning' | 'success' | 'info';

export interface AlertBannerProps {
  variant?: AlertVariant;
  title?: string;
  children: React.ReactNode;
  onDismiss?: () => void;
  className?: string;
}

export const AlertBanner: React.FC<AlertBannerProps> = ({
  variant = 'info',
  title,
  children,
  onDismiss,
  className = '',
}) => {
  const isUrgent = variant === 'error' || variant === 'warning';
  const role = isUrgent ? 'alert' : 'status';

  const config = {
    error: {
      bg: 'bg-red-50',
      border: 'border-red-200',
      text: 'text-red-800',
      iconColor: 'text-red-600',
      Icon: ExclamationTriangleIcon,
    },
    warning: {
      bg: 'bg-amber-50',
      border: 'border-amber-200',
      text: 'text-amber-800',
      iconColor: 'text-amber-600',
      Icon: ExclamationTriangleIcon,
    },
    success: {
      bg: 'bg-emerald-50',
      border: 'border-emerald-200',
      text: 'text-emerald-800',
      iconColor: 'text-emerald-600',
      Icon: CheckIcon,
    },
    info: {
      bg: 'bg-blue-50',
      border: 'border-blue-200',
      text: 'text-blue-800',
      iconColor: 'text-blue-600',
      Icon: InformationCircleIcon,
    },
  }[variant];

  const { Icon } = config;

  return (
    <div
      role={role}
      className={`flex items-start gap-3 p-4 rounded-md border text-sm ${config.bg} ${config.border} ${config.text} ${className}`}
    >
      <div className={`shrink-0 mt-0.5 ${config.iconColor}`}>
        <Icon className="w-5 h-5" />
      </div>

      <div className="flex-1 space-y-1">
        {title && <h3 className="font-semibold text-sm leading-5">{title}</h3>}
        <div className="text-sm leading-5">{children}</div>
      </div>

      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss alert"
          className="shrink-0 -mr-1 -mt-1 p-1 rounded-md hover:bg-black/5 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:ring-brand-500"
        >
          <XMarkIcon className="w-4 h-4" />
        </button>
      )}
    </div>
  );
};

export default AlertBanner;
