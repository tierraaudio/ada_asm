import { api } from "@/lib/api/client";

import type {
  Component,
  ComponentDetail,
  ComponentFilters,
  NatoScoring,
  Paginated,
  Supplier,
} from "../types";

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

  get: async (id: string): Promise<ComponentDetail> => {
    const response = await api.get<ComponentDetail>(`${BASE}/${id}`);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`${BASE}/${id}`);
  },

  listNatoScorings: async (id: string): Promise<NatoScoring[]> => {
    const response = await api.get<NatoScoring[]>(`${BASE}/${id}/nato-scorings`);
    return response.data;
  },

  createNatoScoring: async (
    id: string,
    payload: {
      nato_score: NatoScoring["nato_score"];
      tier: NatoScoring["tier"];
      classified_at?: string;
      expires_at?: string;
      notes?: string;
      classifications?: Array<{
        part_label: string;
        fabricante?: string | null;
        country_of_origin?: string | null;
        nato_score?: NatoScoring["nato_score"] | null;
        verificado?: boolean;
        notas?: string | null;
        reference_component_id?: string | null;
        reference_url?: string | null;
      }>;
      alternatives?: Array<{ alternative_component_id: string; notes?: string | null }>;
    },
  ): Promise<NatoScoring> => {
    const response = await api.post<NatoScoring>(`${BASE}/${id}/nato-scorings`, payload);
    return response.data;
  },
};

export const suppliersApi = {
  list: async (): Promise<Supplier[]> => {
    const response = await api.get<Supplier[]>("/api/v1/suppliers");
    return response.data;
  },
};
