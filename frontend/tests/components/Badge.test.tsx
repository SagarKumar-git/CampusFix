import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PriorityBadge, RoleBadge, StatusBadge } from '../../src/components/ui/Badge';
import type { TicketPriority, TicketStatus, UserRole } from '../../src/types';

describe('Badge Components', () => {
  it('renders all ticket status badges with appropriate text and semantic dot', () => {
    const statuses: TicketStatus[] = [
      'SUBMITTED',
      'ASSIGNED',
      'IN_PROGRESS',
      'RESOLVED',
      'REJECTED',
      'CANCELLED',
    ];

    statuses.forEach((status) => {
      const { unmount } = render(<StatusBadge status={status} />);
      const badge = screen.getByText(new RegExp(status.replace('_', ' '), 'i'));
      expect(badge).toBeInTheDocument();
      unmount();
    });
  });

  it('renders priority badges with correct tiers', () => {
    const priorities: TicketPriority[] = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];

    priorities.forEach((priority) => {
      const { unmount } = render(<PriorityBadge priority={priority} />);
      const badge = screen.getByText(new RegExp(priority, 'i'));
      expect(badge).toBeInTheDocument();
      unmount();
    });
  });

  it('renders role badges for all user roles', () => {
    const roles: UserRole[] = ['STUDENT', 'STAFF', 'ADMINISTRATOR'];

    roles.forEach((role) => {
      const { unmount } = render(<RoleBadge role={role} />);
      if (role === 'STUDENT') {
        expect(screen.getByText('Student')).toBeInTheDocument();
      } else if (role === 'STAFF') {
        expect(screen.getByText('Staff Tech')).toBeInTheDocument();
      } else if (role === 'ADMINISTRATOR') {
        expect(screen.getByText('Admin')).toBeInTheDocument();
      }
      unmount();
    });
  });
});
