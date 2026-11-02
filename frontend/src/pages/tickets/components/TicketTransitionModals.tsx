/**
 * CampusFix State Transition & Action Modals (SCR-06)
 *
 * Implements accessible action dialogs for ticket lifecycle transitions:
 * - Cancel Ticket (Student creator or Admin)
 * - Claim Ticket (Self-assignment for Staff/Admin)
 * - Assign Technician (Admin assignment to staff UUID)
 * - Start Work (Assigned staff or Admin moving to IN_PROGRESS)
 * - Pause Work (Moving back to ASSIGNED)
 * - Resolve Ticket (Mandatory resolution notes >= 10 chars)
 * - Reject Ticket (Mandatory rejection reason >= 10 chars)
 * - Reopen Ticket (Admin reopening to ASSIGNED/SUBMITTED with reason >= 10 chars)
 *
 * Enforces:
 * - Minimum character commentary thresholds
 * - Optimistic concurrency verification using ticket.version
 * - HTTP 409 CONCURRENCY_CONFLICT handling and auto-recovery delegation
 * - Keyboard focus trapping and restoration via Modal component
 */

import React, { useState } from 'react';
import { ApiError } from '../../../api/client';
import { ticketsApi } from '../../../api/tickets';
import { AlertBanner } from '../../../components/ui/AlertBanner';
import { Button } from '../../../components/ui/Button';
import { Input } from '../../../components/ui/Input';
import { Modal } from '../../../components/ui/Modal';
import { Select } from '../../../components/ui/Select';
import { Textarea } from '../../../components/ui/Textarea';
import type { Ticket, TicketStatus } from '../../../types';

export type TransitionActionType =
  | 'CANCEL'
  | 'CLAIM'
  | 'ASSIGN'
  | 'START_WORK'
  | 'PAUSE_WORK'
  | 'RESOLVE'
  | 'REJECT'
  | 'REOPEN';

export interface TicketTransitionModalsProps {
  action: TransitionActionType | null;
  onClose: () => void;
  ticket: Ticket;
  currentUserId: string;
  onSuccess: () => void;
  onConcurrencyConflict: (error: ApiError) => void;
}

