/**
 * CampusFix Ticket Detail View & Audit History (SCR-04)
 *
 * Implements:
 * - Detailed incident view for maintenance tickets
 * - Direct UUID route navigation (/tickets/:id)
 * - Prominent human-readable reference code (CFX-YYYY-XXXXX)
 * - Metadata grid: Category, Location, Priority, Status, Creator, Assignee, Timestamps
 * - Chronological Audit Timeline from GET /api/v1/tickets/{id}/history
 * - Role-governed action triggers based on FSM rules
 * - Optimistic concurrency conflict (HTTP 409) handling & automatic state reload
 * - Accessible loading skeletons, error alerts with retry, and back navigation
 */

import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ApiError } from '../../api/client';
import { ticketsApi } from '../../api/tickets';
import { AlertBanner } from '../../components/ui/AlertBanner';
import { PriorityBadge, StatusBadge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Skeleton } from '../../components/ui/Skeleton';
import { ChevronLeftIcon } from '../../components/ui/icons';
import { useAuth } from '../../context';
import type { Ticket, TicketHistoryItem } from '../../types';
import { TicketAuditTimeline } from './components/TicketAuditTimeline';
import {
  TicketTransitionModals,
  type TransitionActionType,
} from './components/TicketTransitionModals';

const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const TicketDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [history, setHistory] = useState<TicketHistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [concurrencyAlert, setConcurrencyAlert] = useState<string | null>(null);
  const [activeModal, setActiveModal] = useState<TransitionActionType | null>(null);

  const fetchTicketAndHistory = useCallback(
    async (ticketId: string) => {
      setIsLoading(true);
      setError(null);
      try {
        const [ticketData, historyData] = await Promise.all([
          ticketsApi.getTicket(ticketId),
          ticketsApi.getTicketHistory(ticketId),
        ]);
        setTicket(ticketData);
        setHistory(historyData);
      } catch (err: unknown) {
        if (err instanceof ApiError) {
          if (err.status === 404) {
            setError(
              'Ticket not found or you do not have permission to view this maintenance record.'
            );
          } else if (err.status === 403) {
            setError(
              'You lack authorization to access this ticket record.'
            );
          } else {
            setError(err.message || 'Failed to retrieve ticket details.');
          }
        } else {
          setError('A network error occurred while retrieving ticket details.');
        }
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    if (!id || !UUID_REGEX.test(id)) {
      setError(
        'Invalid ticket identifier format. The requested ticket URL must contain a valid UUID.'
      );
      setIsLoading(false);
      return;
    }

    fetchTicketAndHistory(id);
  }, [id, fetchTicketAndHistory]);

  const handleBack = () => {
    if (!user) {
      navigate('/login');
      return;
    }
    if (user.role === 'STUDENT') {
      navigate('/student/tickets');
    } else if (user.role === 'STAFF') {
      navigate('/staff/queue');
    } else {
      navigate('/admin/categories');
    }
  };

  const handleConcurrencyConflict = (conflictError: ApiError) => {
    const details = conflictError.details as
      | { expected_version?: number; actual_version?: number }
      | undefined;
    const msg = details?.actual_version
      ? `Concurrency Conflict: This ticket was updated by another user (expected version ${details.expected_version}, actual is ${details.actual_version}). The latest ticket details and audit trail have been reloaded. Please review the updated status before continuing.`
      : 'Concurrency Conflict: This ticket was updated in another session. The latest ticket details have been reloaded. Please review the updated status before continuing.';

    setConcurrencyAlert(msg);
    if (id) {
      fetchTicketAndHistory(id);
    }
  };

  const handleTransitionSuccess = () => {
    setConcurrencyAlert(null);
    if (id) {
      fetchTicketAndHistory(id);
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto space-y-6" aria-busy="true">
        <div className="flex items-center justify-between">
          <Skeleton variant="rect" className="w-24 h-9" />
          <Skeleton variant="rect" className="w-32 h-9" />
        </div>
        <div className="bg-white p-6 rounded-lg border border-slate-200 space-y-4">
          <Skeleton variant="text" className="w-1/4 h-8" />
          <Skeleton variant="text" className="w-1/2 h-6" />
          <Skeleton variant="rect" className="w-full h-32" />
        </div>
      </div>
    );
  }

  if (error || !ticket) {
    return (
      <div className="max-w-3xl mx-auto space-y-6 py-8">
        <AlertBanner
          variant="error"
          title="Unable to Display Ticket"
        >
          {error || 'Ticket record could not be loaded.'}
        </AlertBanner>
        <div className="flex items-center gap-3">
          <Button variant="secondary" onClick={handleBack}>
            Return to Dashboard
          </Button>
          {id && UUID_REGEX.test(id) && (
            <Button
              variant="primary"
              onClick={() => fetchTicketAndHistory(id)}
            >
              Retry Request
            </Button>
          )}
        </div>
      </div>
    );
  }

  // Determine allowed transitions based on role, status, creator, and assignee
  const isCreator = user?.id === ticket.creator.id;
  const isAssignee = user?.id === ticket.assigned_staff?.id;
  const role = user?.role;

  const canCancel =
    (ticket.status === 'SUBMITTED' || ticket.status === 'ASSIGNED') &&
    isCreator &&
    role === 'STUDENT';

  const canClaim =
    ticket.status === 'SUBMITTED' &&
    (role === 'STAFF' || role === 'ADMINISTRATOR');

  const canAssign =
    (ticket.status === 'SUBMITTED' || ticket.status === 'ASSIGNED') &&
    role === 'ADMINISTRATOR';

  const canStartWork =
    ticket.status === 'ASSIGNED' && (isAssignee || role === 'ADMINISTRATOR');

  const canPauseWork =
    ticket.status === 'IN_PROGRESS' && (isAssignee || role === 'ADMINISTRATOR');

  const canResolve =
    ticket.status === 'IN_PROGRESS' && (isAssignee || role === 'ADMINISTRATOR');

  const canReject =
    ((ticket.status === 'SUBMITTED' || ticket.status === 'ASSIGNED') &&
      (role === 'STAFF' || role === 'ADMINISTRATOR')) ||
    (ticket.status === 'IN_PROGRESS' && role === 'ADMINISTRATOR');

  const canReopen =
    (ticket.status === 'RESOLVED' || ticket.status === 'REJECTED') &&
    role === 'ADMINISTRATOR';

  const formattedCreatedAt = new Date(ticket.created_at).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });

  const formattedUpdatedAt = new Date(ticket.updated_at).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Top back navigation and primary actions */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <button
          type="button"
          onClick={handleBack}
          className="inline-flex items-center text-sm font-medium text-slate-600 hover:text-slate-900 focus:outline-hidden focus-visible:ring-2 focus-visible:ring-primary-500 rounded-md px-2 py-1 -ml-2 transition-colors cursor-pointer"
          aria-label="Back to dashboard"
        >
          <ChevronLeftIcon className="w-5 h-5 mr-1" />
          <span>Back to Dashboard</span>
        </button>

        {/* Action Buttons Toolbar */}
        <div className="flex flex-wrap items-center gap-2">
          {canClaim && (
            <Button
              variant="primary"
              size="sm"
              onClick={() => setActiveModal('CLAIM')}
            >
              Claim Ticket
            </Button>
          )}

          {canAssign && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setActiveModal('ASSIGN')}
            >
              Assign Technician
            </Button>
          )}

          {canStartWork && (
            <Button
              variant="primary"
              size="sm"
              onClick={() => setActiveModal('START_WORK')}
            >
              Start Work
            </Button>
          )}

          {canPauseWork && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setActiveModal('PAUSE_WORK')}
            >
              Pause Work
            </Button>
          )}

          {canResolve && (
            <Button
              variant="primary"
              size="sm"
              onClick={() => setActiveModal('RESOLVE')}
            >
              Resolve Ticket
            </Button>
          )}

          {canReject && (
            <Button
              variant="danger"
              size="sm"
              onClick={() => setActiveModal('REJECT')}
            >
              Reject Ticket
            </Button>
          )}

          {canCancel && (
            <Button
              variant="danger"
              size="sm"
              onClick={() => setActiveModal('CANCEL')}
            >
              Cancel Ticket
            </Button>
          )}

          {canReopen && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setActiveModal('REOPEN')}
            >
              Reopen Ticket
            </Button>
          )}
        </div>
      </div>

      {/* Concurrency Conflict Notification Alert */}
      {concurrencyAlert && (
        <AlertBanner
          variant="warning"
          title="Ticket State Synchronized"
          onDismiss={() => setConcurrencyAlert(null)}
        >
          {concurrencyAlert}
        </AlertBanner>
      )}

      {/* Main Ticket Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Main Incident Breakdown & Audit Timeline */}
        <div className="lg:col-span-2 space-y-6">
          {/* Main Incident Details Card */}
          <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-xs space-y-5">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded-sm bg-slate-100 text-slate-700">
                  {ticket.ticket_number}
                </span>
                <StatusBadge status={ticket.status} />
                <PriorityBadge priority={ticket.priority} />
                <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded-sm">
                  v{ticket.version}
                </span>
              </div>
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                {ticket.title}
              </h1>
            </div>

            {/* Description */}
            <div className="space-y-1.5">
              <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Incident Description
              </h2>
              <p className="text-sm text-slate-800 whitespace-pre-wrap leading-relaxed bg-slate-50 p-4 rounded-md border border-slate-200">
                {ticket.description}
              </p>
            </div>

            {/* Resolution Notes Callout */}
            {ticket.resolution_notes && (
              <div className="bg-emerald-50 border-l-4 border-emerald-500 p-4 rounded-r-md space-y-1">
                <h2 className="text-xs font-semibold text-emerald-900 uppercase tracking-wider">
                  Resolution Summary
                </h2>
                <p className="text-sm text-emerald-800 whitespace-pre-wrap leading-relaxed">
                  {ticket.resolution_notes}
                </p>
              </div>
            )}

            {/* Rejection Reason Callout */}
            {ticket.rejection_reason && (
              <div className="bg-rose-50 border-l-4 border-rose-500 p-4 rounded-r-md space-y-1">
                <h2 className="text-xs font-semibold text-rose-900 uppercase tracking-wider">
                  Rejection Reason
                </h2>
                <p className="text-sm text-rose-800 whitespace-pre-wrap leading-relaxed">
                  {ticket.rejection_reason}
                </p>
              </div>
            )}
          </div>

          {/* Audit History Timeline Card */}
          <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-xs space-y-4">
            <div className="border-b border-slate-200 pb-3">
              <h2 className="text-lg font-bold text-slate-900">
                Audit Trail & History
              </h2>
              <p className="text-xs text-slate-500">
                Immutable, chronological log of all status transitions and staff assignments.
              </p>
            </div>
            <TicketAuditTimeline history={history} />
          </div>
        </div>

        {/* Right 1 Col: Ticket Information Metadata Panel */}
        <div className="space-y-6">
          <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-xs space-y-4">
            <h2 className="text-base font-bold text-slate-900 border-b border-slate-200 pb-3">
              Ticket Details
            </h2>

            <dl className="divide-y divide-slate-100 text-sm">
              <div className="py-2.5 flex justify-between gap-2">
                <dt className="text-slate-500 font-medium">Ticket Code</dt>
                <dd className="font-mono text-slate-900 font-semibold text-right">
                  {ticket.ticket_number}
                </dd>
              </div>

              <div className="py-2.5 flex justify-between gap-2">
                <dt className="text-slate-500 font-medium">Facility Category</dt>
                <dd className="text-slate-900 font-medium text-right">
                  {ticket.category.name}
                </dd>
              </div>

              <div className="py-2.5 flex justify-between gap-2">
                <dt className="text-slate-500 font-medium">Location</dt>
                <dd className="text-slate-900 font-medium text-right">
                  {ticket.location}
                </dd>
              </div>

              <div className="py-2.5 flex justify-between gap-2">
                <dt className="text-slate-500 font-medium">Urgency Tier</dt>
                <dd className="text-right">
                  <PriorityBadge priority={ticket.priority} />
                </dd>
              </div>

              <div className="py-2.5 flex justify-between gap-2">
                <dt className="text-slate-500 font-medium">Current Status</dt>
                <dd className="text-right">
                  <StatusBadge status={ticket.status} />
                </dd>
              </div>

              <div className="py-2.5 flex justify-between gap-2">
                <dt className="text-slate-500 font-medium">Reported By</dt>
                <dd className="text-slate-900 font-medium text-right">
                  {ticket.creator.full_name}
                </dd>
              </div>

              <div className="py-2.5 flex justify-between gap-2">
                <dt className="text-slate-500 font-medium">Assigned Staff</dt>
                <dd className="text-slate-900 font-medium text-right">
                  {ticket.assigned_staff ? (
                    <span className="text-slate-900 font-medium">
                      {ticket.assigned_staff.full_name}
                    </span>
                  ) : (
                    <span className="text-slate-400 italic">Unassigned</span>
                  )}
                </dd>
              </div>

              <div className="py-2.5 flex justify-between gap-2">
                <dt className="text-slate-500 font-medium">FSM Version</dt>
                <dd className="text-slate-700 font-mono text-right">
                  v{ticket.version}
                </dd>
              </div>

              <div className="py-2.5 flex justify-between gap-2">
                <dt className="text-slate-500 font-medium">Date Submitted</dt>
                <dd className="text-slate-700 text-xs text-right">
                  {formattedCreatedAt}
                </dd>
              </div>

              <div className="py-2.5 flex justify-between gap-2">
                <dt className="text-slate-500 font-medium">Last Activity</dt>
                <dd className="text-slate-700 text-xs text-right">
                  {formattedUpdatedAt}
                </dd>
              </div>
            </dl>
          </div>
        </div>
      </div>

      {/* State Transition Modals */}
      {activeModal && (
        <TicketTransitionModals
          action={activeModal}
          onClose={() => setActiveModal(null)}
          ticket={ticket}
          currentUserId={user?.id || ''}
          onSuccess={handleTransitionSuccess}
          onConcurrencyConflict={handleConcurrencyConflict}
        />
      )}
    </div>
  );
};

export default TicketDetailPage;
