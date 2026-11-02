/**
 * CampusFix Maintenance Tickets API Client
 *
 * Implements /api/v1/tickets operations:
 * - listTickets (paginated and filtered tickets; server enforces student IDOR isolation)
 * - createTicket (submits new incident; binds authenticated student)
 * - getTicket (fetches detailed ticket record by UUID)
 */

import { apiClient } from './client';
import type {
  PaginatedResponse,
  SuccessEnvelope,
  Ticket,
  TicketAssignPayload,
  TicketAssignResponseData,
  TicketCreatePayload,
  TicketFilterQuery,
  TicketHistoryItem,
  TicketSummary,
  TicketTransitionPayload,
  TicketTransitionResponseData,
} from '../types';

export const ticketsApi = {
  /**
   * Retrieves paginated list of maintenance tickets matching filters.
   * Student accounts strictly receive tickets they filed (enforced on server).
   */
  async listTickets(params?: TicketFilterQuery): Promise<PaginatedResponse<TicketSummary>> {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.page_size) searchParams.set('page_size', String(params.page_size));
    if (params?.status) searchParams.set('status', params.status);
    if (params?.assigned_staff_id) searchParams.set('assigned_staff_id', params.assigned_staff_id);
    if (params?.category_id) searchParams.set('category_id', params.category_id);
    if (params?.priority) searchParams.set('priority', params.priority);

    const qs = searchParams.toString();
    const url = `/tickets${qs ? `?${qs}` : ''}`;

    return await apiClient.get<PaginatedResponse<TicketSummary>>(url);
  },

  /**
   * Submits a new incident ticket.
   */
  async createTicket(payload: TicketCreatePayload): Promise<Ticket> {
    const res = await apiClient.post<SuccessEnvelope<Ticket>>('/tickets', payload);
    return res.data;
  },

  /**
   * Fetches ticket details by UUID.
   */
  async getTicket(id: string): Promise<Ticket> {
    const res = await apiClient.get<SuccessEnvelope<Ticket>>(`/tickets/${id}`);
    return res.data;
  },

  /**
   * Fetches immutable chronological status & assignment history for a ticket.
   */
  async getTicketHistory(id: string): Promise<TicketHistoryItem[]> {
    const res = await apiClient.get<SuccessEnvelope<TicketHistoryItem[]>>(
      `/tickets/${id}/history`
    );
    return res.data;
  },

  /**
   * Assigns or reassigns a ticket to a staff technician.
   */
  async assignTicket(
    id: string,
    payload: TicketAssignPayload
  ): Promise<TicketAssignResponseData> {
    const res = await apiClient.post<SuccessEnvelope<TicketAssignResponseData>>(
      `/tickets/${id}/assign`,
      payload
    );
    return res.data;
  },

  /**
   * Transitions ticket lifecycle status or reopens a resolved/rejected ticket.
   */
  async transitionTicket(
    id: string,
    payload: TicketTransitionPayload
  ): Promise<TicketTransitionResponseData> {
    const res = await apiClient.post<SuccessEnvelope<TicketTransitionResponseData>>(
      `/tickets/${id}/transition`,
      payload
    );
    return res.data;
  },
};
