/**
 * CampusFix SCR-05: Staff Workbench Queue & Work Execution
 *
 * Implements:
 * - High-efficiency operational workbench for maintenance staff
 * - Two workbench views: "Assigned to Me" (ASSIGNED, IN_PROGRESS) and "Unassigned Queue" (SUBMITTED)
 * - Quick-claim action for unassigned tickets with optimistic concurrency control (expected_version)
 * - Quick "Start Work" action for assigned work orders (transition to IN_PROGRESS)
 * - Filter controls: Category select, Priority select, Sorting (Newest, Oldest, Priority)
 * - Concurrency conflict (HTTP 409) handling with alert banner and queue refresh
 * - Contextual empty states, loading skeletons, error states with retry, and pagination
 * - Row navigation to /tickets/:id (UUID)
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { categoriesApi } from '../../api/categories';
import { ApiError } from '../../api/client';
import { ticketsApi } from '../../api/tickets';
import { AlertBanner } from '../../components/ui/AlertBanner';
import { PriorityBadge, StatusBadge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { type Column, DataTable } from '../../components/ui/DataTable';
import { PaginationBar } from '../../components/ui/PaginationBar';
import { Select } from '../../components/ui/Select';
import { useAuth } from '../../context';
import type {
  Category,
  PaginationMeta,
  TicketPriority,
  TicketSummary,
} from '../../types';

export type StaffQueueTab = 'ASSIGNED' | 'UNASSIGNED';
export type SortOption = 'NEWEST' | 'OLDEST' | 'PRIORITY';

const PRIORITY_WEIGHT: Record<TicketPriority, number> = {
  CRITICAL: 4,
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
};

export const StaffQueuePage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();

  // Tab state
  const [activeTab, setActiveTab] = useState<StaffQueueTab>('ASSIGNED');

  // Queue data & pagination
  const [tickets, setTickets] = useState<TicketSummary[]>([]);
  const [meta, setMeta] = useState<PaginationMeta>({
    page: 1,
    page_size: 10,
    total: 0,
    total_pages: 0,
  });

  // Tab count badges
  const [assignedCount, setAssignedCount] = useState<number | null>(null);
  const [unassignedCount, setUnassignedCount] = useState<number | null>(null);

  // Filter & sort controls
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [selectedPriority, setSelectedPriority] = useState<string>('');
  const [sortBy, setSortBy] = useState<SortOption>('NEWEST');

  // UI state
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [conflictAlert, setConflictAlert] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Load facility categories for filter dropdown
  useEffect(() => {
    let isMounted = true;
    categoriesApi
      .listCategories()
      .then((data) => {
        if (isMounted) setCategories(data);
      })
      .catch(() => {
        // Fallback gracefully; filters will show "All Categories" only
      });
    return () => {
      isMounted = false;
    };
  }, []);

  // Fetch count for inactive tab to keep tab badges synchronized
  const refreshInactiveTabCount = useCallback(
    (currentTab: StaffQueueTab) => {
      if (currentTab === 'ASSIGNED') {
        ticketsApi
          .listTickets({ status: 'SUBMITTED', page: 1, page_size: 1 })
          .then((res) => setUnassignedCount(res.meta.total))
          .catch(() => {});
      } else {
        ticketsApi
          .listTickets({
            assigned_staff_id: 'me',
            status: 'ASSIGNED,IN_PROGRESS',
            page: 1,
            page_size: 1,
          })
          .then((res) => setAssignedCount(res.meta.total))
          .catch(() => {});
      }
    },
    []
  );

  // Main queue loader
  const fetchQueue = useCallback(
    async (
      pageNumber = 1,
      tab: StaffQueueTab = activeTab,
      category = selectedCategory,
      priority = selectedPriority
    ) => {
      setIsLoading(true);
      setError(null);
      try {
        const queryParams = {
          page: pageNumber,
          page_size: 10,
          category_id: category || undefined,
          priority: (priority as TicketPriority) || undefined,
          ...(tab === 'ASSIGNED'
            ? {
                assigned_staff_id: 'me',
                status: 'ASSIGNED,IN_PROGRESS',
              }
            : {
                status: 'SUBMITTED',
              }),
        };

        const response = await ticketsApi.listTickets(queryParams);
        setTickets(response.data);
        setMeta(response.meta);

        if (tab === 'ASSIGNED') {
          setAssignedCount(response.meta.total);
        } else {
          setUnassignedCount(response.meta.total);
        }

        refreshInactiveTabCount(tab);
      } catch (err: unknown) {
        const message =
          err instanceof Error
            ? err.message
            : 'Failed to retrieve workbench queue tickets.';
        setError(message);
      } finally {
        setIsLoading(false);
      }
    },
    [activeTab, selectedCategory, selectedPriority, refreshInactiveTabCount]
  );

  useEffect(() => {
    fetchQueue(1, activeTab, selectedCategory, selectedPriority);
  }, [activeTab, selectedCategory, selectedPriority, fetchQueue]);

  // Tab change handler
  const handleTabChange = (newTab: StaffQueueTab) => {
    if (newTab === activeTab) return;
    setActiveTab(newTab);
    setConflictAlert(null);
    setSuccessMessage(null);
  };

  // Pagination handler
  const handlePageChange = (newPage: number) => {
    fetchQueue(newPage, activeTab, selectedCategory, selectedPriority);
  };

  // Quick Action: Claim Ticket (from Unassigned Queue)
  const handleClaimTicket = async (
    e: React.MouseEvent,
    ticket: TicketSummary
  ) => {
    e.stopPropagation();
    if (!user || actionLoadingId) return;

    setActionLoadingId(ticket.id);
    setConflictAlert(null);
    setSuccessMessage(null);

    try {
      // 1. Fetch fresh ticket to get authoritative expected_version
      const fullTicket = await ticketsApi.getTicket(ticket.id);

      // 2. Perform self-assignment
      await ticketsApi.assignTicket(ticket.id, {
        staff_id: user.id,
        expected_version: fullTicket.version,
      });

      setSuccessMessage(
        `Successfully claimed ticket ${ticket.ticket_number}. It is now in your active assignments.`
      );

      // 3. Reload current queue
      await fetchQueue(meta.page, activeTab, selectedCategory, selectedPriority);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 409) {
        setConflictAlert(
          `Concurrency Conflict: Ticket ${ticket.ticket_number} was claimed or updated by another user. The queue has been reloaded.`
        );
        fetchQueue(meta.page, activeTab, selectedCategory, selectedPriority);
      } else {
        const msg =
          err instanceof Error ? err.message : 'Failed to claim ticket.';
        setError(msg);
      }
    } finally {
      setActionLoadingId(null);
    }
  };

  // Quick Action: Start Work (from Assigned Queue)
  const handleStartWork = async (
    e: React.MouseEvent,
    ticket: TicketSummary
  ) => {
    e.stopPropagation();
    if (actionLoadingId) return;

    setActionLoadingId(ticket.id);
    setConflictAlert(null);
    setSuccessMessage(null);

    try {
      // 1. Fetch full ticket to get authoritative version
      const fullTicket = await ticketsApi.getTicket(ticket.id);

      // 2. Transition status to IN_PROGRESS
      await ticketsApi.transitionTicket(ticket.id, {
        target_status: 'IN_PROGRESS',
        expected_version: fullTicket.version,
      });

      setSuccessMessage(
        `Work started on ticket ${ticket.ticket_number}. Status updated to In Progress.`
      );

      // 3. Reload current queue
      await fetchQueue(meta.page, activeTab, selectedCategory, selectedPriority);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 409) {
        setConflictAlert(
          `Concurrency Conflict: Ticket ${ticket.ticket_number} was modified in another session. The queue has been reloaded.`
        );
        fetchQueue(meta.page, activeTab, selectedCategory, selectedPriority);
      } else {
        const msg =
          err instanceof Error ? err.message : 'Failed to start work.';
        setError(msg);
      }
    } finally {
      setActionLoadingId(null);
    }
  };

  // Apply client-side sorting if user selected Oldest or Priority High-to-Low
  const sortedTickets = useMemo(() => {
    const list = [...tickets];
    if (sortBy === 'PRIORITY') {
      return list.sort(
        (a, b) => PRIORITY_WEIGHT[b.priority] - PRIORITY_WEIGHT[a.priority]
      );
    }
    if (sortBy === 'OLDEST') {
      return list.sort(
        (a, b) =>
          new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      );
    }
    // Default NEWEST
    return list.sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
  }, [tickets, sortBy]);

  const formatDate = (isoString: string): string => {
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return isoString;
    }
  };

  // Table columns definition
  const columns: Column<TicketSummary>[] = [
    {
      id: 'ticket_number',
      header: 'Ticket ID & Priority',
      render: (t) => (
        <div className="space-y-1">
          <span className="font-mono text-xs font-semibold text-brand-600 bg-brand-50 px-2 py-0.5 rounded border border-brand-100 block w-max">
            {t.ticket_number}
          </span>
          <PriorityBadge priority={t.priority} />
        </div>
      ),
    },
    {
      id: 'title',
      header: 'Location & Defect',
      render: (t) => (
        <div>
          <p className="font-semibold text-neutral-900 leading-snug">{t.title}</p>
          <p className="text-xs text-neutral-500 mt-0.5">{t.location}</p>
        </div>
      ),
    },
    {
      id: 'category',
      header: 'Category',
      render: (t) => (
        <span className="text-neutral-700 text-xs font-medium bg-neutral-100 px-2 py-1 rounded">
          {t.category_name}
        </span>
      ),
    },
    {
      id: 'status',
      header: 'Status',
      render: (t) => <StatusBadge status={t.status} />,
    },
    {
      id: 'created_at',
      header: 'Submitted',
      render: (t) => (
        <span className="text-xs text-neutral-500">{formatDate(t.created_at)}</span>
      ),
    },
    {
      id: 'actions',
      header: 'Quick Action',
      render: (t) => {
        const isActionRunning = actionLoadingId === t.id;

        if (activeTab === 'UNASSIGNED') {
          return (
            <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
              <Button
                variant="primary"
                size="sm"
                isLoading={isActionRunning}
                disabled={Boolean(actionLoadingId)}
                onClick={(e) => handleClaimTicket(e, t)}
                aria-label={`Claim ticket ${t.ticket_number}`}
              >
                Claim Ticket
              </Button>
            </div>
          );
        }

        // Assigned to Me tab actions
        return (
          <div
            className="flex flex-wrap items-center gap-2"
            onClick={(e) => e.stopPropagation()}
          >
            {t.status === 'ASSIGNED' && (
              <Button
                variant="primary"
                size="sm"
                isLoading={isActionRunning}
                disabled={Boolean(actionLoadingId)}
                onClick={(e) => handleStartWork(e, t)}
                aria-label={`Start work on ticket ${t.ticket_number}`}
              >
                Start Work
              </Button>
            )}

            {t.status === 'IN_PROGRESS' && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => navigate(`/tickets/${t.id}`)}
                aria-label={`Resolve ticket ${t.ticket_number}`}
              >
                Resolve Work &gt;
              </Button>
            )}

            <Button
              variant="secondary"
              size="sm"
              onClick={() => navigate(`/tickets/${t.id}`)}
              aria-label={`Open work order ${t.ticket_number}`}
            >
              Open Work &gt;
            </Button>
          </div>
        );
      },
    },
  ];

  return (
    <div className="space-y-6">
      {/* Workbench Header */}
      <div>
        <h1 className="text-2xl font-bold text-neutral-900 tracking-tight">
          Facilities Maintenance Queue
        </h1>
        <p className="text-sm text-neutral-600 mt-1">
          Operational workbench to triage incoming requests, manage assigned work
          orders, and record work progress.
        </p>
      </div>

      {/* Tabs navigation */}
      <div className="border-b border-neutral-200">
        <nav
          className="flex space-x-4"
          role="tablist"
          aria-label="Staff workbench queues"
        >
          <button
            type="button"
            id="tab-assigned"
            role="tab"
            aria-selected={activeTab === 'ASSIGNED'}
            aria-controls="queue-tabpanel"
            onClick={() => handleTabChange('ASSIGNED')}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
              activeTab === 'ASSIGNED'
                ? 'border-brand-600 text-brand-700 bg-brand-50/40'
                : 'border-transparent text-neutral-600 hover:text-neutral-900 hover:border-neutral-300'
            }`}
          >
            <span>Assigned to Me</span>
            {assignedCount !== null && (
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
                  activeTab === 'ASSIGNED'
                    ? 'bg-brand-600 text-white'
                    : 'bg-neutral-200 text-neutral-700'
                }`}
              >
                {assignedCount}
              </span>
            )}
          </button>

          <button
            type="button"
            id="tab-unassigned"
            role="tab"
            aria-selected={activeTab === 'UNASSIGNED'}
            aria-controls="queue-tabpanel"
            onClick={() => handleTabChange('UNASSIGNED')}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
              activeTab === 'UNASSIGNED'
                ? 'border-brand-600 text-brand-700 bg-brand-50/40'
                : 'border-transparent text-neutral-600 hover:text-neutral-900 hover:border-neutral-300'
            }`}
          >
            <span>Unassigned Queue</span>
            {unassignedCount !== null && (
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
                  activeTab === 'UNASSIGNED'
                    ? 'bg-amber-600 text-white'
                    : 'bg-neutral-200 text-neutral-700'
                }`}
              >
                {unassignedCount}
              </span>
            )}
          </button>
        </nav>
      </div>

      {/* Queue Controls / Filter Bar */}
      <div className="bg-white p-4 rounded-lg border border-neutral-200 shadow-2xs">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Select
            label="Filter by Category"
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            options={[
              { value: '', label: 'All Categories' },
              ...categories.map((c) => ({ value: c.id, label: c.name })),
            ]}
          />

          <Select
            label="Filter by Priority"
            value={selectedPriority}
            onChange={(e) => setSelectedPriority(e.target.value)}
            options={[
              { value: '', label: 'All Priorities' },
              { value: 'CRITICAL', label: 'Critical' },
              { value: 'HIGH', label: 'High' },
              { value: 'MEDIUM', label: 'Medium' },
              { value: 'LOW', label: 'Low' },
            ]}
          />

          <Select
            label="Sort Orders"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortOption)}
            options={[
              { value: 'NEWEST', label: 'Newest First' },
              { value: 'OLDEST', label: 'Oldest First' },
              { value: 'PRIORITY', label: 'Priority: High to Low' },
            ]}
          />
        </div>
      </div>

      {/* Concurrency Conflict Warning Banner */}
      {conflictAlert && (
        <AlertBanner
          variant="warning"
          title="Queue Update"
          onDismiss={() => setConflictAlert(null)}
        >
          {conflictAlert}
        </AlertBanner>
      )}

      {/* Success Notification Banner */}
      {successMessage && (
        <AlertBanner
          variant="success"
          title="Action Successful"
          onDismiss={() => setSuccessMessage(null)}
        >
          {successMessage}
        </AlertBanner>
      )}

      {/* Error Alert with Retry CTA */}
      {error && (
        <AlertBanner variant="error" title="Could Not Load Queue">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mt-1">
            <span>{error}</span>
            <Button
              size="sm"
              variant="secondary"
              onClick={() =>
                fetchQueue(meta.page, activeTab, selectedCategory, selectedPriority)
              }
            >
              Retry Request
            </Button>
          </div>
        </AlertBanner>
      )}

      {/* Tickets Data Table / Tab Panel */}
      <div
        id="queue-tabpanel"
        role="tabpanel"
        aria-labelledby={activeTab === 'ASSIGNED' ? 'tab-assigned' : 'tab-unassigned'}
        className="bg-white rounded-lg border border-neutral-200 overflow-hidden shadow-2xs"
      >
        <DataTable
          columns={columns}
          data={sortedTickets}
          keyField="id"
          isLoading={isLoading}
          onRowClick={(ticket) => navigate(`/tickets/${ticket.id}`)}
          emptyTitle={
            activeTab === 'ASSIGNED'
              ? 'No Assigned Work Orders'
              : 'Queue Clear'
          }
          emptyDescription={
            activeTab === 'ASSIGNED'
              ? 'Great job! You have no pending work orders assigned. Check the Unassigned Queue to claim open issues.'
              : 'No unassigned tickets in the campus queue. All incoming reports have been dispatched.'
          }
          emptyAction={
            activeTab === 'ASSIGNED' ? (
              <Button
                variant="primary"
                onClick={() => handleTabChange('UNASSIGNED')}
              >
                Check Unassigned Queue
              </Button>
            ) : undefined
          }
        />

        {/* Server Pagination */}
        {!isLoading && tickets.length > 0 && (
          <PaginationBar
            page={meta.page}
            pageSize={meta.page_size}
            total={meta.total}
            totalPages={meta.total_pages}
            onPageChange={handlePageChange}
          />
        )}
      </div>
    </div>
  );
};

export default StaffQueuePage;