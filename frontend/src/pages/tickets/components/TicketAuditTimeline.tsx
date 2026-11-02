/**
 * CampusFix Chronological Ticket Audit Timeline Component
 *
 * Implements SCR-04 Audit Timeline:
 * - Renders immutable transition & assignment logs from GET /api/v1/tickets/{id}/history
 * - Shows transition badges (from_status -> to_status)
 * - Shows actor attribution, assignment target, timestamps, and commentary
 * - Responsive layout accessible across mobile, tablet, and desktop viewports
 */

import React from 'react';
import { StatusBadge } from '../../../components/ui/Badge';
import { Skeleton } from '../../../components/ui/Skeleton';
import {
  CheckIcon,
  ClipboardDocumentListIcon,
  InformationCircleIcon,
  UserIcon,
} from '../../../components/ui/icons';
import type { TicketHistoryItem, TicketStatus } from '../../../types';

export interface TicketAuditTimelineProps {
  history: TicketHistoryItem[];
  isLoading?: boolean;
}

export const TicketAuditTimeline: React.FC<TicketAuditTimelineProps> = ({
  history,
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <div
        className="space-y-4 py-2"
        role="status"
        aria-label="Loading ticket audit timeline"
      >
        <div className="flex gap-4">
          <Skeleton variant="circle" className="w-8 h-8 shrink-0" />
          <div className="flex-1 space-y-2">
            <Skeleton variant="text" className="w-1/3 h-5" />
            <Skeleton variant="text" className="w-2/3 h-4" />
          </div>
        </div>
        <div className="flex gap-4">
          <Skeleton variant="circle" className="w-8 h-8 shrink-0" />
          <div className="flex-1 space-y-2">
            <Skeleton variant="text" className="w-1/4 h-5" />
            <Skeleton variant="text" className="w-1/2 h-4" />
          </div>
        </div>
      </div>
    );
  }

  if (history.length === 0) {
    return (
      <div className="p-6 text-center bg-slate-50 border border-slate-200 rounded-lg">
        <ClipboardDocumentListIcon className="w-8 h-8 mx-auto text-slate-400 mb-2" />
        <p className="text-sm font-medium text-slate-700">No History Records</p>
        <p className="text-xs text-slate-500 mt-1">
          State transitions and assignments will be recorded here as work progresses.
        </p>
      </div>
    );
  }

  // Sort history chronologically (ascending: earliest first)
  const sortedHistory = [...history].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );

  return (
    <div className="flow-root" aria-label="Ticket audit history timeline">
      <ol className="-mb-8" role="list">
        {sortedHistory.map((item, idx) => {
          const isLast = idx === sortedHistory.length - 1;
          const formattedDate = new Date(item.created_at).toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            hour12: true,
          });

          return (
            <li key={item.id} className="relative pb-8">
              {!isLast && (
                <span
                  className="absolute top-4 left-4 -ml-px h-full w-0.5 bg-slate-200"
                  aria-hidden="true"
                />
              )}
              <div className="relative flex items-start space-x-3">
                {/* Timeline node icon */}
                <div className="relative flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 ring-8 ring-white shrink-0">
                  {item.to_status === 'RESOLVED' ? (
                    <CheckIcon className="w-4 h-4 text-emerald-600" />
                  ) : item.to_status === 'REJECTED' || item.to_status === 'CANCELLED' ? (
                    <InformationCircleIcon className="w-4 h-4 text-rose-600" />
                  ) : item.assigned_to ? (
                    <UserIcon className="w-4 h-4 text-sky-600" />
                  ) : (
                    <ClipboardDocumentListIcon className="w-4 h-4 text-slate-600" />
                  )}
                </div>

                {/* Timeline content */}
                <div className="min-w-0 flex-1 pt-0.5">
                  <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold text-slate-900">
                        {item.from_status ? (
                          <span className="flex items-center gap-1.5 flex-wrap">
                            <span>Status changed to</span>
                            <StatusBadge status={item.to_status as TicketStatus} />
                          </span>
                        ) : (
                          <span className="flex items-center gap-1.5 flex-wrap">
                            <span>Incident filed as</span>
                            <StatusBadge status={item.to_status as TicketStatus} />
                          </span>
                        )}
                      </span>
                    </div>
                    <time
                      dateTime={item.created_at}
                      className="text-xs text-slate-500 whitespace-nowrap"
                    >
                      {formattedDate}
                    </time>
                  </div>

                  {/* Actor & Assignee detail */}
                  <div className="mt-1 text-xs text-slate-600 flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span>
                      Changed by{' '}
                      <strong className="font-medium text-slate-800">
                        {item.changed_by.full_name}
                      </strong>
                    </span>
                    {item.assigned_to && (
                      <span className="text-sky-700 bg-sky-50 px-2 py-0.5 rounded-sm font-medium">
                        Assigned to {item.assigned_to.full_name}
                      </span>
                    )}
                  </div>

                  {/* Notes / Comments / Justifications */}
                  {item.notes && (
                    <div className="mt-2 text-sm text-slate-700 bg-slate-50 border-l-2 border-slate-300 rounded-r-md p-3">
                      <p className="whitespace-pre-wrap text-xs leading-relaxed">
                        {item.notes}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
};
