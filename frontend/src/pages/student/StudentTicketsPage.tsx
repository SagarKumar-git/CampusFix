/**
 * CampusFix SCR-02: Student Portal / My Tickets
 *
 * Implements:
 * - Overview of tickets submitted by the authenticated student
 * - Strict server-side IDOR isolation (backend unconditionally filters by creator_id)
 * - Status filter tabs (All, Submitted, Assigned, In Progress, Resolved, Rejected, Cancelled)
 * - Pagination controls
 * - Deterministic UI quadrant: Loading skeletons, Empty state with CTA, Error alert with Retry
 * - Row navigation to /tickets/:id (UUID)
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ticketsApi } from '../../api/tickets';
import { AlertBanner } from '../../components/ui/AlertBanner';
import { PriorityBadge, StatusBadge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { type Column, DataTable } from '../../components/ui/DataTable';
import { PaginationBar } from '../../components/ui/PaginationBar';
import { PlusIcon } from '../../components/ui/icons';
import type { PaginationMeta, TicketStatus, TicketSummary } from '../../types';

type FilterTab = 'ALL' | TicketStatus;

export const StudentTicketsPage: React.FC = () => {
  const navigate = useNavigate();

  const [tickets, setTickets] = useState<TicketSummary[]>([]);
  const [meta, setMeta] = useState<PaginationMeta>({
    page: 1,
    page_size: 10,
    total: 0,
    total_pages: 0,
  });
  const [activeTab, setActiveTab] = useState<FilterTab>('ALL');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTickets = useCallback(
    async (pageNumber = 1, statusFilter: FilterTab = activeTab) => {
      setIsLoading(true);
      setError(null);
      try {
        const queryStatus = statusFilter === 'ALL' ? undefined : statusFilter;
        const response = await ticketsApi.listTickets({
          page: pageNumber,
          page_size: 10,
          status: queryStatus,
        });
        setTickets(response.data);
        setMeta(response.meta);
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Failed to retrieve your tickets.';
        setError(message);
      } finally {
        setIsLoading(false);
      }
    },
    [activeTab]
  );

  useEffect(() => {
    fetchTickets(1, activeTab);
  }, [activeTab, fetchTickets]);

  const handleTabChange = (tab: FilterTab) => {
    setActiveTab(tab);
  };

  const handlePageChange = (newPage: number) => {
    fetchTickets(newPage, activeTab);
  };

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

  const columns: Column<TicketSummary>[] = [
    {
      id: 'ticket_number',
      header: 'Ticket ID',
      render: (t) => (
        <span className="font-mono text-xs font-semibold text-brand-600 bg-brand-50 px-2 py-0.5 rounded border border-brand-100">
          {t.ticket_number}
        </span>
      ),
    },
    {
      id: 'title',
      header: 'Issue & Location',
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
      id: 'priority',
      header: 'Priority',
      render: (t) => <PriorityBadge priority={t.priority} />,
    },
    {
      id: 'status',
      header: 'Status',
      render: (t) => <StatusBadge status={t.status} />,
    },
    {
      id: 'created_at',
      header: 'Filed On',
      render: (t) => <span className="text-xs text-neutral-500">{formatDate(t.created_at)}</span>,
    },
  ];

  const filterTabs: Array<{ id: FilterTab; label: string }> = [
    { id: 'ALL', label: 'All Tickets' },
    { id: 'SUBMITTED', label: 'Submitted' },
    { id: 'ASSIGNED', label: 'Assigned' },
    { id: 'IN_PROGRESS', label: 'In Progress' },
    { id: 'RESOLVED', label: 'Resolved' },
    { id: 'REJECTED', label: 'Rejected' },
    { id: 'CANCELLED', label: 'Cancelled' },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900 tracking-tight">
            My Reported Issues
          </h1>
          <p className="text-sm text-neutral-600 mt-1">
            Track real-time progress, technician notes, and operational resolution of your facility requests.
          </p>
        </div>

        <Link to="/tickets/new">
          <Button leftIcon={<PlusIcon className="w-4 h-4" />}>
            Report New Issue
          </Button>
        </Link>
      </div>

      {/* Status Filter Tabs */}
      <div className="border-b border-neutral-200 overflow-x-auto">
        <nav className="flex space-x-2 sm:space-x-4 min-w-max pb-1" aria-label="Ticket status filters">
          {filterTabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => handleTabChange(tab.id)}
                className={`px-3 py-2 text-xs sm:text-sm font-medium rounded-t-md border-b-2 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
                  isActive
                    ? 'border-brand-600 text-brand-700 bg-brand-50/50'
                    : 'border-transparent text-neutral-600 hover:text-neutral-900 hover:border-neutral-300'
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Error Alert with Retry CTA */}
      {error && (
        <AlertBanner variant="error" title="Could Not Load Tickets">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mt-1">
            <span>{error}</span>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => fetchTickets(meta.page, activeTab)}
            >
              Retry Request
            </Button>
          </div>
        </AlertBanner>
      )}

      {/* Tickets Data Table */}
      <div className="bg-white rounded-lg border border-neutral-200 overflow-hidden shadow-2xs">
        <DataTable
          columns={columns}
          data={tickets}
          keyField="id"
          isLoading={isLoading}
          onRowClick={(ticket) => navigate(`/tickets/${ticket.id}`)}
          emptyTitle={
            activeTab === 'ALL'
              ? 'No tickets filed yet'
              : `No ${activeTab.toLowerCase().replace('_', ' ')} tickets`
          }
          emptyDescription={
            activeTab === 'ALL'
              ? 'You have not reported any campus facility issues. Notice broken equipment or infrastructure? Submit a work order to alert maintenance.'
              : `You have no tickets currently matching the "${activeTab.replace('_', ' ')}" status filter.`
          }
          emptyAction={
            <Link to="/tickets/new">
              <Button leftIcon={<PlusIcon className="w-4 h-4" />}>
                Report Your First Issue
              </Button>
            </Link>
          }
        />

        {/* Pagination Bar */}
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

export default StudentTicketsPage;
