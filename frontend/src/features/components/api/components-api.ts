import { api } from "@/lib/api/client";

import type { Component, ComponentFilters, Paginated, Supplier } from "../types";

const BASE = "/api/v1/components";

function buildListParams(
  filters: ComponentFilters,
  page: number,
  pageSize: number,
): URLSearchParams {
  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  if (filters.q?.trim()) params.set("q", filters.q.trim());
  for (const f of filters.families ?? []) params.append("family", f);
  for (const s of filters.supplier_ids ?? []) params.append("supplier_id", s);
  for (const t of filters.tiers ?? []) params.append("tier", String(t));
  for (const n of filters.nato_scores ?? []) params.append("nato_score", n);
  for (const l of filters.locations ?? []) params.append("location", l);
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

  delete: async (id: string): Promise<void> => {
    await api.delete(`${BASE}/${id}`);
  },
};

export const suppliersApi = {
  list: async (): Promise<Supplier[]> => {
    const response = await api.get<Supplier[]>("/api/v1/suppliers");
    return response.data;
  },
};
