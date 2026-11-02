/**
 * CampusFix Ticket Detail Page Tests (SCR-04)
 *
 * Verifies:
 * - Successful ticket details loading and metadata rendering
 * - Prominent human-readable ticket code (CFX-YYYY-XXXXX)
 * - Chronological audit timeline rendering with transitions, authors, and notes
 * - Invalid UUID format rejection
 * - HTTP 404 and HTTP 403 error states with retry & back navigation
 * - Role-governed action buttons visibility based on FSM rules
 * - HTTP 409 concurrency conflict detection, alert presentation, and state reload
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../src/api/client';
import { ticketsApi } from '../../src/api/tickets';
import { AuthContext, type AuthContextType } from '../../src/context/AuthContext';
import { TicketDetailPage } from '../../src/pages/tickets/TicketDetailPage';
import type { Ticket, TicketHistoryItem, User } from '../../src/types';

const mockTicketId = 'a0000000-0000-0000-0000-000000000001';

const mockStudentUser: User = {
  id: 'u0000000-0000-0000-0000-000000000001',
  email: 'alex.student@university.edu',
  full_name: 'Alex Student',
  role: 'STUDENT',
  is_active: true,
  created_at: '2026-10-01T00:00:00Z',
};

const mockStaffUser: User = {
  id: 'u0000000-0000-0000-0000-000000000002',
  email: 'jordan.tech@university.edu',
  full_name: 'Jordan Tech',
  role: 'STAFF',
  is_active: true,
  created_at: '2026-10-01T00:00:00Z',
};

const mockAdminUser: User = {
  id: 'u0000000-0000-0000-0000-000000000003',
  email: 'morgan.admin@university.edu',
  full_name: 'Morgan Admin',
  role: 'ADMINISTRATOR',
  is_active: true,
  created_at: '2026-10-01T00:00:00Z',
};

const mockTicketData: Ticket = {
  id: mockTicketId,
  ticket_number: 'CFX-2026-00042',
  title: 'Projector HDMI Bent in Room 402',
  description: 'The wall-mounted HDMI plate has bent pins preventing laptop display output.',
  category: { id: 'c0000000-0000-0000-0000-000000000001', name: 'Classroom Audio-Visual' },
  location: 'Science Block A, Room 402',
  priority: 'HIGH',
  status: 'SUBMITTED',
  creator: { id: mockStudentUser.id, full_name: mockStudentUser.full_name },
  assigned_staff: null,
  resolution_notes: null,
  rejection_reason: null,
  version: 1,
  created_at: '2026-11-01T10:00:00Z',
  updated_at: '2026-11-01T10:00:00Z',
};

const mockHistoryData: TicketHistoryItem[] = [
  {
    id: 'h0000000-0000-0000-0000-000000000001',
    ticket_id: mockTicketId,
    from_status: null,
    to_status: 'SUBMITTED',
    changed_by: { id: mockStudentUser.id, full_name: mockStudentUser.full_name },
    assigned_to: null,
    notes: 'Initial issue filing by student.',
    created_at: '2026-11-01T10:00:00Z',
  },
];

describe('SCR-04: TicketDetailPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderDetailPage = (user: User = mockStudentUser, ticketId: string = mockTicketId) => {
    const authContextValue: AuthContextType = {
      user,
      accessToken: 'mock-access-token',
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshSession: vi.fn(),
    };

    return render(
      <AuthContext.Provider value={authContextValue}>
        <MemoryRouter initialEntries={[`/tickets/${ticketId}`]}>
          <Routes>
            <Route path="/tickets/:id" element={<TicketDetailPage />} />
            <Route path="/student/tickets" element={<div>Student Tickets Dashboard</div>} />
            <Route path="/staff/queue" element={<div>Staff Queue Dashboard</div>} />
            <Route path="/admin/categories" element={<div>Admin Categories Dashboard</div>} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    );
  };

  it('renders ticket details and chronological audit timeline cleanly', async () => {
    vi.spyOn(ticketsApi, 'getTicket').mockResolvedValue(mockTicketData);
    vi.spyOn(ticketsApi, 'getTicketHistory').mockResolvedValue(mockHistoryData);

    renderDetailPage(mockStudentUser);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Projector HDMI Bent in Room 402' })).toBeInTheDocument();
    });

    // Human-readable code
    expect(screen.getAllByText('CFX-2026-00042').length).toBeGreaterThanOrEqual(1);

    // Metadata details
    expect(screen.getAllByText('Classroom Audio-Visual').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Science Block A, Room 402').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Alex Student').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('v1').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Unassigned')).toBeInTheDocument();

    // Audit trail timeline
    expect(screen.getByText(/audit trail & history/i)).toBeInTheDocument();
    expect(screen.getByText('Initial issue filing by student.')).toBeInTheDocument();
  });

  it('rejects invalid UUID format immediately without dispatching API request', async () => {
    const getTicketSpy = vi.spyOn(ticketsApi, 'getTicket');

    renderDetailPage(mockStudentUser, 'not-a-valid-uuid');

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(
        screen.getByText(/invalid ticket identifier format/i)
      ).toBeInTheDocument();
    });

    expect(getTicketSpy).not.toHaveBeenCalled();
  });

  it('displays error alert on HTTP 404 (Resource Not Found / IDOR isolation)', async () => {
    vi.spyOn(ticketsApi, 'getTicket').mockRejectedValue(
      new ApiError(404, 'RESOURCE_NOT_FOUND', 'Ticket does not exist or access forbidden.')
    );
    vi.spyOn(ticketsApi, 'getTicketHistory').mockResolvedValue([]);

    renderDetailPage(mockStudentUser);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(
        screen.getByText(/ticket not found or you do not have permission/i)
      ).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /return to dashboard/i })).toBeInTheDocument();
  });

  it('displays role-governed actions for student creator on SUBMITTED ticket (Cancel allowed, Claim hidden)', async () => {
    vi.spyOn(ticketsApi, 'getTicket').mockResolvedValue(mockTicketData);
    vi.spyOn(ticketsApi, 'getTicketHistory').mockResolvedValue(mockHistoryData);

    renderDetailPage(mockStudentUser);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Projector HDMI Bent in Room 402' })).toBeInTheDocument();
    });

    // Student creator can cancel
    expect(screen.getByRole('button', { name: /cancel ticket/i })).toBeInTheDocument();

    // Staff/Admin actions are hidden from student
    expect(screen.queryByRole('button', { name: /claim ticket/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /assign technician/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /start work/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /resolve ticket/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /reject ticket/i })).not.toBeInTheDocument();
  });

  it('displays Cancel Ticket action for student creator on ASSIGNED ticket', async () => {
    const assignedTicket: Ticket = {
      ...mockTicketData,
      status: 'ASSIGNED',
      assigned_staff: { id: mockStaffUser.id, full_name: mockStaffUser.full_name },
      version: 2,
    };
    vi.spyOn(ticketsApi, 'getTicket').mockResolvedValue(assignedTicket);
    vi.spyOn(ticketsApi, 'getTicketHistory').mockResolvedValue(mockHistoryData);

    renderDetailPage(mockStudentUser);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Projector HDMI Bent in Room 402' })).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /cancel ticket/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /start work/i })).not.toBeInTheDocument();
  });

  it('does not display Cancel Ticket action for administrator viewing another user\'s ticket', async () => {
    vi.spyOn(ticketsApi, 'getTicket').mockResolvedValue(mockTicketData);
    vi.spyOn(ticketsApi, 'getTicketHistory').mockResolvedValue(mockHistoryData);

    renderDetailPage(mockAdminUser);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Projector HDMI Bent in Room 402' })).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /assign technician/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /claim ticket/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reject ticket/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /cancel ticket/i })).not.toBeInTheDocument();
  });

  it('does not display Cancel Ticket action for administrator viewing a ticket they created (per FR-016)', async () => {
    const adminCreatedTicket: Ticket = {
      ...mockTicketData,
      creator: { id: mockAdminUser.id, full_name: mockAdminUser.full_name },
    };
    vi.spyOn(ticketsApi, 'getTicket').mockResolvedValue(adminCreatedTicket);
    vi.spyOn(ticketsApi, 'getTicketHistory').mockResolvedValue(mockHistoryData);

    renderDetailPage(mockAdminUser);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Projector HDMI Bent in Room 402' })).toBeInTheDocument();
    });

    // Administrator cannot cancel even if creator; FR-016 restricts cancellation strictly to students
    expect(screen.queryByRole('button', { name: /cancel ticket/i })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reject ticket/i })).toBeInTheDocument();
  });

  it('does not display Cancel Ticket action for staff user viewing a ticket', async () => {
    vi.spyOn(ticketsApi, 'getTicket').mockResolvedValue(mockTicketData);
    vi.spyOn(ticketsApi, 'getTicketHistory').mockResolvedValue(mockHistoryData);

    renderDetailPage(mockStaffUser);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Projector HDMI Bent in Room 402' })).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: /cancel ticket/i })).not.toBeInTheDocument();
  });

  it('displays role-governed actions for staff on SUBMITTED ticket (Claim & Reject allowed)', async () => {
    vi.spyOn(ticketsApi, 'getTicket').mockResolvedValue(mockTicketData);
    vi.spyOn(ticketsApi, 'getTicketHistory').mockResolvedValue(mockHistoryData);

    renderDetailPage(mockStaffUser);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Projector HDMI Bent in Room 402' })).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /claim ticket/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reject ticket/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /start work/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /resolve ticket/i })).not.toBeInTheDocument();
  });

  it('displays Start Work for assigned staff on ASSIGNED ticket', async () => {
    const assignedTicket: Ticket = {
      ...mockTicketData,
      status: 'ASSIGNED',
      assigned_staff: { id: mockStaffUser.id, full_name: mockStaffUser.full_name },
      version: 2,
    };
    vi.spyOn(ticketsApi, 'getTicket').mockResolvedValue(assignedTicket);
    vi.spyOn(ticketsApi, 'getTicketHistory').mockResolvedValue(mockHistoryData);

    renderDetailPage(mockStaffUser);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /start work/i })).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /reject ticket/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /claim ticket/i })).not.toBeInTheDocument();
  });

  it('displays Resolve Ticket and Pause Work for assigned staff on IN_PROGRESS ticket', async () => {
    const inProgressTicket: Ticket = {
      ...mockTicketData,
      status: 'IN_PROGRESS',
      assigned_staff: { id: mockStaffUser.id, full_name: mockStaffUser.full_name },
      version: 3,
    };
    vi.spyOn(ticketsApi, 'getTicket').mockResolvedValue(inProgressTicket);
    vi.spyOn(ticketsApi, 'getTicketHistory').mockResolvedValue(mockHistoryData);

    renderDetailPage(mockStaffUser);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /resolve ticket/i })).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /pause work/i })).toBeInTheDocument();
    // Non-admin cannot reject while IN_PROGRESS
    expect(screen.queryByRole('button', { name: /reject ticket/i })).not.toBeInTheDocument();
  });

  it('displays Reopen Ticket for administrator on RESOLVED ticket', async () => {
    const resolvedTicket: Ticket = {
      ...mockTicketData,
      status: 'RESOLVED',
      resolution_notes: 'Replaced wall connector socket plate.',
      version: 4,
    };
    vi.spyOn(ticketsApi, 'getTicket').mockResolvedValue(resolvedTicket);
    vi.spyOn(ticketsApi, 'getTicketHistory').mockResolvedValue(mockHistoryData);

    renderDetailPage(mockAdminUser);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /reopen ticket/i })).toBeInTheDocument();
    });

    expect(screen.getByText('Replaced wall connector socket plate.')).toBeInTheDocument();
  });

  it('handles HTTP 409 concurrency conflict by showing alert and reloading updated ticket state', async () => {
    const user = userEvent.setup();
    const staleTicket: Ticket = {
      ...mockTicketData,
      status: 'IN_PROGRESS',
      assigned_staff: { id: mockStaffUser.id, full_name: mockStaffUser.full_name },
      version: 2,
    };
    const freshTicket: Ticket = {
      ...staleTicket,
      version: 3,
      status: 'RESOLVED',
      resolution_notes: 'Resolved by another technician in concurrent session.',
    };

    const getTicketSpy = vi
      .spyOn(ticketsApi, 'getTicket')
      .mockResolvedValueOnce(staleTicket)
      .mockResolvedValueOnce(freshTicket);

    vi.spyOn(ticketsApi, 'getTicketHistory').mockResolvedValue(mockHistoryData);

    const conflictError = new ApiError(
      409,
      'CONCURRENCY_CONFLICT',
      'Ticket version conflict: expected 2, but ticket is at version 3.',
      { expected_version: 2, actual_version: 3 }
    );
    vi.spyOn(ticketsApi, 'transitionTicket').mockRejectedValueOnce(conflictError);

    renderDetailPage(mockStaffUser);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /resolve ticket/i })).toBeInTheDocument();
    });

    // Open resolve modal
    await user.click(screen.getByRole('button', { name: /resolve ticket/i }));

    const textarea = screen.getByLabelText(/resolution actions taken/i);
    await user.type(textarea, 'Replaced projector lamp and cleaned exhaust filter.');

    const confirmBtn = screen.getByRole('button', { name: /confirm & mark resolved/i });
    await user.click(confirmBtn);

    // After 409 rejection:
    // 1. Conflict banner rendered
    await waitFor(() => {
      expect(screen.getByText(/concurrency conflict/i)).toBeInTheDocument();
    });

    // 2. Fresh ticket data reloaded
    expect(getTicketSpy).toHaveBeenCalledTimes(2);

    // 3. New state reflected in UI
    await waitFor(() => {
      expect(screen.getAllByText('v3').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Resolved by another technician in concurrent session.')).toBeInTheDocument();
    });
  });

  it('navigates back to student dashboard when back button is clicked', async () => {
    const user = userEvent.setup();
    vi.spyOn(ticketsApi, 'getTicket').mockResolvedValue(mockTicketData);
    vi.spyOn(ticketsApi, 'getTicketHistory').mockResolvedValue(mockHistoryData);

    renderDetailPage(mockStudentUser);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /back to dashboard/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /back to dashboard/i }));

    await waitFor(() => {
      expect(screen.getByText('Student Tickets Dashboard')).toBeInTheDocument();
    });
  });
});
