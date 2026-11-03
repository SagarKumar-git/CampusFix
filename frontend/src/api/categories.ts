/**
 * CampusFix Categories API Client
 *
 * Implements /api/v1/categories operations:
 * - listCategories (fetches active facility categories; admin can include inactive)
 * - getCategory (retrieves category by UUID)
 * - createCategory (creates new facility category; admin restricted)
 * - updateCategory (updates category title, description, or active status; admin restricted)
 */

import { apiClient } from './client';
import type {
  Category,
  CategoryCreatePayload,
  CategoryUpdatePayload,
  SuccessEnvelope,
} from '../types';

export const categoriesApi = {
  /**
   * Retrieves facility categories. By default, returns active categories only.
   * Administrators can pass includeInactive=true to inspect all operational categories.
   */
  async listCategories(includeInactive = false): Promise<Category[]> {
    const query = includeInactive ? '?include_inactive=true' : '';
    const res = await apiClient.get<SuccessEnvelope<Category[]>>(`/categories${query}`);
    return res.data;
  },

  /**
   * Retrieves single facility category by its UUID primary key.
   */
  async getCategory(id: string): Promise<Category> {
    const res = await apiClient.get<SuccessEnvelope<Category>>(`/categories/${id}`);
    return res.data;
  },

  /**
   * Creates a new facility maintenance category. Restricted to administrators.
   */
  async createCategory(payload: CategoryCreatePayload): Promise<Category> {
    const res = await apiClient.post<SuccessEnvelope<Category>>('/categories', payload);
    return res.data;
  },

  /**
   * Updates an existing facility category title, description, or active status.
   * Restricted to administrators.
   */
  async updateCategory(id: string, payload: CategoryUpdatePayload): Promise<Category> {
    const res = await apiClient.patch<SuccessEnvelope<Category>>(`/categories/${id}`, payload);
    return res.data;
  },
};
