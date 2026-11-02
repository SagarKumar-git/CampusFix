import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { categoriesApi } from '../../src/api/categories';
import { ticketsApi } from '../../src/api/tickets';
import TicketCreatePage from '../../src/pages/tickets/TicketCreatePage';
import type { Category, Ticket } from '../../src/types';

describe('SCR-03: TicketCreatePage', () => {
  const mockCategories: Category[] = [
    {
      id: 'cat-av-1',
      name: 'Classroom Audio-Visual',
      description: 'Projectors, microphones, and screens',
      is_active: true,
    },
    {
      id: 'cat-elec-2',
      name: 'Electrical & Lighting',
      description: 'Power outlets and lighting',
      is_active: true,
    },
  ];

  const renderTicketCreatePage = () => {
    return render(
      <MemoryRouter initialEntries={['/tickets/new']}>
        <Routes>
          <Route path="/tickets/new" element={<TicketCreatePage />} />
          <Route
            path="/tickets/:id"
            element={<div>Ticket Detail Created View</div>}
          />
          <Route
            path="/student/tickets"
            element={<div>My Tickets Dashboard</div>}
          />
        </Routes>
      </MemoryRouter>
    );
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('loads facility categories from API into the category dropdown', async () => {
    vi.spyOn(categoriesApi, 'listCategories').mockResolvedValue(mockCategories);

    renderTicketCreatePage();

    await waitFor(() => {
      expect(
        screen.getByRole('option', { name: 'Classroom Audio-Visual' })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('option', { name: 'Electrical & Lighting' })
      ).toBeInTheDocument();
    });
  });

  it('validates required fields and minimum string lengths', async () => {
    const user = userEvent.setup();
    vi.spyOn(categoriesApi, 'listCategories').mockResolvedValue(mockCategories);

    renderTicketCreatePage();

    await waitFor(() => {
      expect(
        screen.getByRole('option', { name: 'Classroom Audio-Visual' })
      ).toBeInTheDocument();
    });

    // Try submitting empty
    await user.click(screen.getByRole('button', { name: /submit work order/i }));

    expect(screen.getByText('Title is required.')).toBeInTheDocument();
    expect(screen.getByText('Description is required.')).toBeInTheDocument();
    expect(screen.getByText('Campus location is required.')).toBeInTheDocument();

    // Fill with too short inputs
    await user.type(screen.getByLabelText(/issue headline/i), 'Fix');
    await user.type(screen.getByLabelText(/detailed description/i), 'Broken');
    await user.type(screen.getByLabelText(/campus location/i), 'R1');
    await user.click(screen.getByRole('button', { name: /submit work order/i }));

    expect(
      screen.getByText('Title must be at least 5 characters in length.')
    ).toBeInTheDocument();
    expect(
      screen.getByText(/description must be at least 10 characters/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/location must be at least 3 characters/i)
    ).toBeInTheDocument();
  });

  it('submits valid ticket and redirects to /tickets/:id with newly created ticket UUID', async () => {
    const user = userEvent.setup();
    vi.spyOn(categoriesApi, 'listCategories').mockResolvedValue(mockCategories);

    const createdTicket: Ticket = {
      id: '990e8400-e29b-41d4-a716-446655440099',
      ticket_number: 'CFX-2026-00099',
      title: 'Lab Fume Hood Alarm Beeping Continuously',
      description: 'The velocity sensor airflow warning is triggering every 30 seconds.',
      category: { id: 'cat-elec-2', name: 'Electrical & Lighting' },
      location: 'Chemistry Block C, Room 204',
      priority: 'HIGH',
      status: 'SUBMITTED',
      creator: { id: 'student-1', full_name: 'Student Name' },
      assigned_staff: null,
      resolution_notes: null,
      rejection_reason: null,
      version: 1,
      created_at: '2026-11-01T15:00:00Z',
      updated_at: '2026-11-01T15:00:00Z',
    };

    const createSpy = vi.spyOn(ticketsApi, 'createTicket').mockResolvedValue(createdTicket);

    renderTicketCreatePage();

    await waitFor(() => {
      expect(
        screen.getByRole('option', { name: 'Classroom Audio-Visual' })
      ).toBeInTheDocument();
    });

    await user.type(
      screen.getByLabelText(/issue headline/i),
      'Lab Fume Hood Alarm Beeping Continuously'
    );
    await user.type(
      screen.getByLabelText(/detailed description/i),
      'The velocity sensor airflow warning is triggering every 30 seconds.'
    );
    await user.type(
      screen.getByLabelText(/campus location/i),
      'Chemistry Block C, Room 204'
    );

    // Select Priority High
    await user.selectOptions(
      screen.getByLabelText(/priority \/ urgency tier/i),
      'HIGH'
    );

    // Select Category
    await user.selectOptions(
      screen.getByLabelText(/issue category/i),
      'cat-elec-2'
    );

    await user.click(screen.getByRole('button', { name: /submit work order/i }));

    expect(createSpy).toHaveBeenCalledWith({
      title: 'Lab Fume Hood Alarm Beeping Continuously',
      description: 'The velocity sensor airflow warning is triggering every 30 seconds.',
      location: 'Chemistry Block C, Room 204',
      category_id: 'cat-elec-2',
      priority: 'HIGH',
    });

    await waitFor(() => {
      expect(screen.getByText('Ticket Detail Created View')).toBeInTheDocument();
    });
  });

  it('displays API error alert when submission fails', async () => {
    const user = userEvent.setup();
    vi.spyOn(categoriesApi, 'listCategories').mockResolvedValue(mockCategories);
    vi.spyOn(ticketsApi, 'createTicket').mockRejectedValue(
      new Error('Facility category is currently inactive.')
    );

    renderTicketCreatePage();

    await waitFor(() => {
      expect(
        screen.getByRole('option', { name: 'Classroom Audio-Visual' })
      ).toBeInTheDocument();
    });

    await user.type(
      screen.getByLabelText(/issue headline/i),
      'Valid Issue Title'
    );
    await user.type(
      screen.getByLabelText(/detailed description/i),
      'Detailed contextual description of malfunction.'
    );
    await user.type(
      screen.getByLabelText(/campus location/i),
      'Science Block Room 101'
    );

    await user.click(screen.getByRole('button', { name: /submit work order/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(
        screen.getByText('Facility category is currently inactive.')
      ).toBeInTheDocument();
    });
  });
});
