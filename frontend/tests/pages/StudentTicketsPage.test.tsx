import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ticketsApi } from '../../src/api/tickets';
import StudentTicketsPage from '../../src/pages/student/StudentTicketsPage';
import type { PaginatedResponse, TicketSummary } from '../../src/types';

describe('SCR-02: StudentTicketsPage', () => {
  const mockTickets: TicketSummary[] = [
    {
      id: '550e8400-e29b-41d4-a716-446655440000',
      ticket_number: 'CFX-2026-00042',
      title: 'Projector HDMI Bent in Room 402',
      category_name: 'Classroom Audio-Visual',
      location: 'Science Block A, Room 402',
      priority: 'HIGH',
      status: 'SUBMITTED',
      creator_name: 'Jane Student',
      assigned_staff_name: null,
      created_at: '2026-10-27T13:40:00Z',
    },
    {
      id: '660e8400-e29b-41d4-a716-446655440001',
      ticket_number: 'CFX-2026-00043',
      title: 'Water Leak under Lab Sink',
      category_name: 'Plumbing & Water',
      location: 'Chemistry Lab 101',
      priority: 'CRITICAL',
      status: 'RESOLVED',
      creator_name: 'Jane Student',
      assigned_staff_name: 'Alex Tech',
      created_at: '2026-10-26T09:15:00Z',
    },
  ];

  const mockResponse: PaginatedResponse<TicketSummary> = {
    success: true,
    data: mockTickets,
    meta: {
      page: 1,
      page_size: 10,
      total: 2,
      total_pages: 1,
    },
  };

  const renderStudentTicketsPage = () => {
    return render(
      <MemoryRouter initialEntries={['/student/tickets']}>
        <Routes>
          <Route path="/student/tickets" element={<StudentTicketsPage />} />
          <Route path="/tickets/new" element={<div>Create Ticket Flow</div>} />
          <Route
            path="/tickets/:id"
            element={<div>Ticket Detail UUID View</div>}
          />
        </Routes>
      </MemoryRouter>
    );
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders ticket list with status badges, priority pills, and codes', async () => {
    vi.spyOn(ticketsApi, 'listTickets').mockResolvedValue(mockResponse);

    renderStudentTicketsPage();

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /my reported issues/i })
      ).toBeInTheDocument();
    });

    expect(screen.getAllByText('CFX-2026-00042').length).toBeGreaterThanOrEqual(1);
    expect(
      screen.getAllByText('Projector HDMI Bent in Room 402')[0]
    ).toBeInTheDocument();
    expect(screen.getAllByText('Science Block A, Room 402')[0]).toBeInTheDocument();
    expect(screen.getAllByText('Classroom Audio-Visual')[0]).toBeInTheDocument();
    expect(screen.getAllByText('High')[0]).toBeInTheDocument();
    expect(screen.getAllByText('Submitted')[0]).toBeInTheDocument();

    expect(screen.getAllByText('CFX-2026-00043').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Water Leak under Lab Sink')[0]).toBeInTheDocument();
    expect(screen.getAllByText('Resolved')[0]).toBeInTheDocument();
  });

  it('re-queries API with status parameter when filter tab is clicked', async () => {
    const user = userEvent.setup();
    const listSpy = vi.spyOn(ticketsApi, 'listTickets').mockResolvedValue(mockResponse);

    renderStudentTicketsPage();

    await waitFor(() => {
      expect(screen.getAllByText('CFX-2026-00042').length).toBeGreaterThanOrEqual(1);
    });

    const resolvedTab = screen.getByRole('button', { name: /resolved/i });
    await user.click(resolvedTab);

    expect(listSpy).toHaveBeenCalledWith({
      page: 1,
      page_size: 10,
      status: 'RESOLVED',
    });
  });

  it('renders contextual empty state when student has no tickets', async () => {
    vi.spyOn(ticketsApi, 'listTickets').mockResolvedValue({
      success: true,
      data: [],
      meta: { page: 1, page_size: 10, total: 0, total_pages: 0 },
    });

    renderStudentTicketsPage();

    await waitFor(() => {
      expect(screen.getByText(/no tickets filed yet/i)).toBeInTheDocument();
    });

    expect(
      screen.getByRole('button', { name: /report your first issue/i })
    ).toBeInTheDocument();
  });

  it('displays error alert with retry button when API fails', async () => {
    const user = userEvent.setup();
    const listSpy = vi
      .spyOn(ticketsApi, 'listTickets')
      .mockRejectedValueOnce(new Error('Network error loading tickets.'))
      .mockResolvedValueOnce(mockResponse);

    renderStudentTicketsPage();

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(
        screen.getByText('Network error loading tickets.')
      ).toBeInTheDocument();
    });

    const retryBtn = screen.getByRole('button', { name: /retry request/i });
    await user.click(retryBtn);

    await waitFor(() => {
      expect(screen.getAllByText('CFX-2026-00042').length).toBeGreaterThanOrEqual(1);
    });
    expect(listSpy).toHaveBeenCalledTimes(2);
  });

  it('navigates to /tickets/:id (UUID) when row is clicked', async () => {
    const user = userEvent.setup();
    vi.spyOn(ticketsApi, 'listTickets').mockResolvedValue(mockResponse);

    renderStudentTicketsPage();

    await waitFor(() => {
      expect(screen.getAllByText('CFX-2026-00042').length).toBeGreaterThanOrEqual(1);
    });

    const firstRowText = screen.getAllByText('Projector HDMI Bent in Room 402')[0];
    await user.click(firstRowText);

    await waitFor(() => {
      expect(screen.getByText('Ticket Detail UUID View')).toBeInTheDocument();
    });
  });
});
