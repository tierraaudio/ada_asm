import { api } from "@/lib/api/client";

import type {
  ComponentCreatePayload,
  ComponentUpdatePayload,
} from "../schemas";
import type {
  Component,
  ComponentFilters,
  ComponentPurchase,
  Paginated,
} from "../types";

const BASE = "/api/v1/components";

function buildListParams(
  filters: ComponentFilters,
  page: number,
  pageSize: number,
): Record<string, string | number> {
  const params: Record<string, string | number> = { page, page_size: pageSize };
  if (filters.q?.trim()) params.q = filters.q.trim();
  if (filters.family) params.family = filters.family;
  if (filters.supplier) params.supplier = filters.supplier;
  if (filters.tier) params.tier = filters.tier;
  if (filters.nato_score) params.nato_score = filters.nato_score;
  return params;
}

export const componentsApi = {
  list: async (
    filters: ComponentFilters,
    page: number,
    pageSize: number,
  ): Promise<Paginated<Component>> => {
    const response = await api.get<Paginated<Component>>(BASE, {
      params: buildListParams(filters, page, pageSize),
    });
    return response.data;
  },

  get: async (id: string): Promise<Component> => {
    const response = await api.get<Component>(`${BASE}/${id}`);
    return response.data;
  },

  create: async (payload: ComponentCreatePayload): Promise<Component> => {
    const response = await api.post<Component>(BASE, payload);
    return response.data;
  },

  update: async (id: string, payload: ComponentUpdatePayload): Promise<Component> => {
    const response = await api.patch<Component>(`${BASE}/${id}`, payload);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`${BASE}/${id}`);
  },

  listPurchases: async (
    id: string,
    page: number,
    pageSize: number,
  ): Promise<Paginated<ComponentPurchase>> => {
    const response = await api.get<Paginated<ComponentPurchase>>(
      `${BASE}/${id}/purchases`,
      { params: { page, page_size: pageSize } },
    );
    return response.data;
  },

  sync: async (id: string): Promise<{ status: "queued" }> => {
    const response = await api.post<{ status: "queued" }>(`${BASE}/${id}/sync`);
    return response.data;
  },
};