export const TicketTransitionModals: React.FC<TicketTransitionModalsProps> = ({
  action,
  onClose,
  ticket,
  currentUserId,
  onSuccess,
  onConcurrencyConflict,
}) => {
  const [notes, setNotes] = useState('');
  const [staffId, setStaffId] = useState('');
  const [reopenTargetStatus, setReopenTargetStatus] = useState<TicketStatus>('ASSIGNED');
  const [reopenStaffId, setReopenStaffId] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Reset local state when modal closes
  const handleClose = () => {
    if (isSubmitting) return; // Prevent closing while request in-flight
    setNotes('');
    setStaffId('');
    setReopenTargetStatus('ASSIGNED');
    setReopenStaffId('');
    setFieldErrors({});
    setApiError(null);
    onClose();
  };

  const validate = (): boolean => {
    const errors: Record<string, string> = {};
    const trimmedNotes = notes.trim();

    if (action === 'RESOLVE') {
      if (!trimmedNotes) {
        errors.notes = 'Resolution notes are required.';
      } else if (trimmedNotes.length < 10) {
        errors.notes = 'Resolution notes must be at least 10 characters.';
      }
    } else if (action === 'REJECT') {
      if (!trimmedNotes) {
        errors.notes = 'Rejection reason is required.';
      } else if (trimmedNotes.length < 10) {
        errors.notes = 'Rejection reason must be at least 10 characters.';
      }
    } else if (action === 'REOPEN') {
      if (!trimmedNotes) {
        errors.notes = 'Reopening reason is required.';
      } else if (trimmedNotes.length < 10) {
        errors.notes = 'Reopening reason must be at least 10 characters.';
      }
      if (reopenTargetStatus === 'ASSIGNED' && reopenStaffId.trim()) {
        const uuidRegex =
          /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
        if (!uuidRegex.test(reopenStaffId.trim())) {
          errors.reopenStaffId = 'Staff ID must be a valid UUID.';
        }
      }
    } else if (action === 'ASSIGN') {
      const trimmedStaffId = staffId.trim();
      if (!trimmedStaffId) {
        errors.staffId = 'Staff technician UUID is required.';
      } else {
        const uuidRegex =
          /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
        if (!uuidRegex.test(trimmedStaffId)) {
          errors.staffId = 'Staff ID must be a valid UUID.';
        }
      }
    } else if (action === 'CANCEL' || action === 'PAUSE_WORK') {
      if (trimmedNotes && trimmedNotes.length < 10) {
        errors.notes = 'Notes must be at least 10 characters if provided.';
      }
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;

    if (!validate()) return;

    setIsSubmitting(true);
    setApiError(null);

    try {
      if (action === 'CLAIM') {
        await ticketsApi.assignTicket(ticket.id, {
          staff_id: currentUserId,
          expected_version: ticket.version,
        });
      } else if (action === 'ASSIGN') {
        await ticketsApi.assignTicket(ticket.id, {
          staff_id: staffId.trim(),
          expected_version: ticket.version,
        });
      } else if (action === 'START_WORK') {
        await ticketsApi.transitionTicket(ticket.id, {
          target_status: 'IN_PROGRESS',
          expected_version: ticket.version,
        });
      } else if (action === 'PAUSE_WORK') {
        await ticketsApi.transitionTicket(ticket.id, {
          target_status: 'ASSIGNED',
          notes: notes.trim() || null,
          expected_version: ticket.version,
        });
      } else if (action === 'RESOLVE') {
        await ticketsApi.transitionTicket(ticket.id, {
          target_status: 'RESOLVED',
          notes: notes.trim(),
          expected_version: ticket.version,
        });
      } else if (action === 'REJECT') {
        await ticketsApi.transitionTicket(ticket.id, {
          target_status: 'REJECTED',
          notes: notes.trim(),
          expected_version: ticket.version,
        });
      } else if (action === 'CANCEL') {
        await ticketsApi.transitionTicket(ticket.id, {
          target_status: 'CANCELLED',
          notes: notes.trim() || null,
          expected_version: ticket.version,
        });
      } else if (action === 'REOPEN') {
        await ticketsApi.transitionTicket(ticket.id, {
          target_status: reopenTargetStatus,
          notes: notes.trim(),
          assigned_staff_id: reopenStaffId.trim() || null,
          expected_version: ticket.version,
        });
      }

      handleClose();
      onSuccess();
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 409) {
        // Concurrency conflict detected! Delegate recovery to parent component
        handleClose();
        onConcurrencyConflict(err);
        return;
      }
      const msg =
        err instanceof Error ? err.message : 'An error occurred during state transition.';
      setApiError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!action) return null;

  const modalMeta: Record<
    TransitionActionType,
    {
      title: string;
      description: string;
      confirmText: string;
      variant: 'primary' | 'secondary' | 'danger';
    }
  > = {
    CLAIM: {
      title: 'Claim Maintenance Ticket',
      description:
        'Assign this facility incident to yourself. You will be recorded as the responsible technician.',
      confirmText: 'Claim Ticket',
      variant: 'primary',
    },
    ASSIGN: {
      title: 'Assign Staff Technician',
      description:
        'Select or enter the UUID of the staff technician responsible for executing repairs.',
      confirmText: 'Assign Technician',
      variant: 'primary',
    },
    START_WORK: {
      title: 'Begin Maintenance Work',
      description:
        'Transition ticket to IN_PROGRESS. This confirms you have initiated physical diagnosis or repair.',
      confirmText: 'Start Work',
      variant: 'primary',
    },
    PAUSE_WORK: {
      title: 'Pause Maintenance Work',
      description:
        'Move this ticket back to ASSIGNED if work is temporarily suspended, pending parts, or waiting on access.',
      confirmText: 'Pause Work',
      variant: 'secondary',
    },
    RESOLVE: {
      title: 'Mark Incident as Resolved',
      description:
        'Document the corrective maintenance actions completed to fix this campus facility issue.',
      confirmText: 'Confirm & Mark Resolved',
      variant: 'primary',
    },
    REJECT: {
      title: 'Reject Facility Issue',
      description:
        'Provide a clear administrative justification for rejecting this reported maintenance issue.',
      confirmText: 'Confirm Rejection',
      variant: 'danger',
    },
    CANCEL: {
      title: 'Cancel Maintenance Ticket',
      description:
        'Are you sure you want to cancel this ticket? Cancelled tickets are placed in a permanent terminal state.',
      confirmText: 'Confirm Cancellation',
      variant: 'danger',
    },
    REOPEN: {
      title: 'Reopen Maintenance Ticket',
      description:
        'Administrative reopening returns this ticket to the active queue for further triage or repair.',
      confirmText: 'Reopen Ticket',
      variant: 'primary',
    },
  };

  const currentMeta = modalMeta[action];

  return (
    <Modal
      isOpen={Boolean(action)}
      onClose={handleClose}
      title={currentMeta.title}
      description={currentMeta.description}
      maxWidth="md"
    >
      <form noValidate onSubmit={handleSubmit} className="space-y-4">
        {apiError && (
          <AlertBanner
            variant="error"
            onDismiss={() => setApiError(null)}
          >
            {apiError}
          </AlertBanner>
        )}

        {/* Action-specific input fields */}
        {action === 'ASSIGN' && (
          <Input
            label="Staff Technician UUID"
            id="assignee-uuid"
            required
            placeholder="e.g. 11111111-2222-3333-4444-555555555555"
            value={staffId}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
              setStaffId(e.target.value);
              if (fieldErrors.staffId) {
                setFieldErrors((prev) => ({ ...prev, staffId: '' }));
              }
            }}
            error={fieldErrors.staffId}
            helperText="Enter the UUID of an active staff technician."
            disabled={isSubmitting}
          />
        )}

        {action === 'REOPEN' && (
          <div className="space-y-4">
            <Select
              label="Reopen Destination Status"
              id="reopen-status"
              required
              value={reopenTargetStatus}
              onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
                setReopenTargetStatus(e.target.value as TicketStatus)
              }
              options={[
                { value: 'ASSIGNED', label: 'ASSIGNED (Active Technician Queue)' },
                { value: 'SUBMITTED', label: 'SUBMITTED (Unassigned Triage Queue)' },
              ]}
              disabled={isSubmitting}
            />

            {reopenTargetStatus === 'ASSIGNED' && (
              <Input
                label="Assignee Staff UUID (Optional)"
                id="reopen-staff-id"
                placeholder="Leave blank to retain or reassign later"
                value={reopenStaffId}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                  setReopenStaffId(e.target.value);
                  if (fieldErrors.reopenStaffId) {
                    setFieldErrors((prev) => ({ ...prev, reopenStaffId: '' }));
                  }
                }}
                error={fieldErrors.reopenStaffId}
                disabled={isSubmitting}
              />
            )}
          </div>
        )}

        {/* Notes / Reason field */}
        {(action === 'RESOLVE' ||
          action === 'REJECT' ||
          action === 'REOPEN' ||
          action === 'CANCEL' ||
          action === 'PAUSE_WORK') && (
          <Textarea
            label={
              action === 'RESOLVE'
                ? 'Resolution Actions Taken'
                : action === 'REJECT'
                ? 'Rejection Justification'
                : action === 'REOPEN'
                ? 'Reopening Justification'
                : 'Explanatory Notes (Optional)'
            }
            id="transition-notes"
            required={action === 'RESOLVE' || action === 'REJECT' || action === 'REOPEN'}
            rows={4}
            value={notes}
            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => {
              setNotes(e.target.value);
              if (fieldErrors.notes) {
                setFieldErrors((prev) => ({ ...prev, notes: '' }));
              }
            }}
            placeholder={
              action === 'RESOLVE'
                ? 'Describe repairs performed, replaced components, and operational test results...'
                : action === 'REJECT'
                ? 'Explain why this incident cannot be serviced or was filed in error...'
                : action === 'REOPEN'
                ? 'Explain why this incident requires further maintenance or follow-up...'
                : 'Add any optional notes regarding this cancellation or work order pause...'
            }
            error={fieldErrors.notes}
            minChars={
              action === 'RESOLVE' || action === 'REJECT' || action === 'REOPEN'
                ? 10
                : undefined
            }
            maxLength={2000}
            showCount={true}
            disabled={isSubmitting}
          />
        )}

        {/* Modal actions footer */}
        <div className="flex items-center justify-end space-x-3 pt-4 border-t border-slate-200">
          <Button
            type="button"
            variant="ghost"
            onClick={handleClose}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant={currentMeta.variant}
            isLoading={isSubmitting}
          >
            {currentMeta.confirmText}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
