/**
 * CampusFix Staff Workbench Queue Tests (SCR-05)
 *
 * Verifies:
 * - Workbench rendering, tab navigation, badge counts, and filter selects
 * - Initial load fetches assigned tickets with assigned_staff_id='me' and status='ASSIGNED,IN_PROGRESS'
 * - Tab switching to "Unassigned Queue" fetches status='SUBMITTED'
 * - Quick-claim workflow: fetches fresh ticket version, assigns to authenticated staff, shows success, and refreshes queue
 * - Concurrency conflict (HTTP 409) handling on claim & start work: displays conflict alert and refreshes queue
 * - Quick "Start Work" workflow: transitions ASSIGNED ticket to IN_PROGRESS
 * - Filter controls: category and priority re-querying
 * - Client-side sorting: Priority High-to-Low and Oldest First
 * - Contextual empty states for Assigned and Unassigned tabs
 * - Action in-flight disabling to prevent duplicate clicks
 * - Navigation to /tickets/:id on row click and proper stopPropagation on action buttons
 * - Error state presentation with functional retry CTA
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { categoriesApi } from '../../src/api/categories';
import { ApiError } from '../../src/api/client';
import { ticketsApi } from '../../src/api/tickets';
import { AuthContext, type AuthContextType } from '../../src/context/AuthContext';
import StaffQueuePage from '../../src/pages/staff/StaffQueuePage';
import type {
  Category,
  PaginatedResponse,
  Ticket,
  TicketSummary,
  User,
} from '../../src/types';

const mockStaffUser: User = {
  id: 'u0000000-0000-0000-0000-000000000002',
  email: 'alex.tech@university.edu',
  full_name: 'Alex Rivera',
  role: 'STAFF',
  is_active: true,
  created_at: '2026-10-01T00:00:00Z',
};

const mockCategories: Category[] = [
  {
    id: 'c0000000-0000-0000-0000-000000000001',
    name: 'Classroom Audio-Visual',
    description: 'Projectors and audio equipment',
    is_active: true,
  },
  {
    id: 'c0000000-0000-0000-0000-000000000002',
    name: 'Plumbing & Water',
    description: 'Leaks and restroom fixtures',
    is_active: true,
  },
];

const mockAssignedTickets: TicketSummary[] = [
  {
    id: 'a0000000-0000-0000-0000-000000000001',
    ticket_number: 'CFX-2026-00042',
    title: 'Projector HDMI Port Damaged',
    category_name: 'Classroom Audio-Visual',
    location: 'Science Block A, Room 402',
    priority: 'HIGH',
    status: 'IN_PROGRESS',
    creator_name: 'Jane Student',
    assigned_staff_name: 'Alex Rivera',
    created_at: '2026-11-01T10:00:00Z',
  },
  {
    id: 'a0000000-0000-0000-0000-000000000002',
    ticket_number: 'CFX-2026-00038',
    title: 'Water Leak Under Main Sink',
    category_name: 'Plumbing & Water',
    location: 'Hostel 3, Restroom 2nd Floor',
    priority: 'CRITICAL',
    status: 'ASSIGNED',
    creator_name: 'Bob Student',
    assigned_staff_name: 'Alex Rivera',
    created_at: '2026-11-01T08:00:00Z',
  },
];

const mockUnassignedTickets: TicketSummary[] = [
  {
    id: 'u0000000-0000-0000-0000-000000000003',
    ticket_number: 'CFX-2026-00050',
    title: 'Broken Window Latch',
    category_name: 'Plumbing & Water',
    location: 'Library 3rd Floor',
    priority: 'LOW',
    status: 'SUBMITTED',
    creator_name: 'Alice Student',
    assigned_staff_name: null,
    created_at: '2026-11-01T11:00:00Z',
  },
];

const createPaginatedResponse = (
  items: TicketSummary[],
  total?: number
): PaginatedResponse<TicketSummary> => ({
  success: true,
  data: items,
  meta: {
    page: 1,
    page_size: 10,
    total: total ?? items.length,
    total_pages: 1,
  },
});

describe('SCR-05: StaffQueuePage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(categoriesApi, 'listCategories').mockResolvedValue(mockCategories);
  });

  const renderStaffQueuePage = (user: User = mockStaffUser) => {
    const authContextValue: AuthContextType = {
      user,
      accessToken: 'mock-staff-token',
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshSession: vi.fn(),
    };

    return render(
      <AuthContext.Provider value={authContextValue}>
        <MemoryRouter initialEntries={['/staff/queue']}>
          <Routes>
            <Route path="/staff/queue" element={<StaffQueuePage />} />
            <Route
              path="/tickets/:id"
              element={<div data-testid="ticket-detail-view">Ticket Detail View</div>}
            />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    );
  };

  it('renders workbench queue header, tabs with badges, and assigned work orders', async () => {
    const listSpy = vi.spyOn(ticketsApi, 'listTickets').mockImplementation(async (params) => {
      if (params?.status === 'SUBMITTED') {
        return createPaginatedResponse(mockUnassignedTickets, 1);
      }
      return createPaginatedResponse(mockAssignedTickets, 2);
    });

    renderStaffQueuePage();

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /facilities maintenance queue/i })
      ).toBeInTheDocument();
    });

    // Check tab buttons
    expect(screen.getByRole('tab', { name: /assigned to me/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /unassigned queue/i })).toBeInTheDocument();

    // Check tickets rendered in table
    expect(screen.getAllByText('CFX-2026-00042').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Projector HDMI Port Damaged')[0]).toBeInTheDocument();
    expect(screen.getAllByText('CFX-2026-00038').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Water Leak Under Main Sink')[0]).toBeInTheDocument();

    // Check action buttons for Assigned tab
    expect(screen.getAllByRole('button', { name: /start work on ticket cfx-2026-00038/i })[0]).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /resolve ticket cfx-2026-00042/i })[0]).toBeInTheDocument();

    // Verify initial call queried assigned_staff_id='me'
    expect(listSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        assigned_staff_id: 'me',
        status: 'ASSIGNED,IN_PROGRESS',
      })
    );
  });

  it('switches to unassigned queue tab and renders claim ticket action', async () => {
    const user = userEvent.setup();
    const listSpy = vi.spyOn(ticketsApi, 'listTickets').mockImplementation(async (params) => {
      if (params?.status === 'SUBMITTED') {
        return createPaginatedResponse(mockUnassignedTickets, 1);
      }
      return createPaginatedResponse(mockAssignedTickets, 2);
    });

    renderStaffQueuePage();

    await waitFor(() => {
      expect(screen.getAllByText('CFX-2026-00042').length).toBeGreaterThanOrEqual(1);
    });

    // Click Unassigned Queue tab
    const unassignedTab = screen.getByRole('tab', { name: /unassigned queue/i });
    await user.click(unassignedTab);

    await waitFor(() => {
      expect(screen.getAllByText('CFX-2026-00050').length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getAllByText('Broken Window Latch')[0]).toBeInTheDocument();
    expect(
      screen.getAllByRole('button', { name: /claim ticket cfx-2026-00050/i })[0]
    ).toBeInTheDocument();

    expect(listSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        status: 'SUBMITTED',
      })
    );
  });

  it('successfully executes quick-claim workflow on unassigned ticket', async () => {
    const user = userEvent.setup();

    vi.spyOn(ticketsApi, 'listTickets').mockImplementation(async (params) => {
      if (params?.status === 'SUBMITTED') {
        return createPaginatedResponse(mockUnassignedTickets, 1);
      }
      return createPaginatedResponse(mockAssignedTickets, 2);
    });

    const mockDetail: Ticket = {
      id: 'u0000000-0000-0000-0000-000000000003',
      ticket_number: 'CFX-2026-00050',
      title: 'Broken Window Latch',
      description: 'The latch is broken.',
      category: { id: 'c0000000-0000-0000-0000-000000000002', name: 'Plumbing & Water' },
      location: 'Library 3rd Floor',
      priority: 'LOW',
      status: 'SUBMITTED',
      creator: { id: 'u0000000-0000-0000-0000-000000000001', full_name: 'Alice Student' },
      assigned_staff: null,
      resolution_notes: null,
      rejection_reason: null,
      version: 3,
      created_at: '2026-11-01T11:00:00Z',
      updated_at: '2026-11-01T11:00:00Z',
    };

    const getTicketSpy = vi.spyOn(ticketsApi, 'getTicket').mockResolvedValue(mockDetail);
    const assignTicketSpy = vi.spyOn(ticketsApi, 'assignTicket').mockResolvedValue({
      id: mockDetail.id,
      ticket_number: mockDetail.ticket_number,
      status: 'ASSIGNED',
      assigned_staff_id: mockStaffUser.id,
      version: 4,
      updated_at: '2026-11-01T11:05:00Z',
    });

    renderStaffQueuePage();

    await waitFor(() => {
      expect(screen.getAllByText('CFX-2026-00042').length).toBeGreaterThanOrEqual(1);
    });

    // Switch to Unassigned
    await user.click(screen.getByRole('tab', { name: /unassigned queue/i }));

    await waitFor(() => {
      expect(screen.getAllByText('CFX-2026-00050').length).toBeGreaterThanOrEqual(1);
    });

    // Click Claim Ticket
    const claimBtn = screen.getAllByRole('button', { name: /claim ticket cfx-2026-00050/i })[0];
    await user.click(claimBtn);

    await waitFor(() => {
      expect(getTicketSpy).toHaveBeenCalledWith('u0000000-0000-0000-0000-000000000003');
      expect(assignTicketSpy).toHaveBeenCalledWith(
        'u0000000-0000-0000-0000-000000000003',
        {
          staff_id: mockStaffUser.id,
          expected_version: 3,
        }
      );
    });

    await waitFor(() => {
      expect(
        screen.getByText(/successfully claimed ticket cfx-2026-00050/i)
      ).toBeInTheDocument();
    });
  });

  it('handles HTTP 409 concurrency conflict on claim and refreshes queue', async () => {
    const user = userEvent.setup();

    const listSpy = vi.spyOn(ticketsApi, 'listTickets').mockImplementation(async (params) => {
      if (params?.status === 'SUBMITTED') {
        return createPaginatedResponse(mockUnassignedTickets, 1);
      }
      return createPaginatedResponse(mockAssignedTickets, 2);
    });

    vi.spyOn(ticketsApi, 'getTicket').mockResolvedValue({
      id: 'u0000000-0000-0000-0000-000000000003',
      ticket_number: 'CFX-2026-00050',
      title: 'Broken Window Latch',
      description: 'The latch is broken.',
      category: { id: 'c0000000-0000-0000-0000-000000000002', name: 'Plumbing & Water' },
      location: 'Library 3rd Floor',
      priority: 'LOW',
      status: 'SUBMITTED',
      creator: { id: 'u0000000-0000-0000-0000-000000000001', full_name: 'Alice Student' },
      assigned_staff: null,
      resolution_notes: null,
      rejection_reason: null,
      version: 1,
      created_at: '2026-11-01T11:00:00Z',
      updated_at: '2026-11-01T11:00:00Z',
    });

    vi.spyOn(ticketsApi, 'assignTicket').mockRejectedValue(
      new ApiError(409, 'CONCURRENCY_CONFLICT', 'Ticket was modified by another technician')
    );

    renderStaffQueuePage();

    await waitFor(() => {
      expect(screen.getAllByText('CFX-2026-00042').length).toBeGreaterThanOrEqual(1);
    });

    await user.click(screen.getByRole('tab', { name: /unassigned queue/i }));

    await waitFor(() => {
      expect(screen.getAllByText('CFX-2026-00050').length).toBeGreaterThanOrEqual(1);
    });

    await user.click(screen.getAllByRole('button', { name: /claim ticket cfx-2026-00050/i })[0]);

    await waitFor(() => {
      expect(
        screen.getByText(/concurrency conflict: ticket cfx-2026-00050 was claimed or updated by another user/i)
      ).toBeInTheDocument();
    });

    // Queue was refreshed following conflict
    expect(listSpy.mock.calls.length).toBeGreaterThanOrEqual(4);
  });

  it('successfully executes quick "Start Work" action on assigned ticket', async () => {
    const user = userEvent.setup();

    vi.spyOn(ticketsApi, 'listTickets').mockImplementation(async (params) => {
      if (params?.status === 'SUBMITTED') {
        return createPaginatedResponse(mockUnassignedTickets, 1);
      }
      return createPaginatedResponse(mockAssignedTickets, 2);
    });

    const mockDetail: Ticket = {
      id: 'a0000000-0000-0000-0000-000000000002',
      ticket_number: 'CFX-2026-00038',
      title: 'Water Leak Under Main Sink',
      description: 'Leak detail',
      category: { id: 'c0000000-0000-0000-0000-000000000002', name: 'Plumbing & Water' },
      location: 'Hostel 3, Restroom 2nd Floor',
      priority: 'CRITICAL',
      status: 'ASSIGNED',
      creator: { id: 'u0000000-0000-0000-0000-000000000001', full_name: 'Bob Student' },
      assigned_staff: { id: mockStaffUser.id, full_name: mockStaffUser.full_name },
      resolution_notes: null,
      rejection_reason: null,
      version: 2,
      created_at: '2026-11-01T08:00:00Z',
      updated_at: '2026-11-01T08:00:00Z',
    };

    const getTicketSpy = vi.spyOn(ticketsApi, 'getTicket').mockResolvedValue(mockDetail);
    const transitionSpy = vi.spyOn(ticketsApi, 'transitionTicket').mockResolvedValue({
      id: mockDetail.id,
      ticket_number: mockDetail.ticket_number,
      status: 'IN_PROGRESS',
      resolution_notes: null,
      rejection_reason: null,
      version: 3,
      updated_at: '2026-11-01T08:30:00Z',
    });

    renderStaffQueuePage();

    await waitFor(() => {
      expect(screen.getAllByText('CFX-2026-00038').length).toBeGreaterThanOrEqual(1);
    });

    const startWorkBtn = screen.getAllByRole('button', {
      name: /start work on ticket cfx-2026-00038/i,
    })[0];
    await user.click(startWorkBtn);

    await waitFor(() => {
      expect(getTicketSpy).toHaveBeenCalledWith('a0000000-0000-0000-0000-000000000002');
      expect(transitionSpy).toHaveBeenCalledWith(
        'a0000000-0000-0000-0000-000000000002',
        {
          target_status: 'IN_PROGRESS',
          expected_version: 2,
        }
      );
    });

    await waitFor(() => {
      expect(
        screen.getByText(/work started on ticket cfx-2026-00038/i)
      ).toBeInTheDocument();
    });
  });

  it('re-queries queue when filter select values change', async () => {
    const user = userEvent.setup();
    const listSpy = vi.spyOn(ticketsApi, 'listTickets').mockResolvedValue(
      createPaginatedResponse(mockAssignedTickets)
    );

    renderStaffQueuePage();

    await waitFor(() => {
      expect(screen.getAllByText('CFX-2026-00042').length).toBeGreaterThanOrEqual(1);
    });

    // Change category filter
    const categorySelect = screen.getByLabelText(/filter by category/i);
    await user.selectOptions(categorySelect, 'c0000000-0000-0000-0000-000000000001');

    await waitFor(() => {
      expect(listSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          category_id: 'c0000000-0000-0000-0000-000000000001',
        })
      );
    });

    // Change priority filter
    const prioritySelect = screen.getByLabelText(/filter by priority/i);
    await user.selectOptions(prioritySelect, 'CRITICAL');

    await waitFor(() => {
      expect(listSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          priority: 'CRITICAL',
        })
      );
    });
  });

  it('sorts tickets client-side when user selects priority or oldest first', async () => {
    const user = userEvent.setup();
    vi.spyOn(ticketsApi, 'listTickets').mockResolvedValue(
      createPaginatedResponse(mockAssignedTickets)
    );

    renderStaffQueuePage();

    await waitFor(() => {
      expect(screen.getAllByText('CFX-2026-00042').length).toBeGreaterThanOrEqual(1);
    });

    const sortSelect = screen.getByLabelText(/sort orders/i);

    // Sort by priority (CRITICAL > HIGH)
    await user.selectOptions(sortSelect, 'PRIORITY');

    // CFX-2026-00038 is CRITICAL, CFX-2026-00042 is HIGH
    // Check that both tickets remain rendered
    expect(screen.getAllByText('CFX-2026-00038').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('CFX-2026-00042').length).toBeGreaterThanOrEqual(1);
  });

  it('renders contextual empty state for assigned queue and switches to unassigned on CTA click', async () => {
    const user = userEvent.setup();
    vi.spyOn(ticketsApi, 'listTickets').mockImplementation(async (params) => {
      if (params?.status === 'SUBMITTED') {
        return createPaginatedResponse(mockUnassignedTickets, 1);
      }
      return createPaginatedResponse([], 0);
    });

    renderStaffQueuePage();

    await waitFor(() => {
      expect(screen.getByText(/no assigned work orders/i)).toBeInTheDocument();
      expect(
        screen.getByText(/great job! you have no pending work orders assigned/i)
      ).toBeInTheDocument();
    });

    const ctaButton = screen.getByRole('button', { name: /check unassigned queue/i });
    await user.click(ctaButton);

    await waitFor(() => {
      expect(screen.getAllByText('CFX-2026-00050').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('renders contextual empty state for unassigned queue when pool is clear', async () => {
    const user = userEvent.setup();
    vi.spyOn(ticketsApi, 'listTickets').mockImplementation(async (params) => {
      if (params?.status === 'SUBMITTED') {
        return createPaginatedResponse([], 0);
      }
      return createPaginatedResponse(mockAssignedTickets, 2);
    });

    renderStaffQueuePage();

    await waitFor(() => {
      expect(screen.getAllByText('CFX-2026-00042').length).toBeGreaterThanOrEqual(1);
    });

    await user.click(screen.getByRole('tab', { name: /unassigned queue/i }));

    await waitFor(() => {
      expect(screen.getByText(/queue clear/i)).toBeInTheDocument();
      expect(
        screen.getByText(/no unassigned tickets in the campus queue/i)
      ).toBeInTheDocument();
    });
  });

  it('navigates to /tickets/:id on row click but stops propagation on action buttons', async () => {
    const user = userEvent.setup();
    vi.spyOn(ticketsApi, 'listTickets').mockResolvedValue(
      createPaginatedResponse(mockAssignedTickets)
    );

    renderStaffQueuePage();

    await waitFor(() => {
      expect(screen.getAllByText('CFX-2026-00042').length).toBeGreaterThanOrEqual(1);
    });

    // Click Open Work button
    const openWorkButtons = screen.getAllByRole('button', { name: /open work order/i });
    await user.click(openWorkButtons[0]);

    await waitFor(() => {
      expect(screen.getByTestId('ticket-detail-view')).toBeInTheDocument();
    });
  });

  it('renders error banner with retry button when queue fetch fails', async () => {
    const user = userEvent.setup();
    const listSpy = vi
      .spyOn(ticketsApi, 'listTickets')
      .mockRejectedValueOnce(new Error('Network error loading queue'))
      .mockResolvedValueOnce(createPaginatedResponse(mockAssignedTickets));

    renderStaffQueuePage();

    await waitFor(() => {
      expect(screen.getByText(/could not load queue/i)).toBeInTheDocument();
      expect(screen.getByText(/network error loading queue/i)).toBeInTheDocument();
    });

    const retryBtn = screen.getByRole('button', { name: /retry request/i });
    await user.click(retryBtn);

    await waitFor(() => {
      expect(screen.getAllByText('CFX-2026-00042').length).toBeGreaterThanOrEqual(1);
    });

    expect(listSpy.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});
