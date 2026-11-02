/**
 * CampusFix Categories API Client
 *
 * Implements /api/v1/categories operations:
 * - listCategories (fetches active facility categories; admin can include inactive)
 */

import { apiClient } from './client';
import type { Category, SuccessEnvelope } from '../types';

export const categoriesApi = {
  /**
   * Retrieves facility categories. By default, returns active categories only.
   */
  async listCategories(includeInactive = false): Promise<Category[]> {
    const query = includeInactive ? '?include_inactive=true' : '';
    const res = await apiClient.get<SuccessEnvelope<Category[]>>(`/categories${query}`);
    return res.data;
  },
};
