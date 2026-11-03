/**
 * CampusFix Status and Priority Badge Component
 *
 * Implements:
 * - WCAG 2.1 AA verified contrast ratios
 * - Status pills with semantic colored dots
 * - Priority urgency tier badges
 * - Role identifier pills
 */

import React from 'react';
import type { TicketPriority, TicketStatus, UserRole } from '../../types';

export interface StatusBadgeProps {
  status: TicketStatus;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className = '' }) => {
  const configs: Record<
    TicketStatus,
    { label: string; bg: string; text: string; border: string; dot: string }
  > = {
    SUBMITTED: {
      label: 'Submitted',
      bg: 'bg-status-submitted-bg',
      text: 'text-status-submitted-text',
      border: 'border-status-submitted-border',
      dot: 'bg-status-submitted-dot',
    },
    ASSIGNED: {
      label: 'Assigned',
      bg: 'bg-status-assigned-bg',
      text: 'text-status-assigned-text',
      border: 'border-status-assigned-border',
      dot: 'bg-status-assigned-dot',
    },
    IN_PROGRESS: {
      label: 'In Progress',
      bg: 'bg-status-in_progress-bg',
      text: 'text-status-in_progress-text',
      border: 'border-status-in_progress-border',
      dot: 'bg-status-in_progress-dot',
    },
    RESOLVED: {
      label: 'Resolved',
      bg: 'bg-status-resolved-bg',
      text: 'text-status-resolved-text',
      border: 'border-status-resolved-border',
      dot: 'bg-status-resolved-dot',
    },
    REJECTED: {
      label: 'Rejected',
      bg: 'bg-status-rejected-bg',
      text: 'text-status-rejected-text',
      border: 'border-status-rejected-border',
      dot: 'bg-status-rejected-dot',
    },
    CANCELLED: {
      label: 'Cancelled',
      bg: 'bg-status-cancelled-bg',
      text: 'text-status-cancelled-text',
      border: 'border-status-cancelled-border',
      dot: 'bg-status-cancelled-dot',
    },
  };

  const config = configs[status] || configs.SUBMITTED;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${config.bg} ${config.text} ${config.border} ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} aria-hidden="true" />
      <span>{config.label}</span>
    </span>
  );
};

export interface PriorityBadgeProps {
  priority: TicketPriority;
  className?: string;
}

export const PriorityBadge: React.FC<PriorityBadgeProps> = ({ priority, className = '' }) => {
  const configs: Record<
    TicketPriority,
    { label: string; bg: string; text: string; border: string }
  > = {
    LOW: {
      label: 'Low',
      bg: 'bg-priority-low-bg',
      text: 'text-priority-low-text',
      border: 'border-priority-low-border',
    },
    MEDIUM: {
      label: 'Medium',
      bg: 'bg-priority-medium-bg',
      text: 'text-priority-medium-text',
      border: 'border-priority-medium-border',
    },
    HIGH: {
      label: 'High',
      bg: 'bg-priority-high-bg',
      text: 'text-priority-high-text',
      border: 'border-priority-high-border',
    },
    CRITICAL: {
      label: 'Critical',
      bg: 'bg-priority-critical-bg',
      text: 'text-priority-critical-text',
      border: 'border-priority-critical-border',
    },
  };

  const config = configs[priority] || configs.MEDIUM;

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${config.bg} ${config.text} ${config.border} ${className}`}
    >
      {config.label}
    </span>
  );
};

export interface RoleBadgeProps {
  role: UserRole;
  className?: string;
}

export const RoleBadge: React.FC<RoleBadgeProps> = ({ role, className = '' }) => {
  const configs: Record<UserRole, { label: string; bg: string; text: string }> = {
    STUDENT: {
      label: 'Student',
      bg: 'bg-blue-100',
      text: 'text-blue-800',
    },
    STAFF: {
      label: 'Staff Tech',
      bg: 'bg-purple-100',
      text: 'text-purple-800',
    },
    ADMINISTRATOR: {
      label: 'Admin',
      bg: 'bg-amber-100',
      text: 'text-amber-900',
    },
  };

  const config = configs[role] || configs.STUDENT;

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${config.bg} ${config.text} ${className}`}
    >
      {config.label}
    </span>
  );
};

export interface ActiveStatusBadgeProps {
  isActive: boolean;
  className?: string;
}

export const ActiveStatusBadge: React.FC<ActiveStatusBadgeProps> = ({
  isActive,
  className = '',
}) => {
  return isActive ? (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200 ${className}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" aria-hidden="true" />
      <span>ACTIVE</span>
    </span>
  ) : (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-neutral-100 text-neutral-600 border border-neutral-300 ${className}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-neutral-400" aria-hidden="true" />
      <span>INACTIVE</span>
    </span>
  );
};

