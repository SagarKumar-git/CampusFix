/**
 * CampusFix State Transition Modals Component Tests (SCR-06)
 *
 * Verifies:
 * - Modal rendering across action types
 * - Commentary threshold validation (min 10 chars for RESOLVE, REJECT, REOPEN)
 * - Assignee UUID format validation for ASSIGN
 * - Submitting correct expected_version for optimistic concurrency
 * - Duplicate submission prevention
 * - HTTP 409 concurrency conflict handling
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../src/api/client';
import { ticketsApi } from '../../src/api/tickets';
import {
  TicketTransitionModals,
  type TransitionActionType,
} from '../../src/pages/tickets/components/TicketTransitionModals';
import type { Ticket } from '../../src/types';

const mockTicket: Ticket = {
  id: 'a0000000-0000-0000-0000-000000000001',
  ticket_number: 'CFX-2026-00042',
  title: 'Projector HDMI Bent in Room 402',
  description: 'The wall-mounted HDMI plate has bent pins preventing laptop display output.',
  category: { id: 'c0000000-0000-0000-0000-000000000001', name: 'Classroom Audio-Visual' },
  location: 'Science Block A, Room 402',
  priority: 'HIGH',
  status: 'IN_PROGRESS',
  creator: { id: 'u0000000-0000-0000-0000-000000000001', full_name: 'Alex Student' },
  assigned_staff: { id: 'u0000000-0000-0000-0000-000000000002', full_name: 'Jordan Tech' },
  resolution_notes: null,
  rejection_reason: null,
  version: 3,
  created_at: '2026-11-01T10:00:00Z',
  updated_at: '2026-11-01T11:00:00Z',
};

describe('SCR-06: TicketTransitionModals Component', () => {
  const currentUserId = 'u0000000-0000-0000-0000-000000000002';
  let onCloseMock: () => void;
  let onSuccessMock: () => void;
  let onConcurrencyConflictMock: (err: ApiError) => void;

  beforeEach(() => {
    vi.clearAllMocks();
    onCloseMock = vi.fn();
    onSuccessMock = vi.fn();
    onConcurrencyConflictMock = vi.fn();
  });

  const renderModal = (action: TransitionActionType, ticketOverride: Partial<Ticket> = {}) => {
    const ticket = { ...mockTicket, ...ticketOverride };
    return render(
      <TicketTransitionModals
        action={action}
        onClose={onCloseMock}
        ticket={ticket}
        currentUserId={currentUserId}
        onSuccess={onSuccessMock}
        onConcurrencyConflict={onConcurrencyConflictMock}
      />
    );
  };

  it('renders RESOLVE modal and validates minimum 10 characters resolution notes', async () => {
    const user = userEvent.setup();
    const transitionSpy = vi.spyOn(ticketsApi, 'transitionTicket').mockResolvedValue({
      id: mockTicket.id,
      ticket_number: mockTicket.ticket_number,
      status: 'RESOLVED',
      resolution_notes: 'Replaced HDMI socket plate and verified 1080p display.',
      rejection_reason: null,
      version: 4,
      updated_at: '2026-11-01T12:00:00Z',
    });

    renderModal('RESOLVE');

    expect(screen.getByRole('heading', { name: /mark incident as resolved/i })).toBeInTheDocument();

    const submitBtn = screen.getByRole('button', { name: /confirm & mark resolved/i });
    await user.click(submitBtn);

    // Error for empty notes
    expect(screen.getByText('Resolution notes are required.')).toBeInTheDocument();
    expect(transitionSpy).not.toHaveBeenCalled();

    // Error for too short (< 10 chars)
    const textarea = screen.getByLabelText(/resolution actions taken/i);
    await user.type(textarea, 'Short');
    await user.click(submitBtn);
    expect(screen.getByText('Resolution notes must be at least 10 characters.')).toBeInTheDocument();
    expect(transitionSpy).not.toHaveBeenCalled();

    // Valid submission >= 10 chars
    await user.clear(textarea);
    await user.type(textarea, 'Replaced HDMI socket plate and verified 1080p display.');
    await user.click(submitBtn);

    await waitFor(() => {
      expect(transitionSpy).toHaveBeenCalledWith(mockTicket.id, {
        target_status: 'RESOLVED',
        notes: 'Replaced HDMI socket plate and verified 1080p display.',
        expected_version: 3,
      });
      expect(onSuccessMock).toHaveBeenCalledTimes(1);
    });
  });

  it('renders REJECT modal and enforces minimum 10 characters rejection justification', async () => {
    const user = userEvent.setup();
    const transitionSpy = vi.spyOn(ticketsApi, 'transitionTicket').mockResolvedValue({
      id: mockTicket.id,
      ticket_number: mockTicket.ticket_number,
      status: 'REJECTED',
      resolution_notes: null,
      rejection_reason: 'Equipment belongs to private contractor, not campus facility.',
      version: 4,
      updated_at: '2026-11-01T12:00:00Z',
    });

    renderModal('REJECT', { status: 'SUBMITTED', version: 1 });

    expect(screen.getByRole('heading', { name: /reject facility issue/i })).toBeInTheDocument();

    const submitBtn = screen.getByRole('button', { name: /confirm rejection/i });
    const textarea = screen.getByLabelText(/rejection justification/i);

    await user.type(textarea, 'No fix');
    await user.click(submitBtn);
    expect(screen.getByText('Rejection reason must be at least 10 characters.')).toBeInTheDocument();
    expect(transitionSpy).not.toHaveBeenCalled();

    await user.clear(textarea);
    await user.type(textarea, 'Equipment belongs to private contractor, not campus facility.');
    await user.click(submitBtn);

    await waitFor(() => {
      expect(transitionSpy).toHaveBeenCalledWith(mockTicket.id, {
        target_status: 'REJECTED',
        notes: 'Equipment belongs to private contractor, not campus facility.',
        expected_version: 1,
      });
      expect(onSuccessMock).toHaveBeenCalledTimes(1);
    });
  });

  it('submits CLAIM request with staff_id and expected_version', async () => {
    const user = userEvent.setup();
    const assignSpy = vi.spyOn(ticketsApi, 'assignTicket').mockResolvedValue({
      id: mockTicket.id,
      ticket_number: mockTicket.ticket_number,
      status: 'ASSIGNED',
      assigned_staff_id: currentUserId,
      version: 2,
      updated_at: '2026-11-01T10:30:00Z',
    });

    renderModal('CLAIM', { status: 'SUBMITTED', version: 1 });

    expect(screen.getByRole('heading', { name: /claim maintenance ticket/i })).toBeInTheDocument();

    const submitBtn = screen.getByRole('button', { name: /claim ticket/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(assignSpy).toHaveBeenCalledWith(mockTicket.id, {
        staff_id: currentUserId,
        expected_version: 1,
      });
      expect(onSuccessMock).toHaveBeenCalledTimes(1);
    });
  });

  it('submits ASSIGN request with validated staff UUID', async () => {
    const user = userEvent.setup();
    const validStaffUuid = '99999999-8888-7777-6666-555555555555';
    const assignSpy = vi.spyOn(ticketsApi, 'assignTicket').mockResolvedValue({
      id: mockTicket.id,
      ticket_number: mockTicket.ticket_number,
      status: 'ASSIGNED',
      assigned_staff_id: validStaffUuid,
      version: 2,
      updated_at: '2026-11-01T10:30:00Z',
    });

    renderModal('ASSIGN', { status: 'SUBMITTED', version: 1 });

    const submitBtn = screen.getByRole('button', { name: /assign technician/i });
    const input = screen.getByLabelText(/staff technician uuid/i);

    // Non-UUID invalid string
    await user.type(input, 'not-a-valid-uuid');
    await user.click(submitBtn);
    expect(screen.getByText('Staff ID must be a valid UUID.')).toBeInTheDocument();
    expect(assignSpy).not.toHaveBeenCalled();

    // Valid UUID
    await user.clear(input);
    await user.type(input, validStaffUuid);
    await user.click(submitBtn);

    await waitFor(() => {
      expect(assignSpy).toHaveBeenCalledWith(mockTicket.id, {
        staff_id: validStaffUuid,
        expected_version: 1,
      });
      expect(onSuccessMock).toHaveBeenCalledTimes(1);
    });
  });

  it('submits REOPEN request with target status, reason, and expected version', async () => {
    const user = userEvent.setup();
    const transitionSpy = vi.spyOn(ticketsApi, 'transitionTicket').mockResolvedValue({
      id: mockTicket.id,
      ticket_number: mockTicket.ticket_number,
      status: 'ASSIGNED',
      resolution_notes: null,
      rejection_reason: null,
      version: 5,
      updated_at: '2026-11-01T13:00:00Z',
    });

    renderModal('REOPEN', { status: 'RESOLVED', version: 4 });

    expect(screen.getByRole('heading', { name: /reopen maintenance ticket/i })).toBeInTheDocument();

    const textarea = screen.getByLabelText(/reopening justification/i);
    await user.type(textarea, 'Projector flickering again during afternoon seminar session.');

    const submitBtn = screen.getByRole('button', { name: /reopen ticket/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(transitionSpy).toHaveBeenCalledWith(mockTicket.id, {
        target_status: 'ASSIGNED',
        notes: 'Projector flickering again during afternoon seminar session.',
        assigned_staff_id: null,
        expected_version: 4,
      });
      expect(onSuccessMock).toHaveBeenCalledTimes(1);
    });
  });

  it('handles HTTP 409 concurrency conflict by delegating to onConcurrencyConflict and closing modal', async () => {
    const user = userEvent.setup();
    const conflictError = new ApiError(
      409,
      'CONCURRENCY_CONFLICT',
      'Ticket version conflict: expected 3, but ticket is at version 4.',
      { expected_version: 3, actual_version: 4 }
    );
    vi.spyOn(ticketsApi, 'transitionTicket').mockRejectedValue(conflictError);

    renderModal('RESOLVE', { version: 3 });

    const textarea = screen.getByLabelText(/resolution actions taken/i);
    await user.type(textarea, 'Replaced HDMI plate and tested display output.');

    const submitBtn = screen.getByRole('button', { name: /confirm & mark resolved/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(onConcurrencyConflictMock).toHaveBeenCalledWith(conflictError);
      expect(onCloseMock).toHaveBeenCalled();
      expect(onSuccessMock).not.toHaveBeenCalled();
    });
  });

  it('displays API error banner when request fails with non-conflict error', async () => {
    const user = userEvent.setup();
    vi.spyOn(ticketsApi, 'transitionTicket').mockRejectedValue(
      new Error('Forbidden: only assigned staff can resolve ticket.')
    );

    renderModal('RESOLVE', { version: 3 });

    const textarea = screen.getByLabelText(/resolution actions taken/i);
    await user.type(textarea, 'Replaced HDMI plate and tested display output.');

    const submitBtn = screen.getByRole('button', { name: /confirm & mark resolved/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(
        screen.getByText('Forbidden: only assigned staff can resolve ticket.')
      ).toBeInTheDocument();
      expect(onCloseMock).not.toHaveBeenCalled();
      expect(onSuccessMock).not.toHaveBeenCalled();
    });
  });
});
