import { api } from "@/lib/api/client";
import type { ModuleSummary } from "@/features/modules/types";

import type {
  Component,
  ComponentDetail,
  ComponentFilters,
  NatoScoreValue,
  NatoScoring,
  Paginated,
  StockEvent,
  Supplier,
  SupplierPrice,
  SupplierStockSnapshot,
  TierValue,
} from "../types";

export interface ComponentCreatePayload {
  mpn: string;
  name: string;
  family: string;
  tier: TierValue;
  nato_score: NatoScoreValue;
  sku?: string | null;
  description?: string | null;
  datasheet_url?: string | null;
  location?: string | null;
  fabricante?: string | null;
  tipo_almacenamiento?: string | null;
  holded_id?: string | null;
  fecha_creacion?: string | null;
  notas?: string | null;
  stock?: number;
  stock_min?: number | null;
  country_of_origin?: string | null;
  proveedor_preferente_id?: string | null;
}

export type ComponentUpdatePayload = Partial<Omit<ComponentCreatePayload, "mpn">>;

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

  listSupplierPrices: async (id: string): Promise<SupplierPrice[]> => {
    const response = await api.get<SupplierPrice[]>(`${BASE}/${id}/supplier-prices`);
    return response.data;
  },

  listSupplierStocks: async (id: string): Promise<SupplierStockSnapshot[]> => {
    const response = await api.get<SupplierStockSnapshot[]>(`${BASE}/${id}/supplier-stocks`);
    return response.data;
  },

  listStockEvents: async (id: string, page = 1, pageSize = 200): Promise<Paginated<StockEvent>> => {
    const response = await api.get<Paginated<StockEvent>>(`${BASE}/${id}/stock-events`, {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },

  listParents: async (id: string): Promise<ModuleSummary[]> => {
    const response = await api.get<ModuleSummary[]>(`${BASE}/${id}/parents`);
    return response.data;
  },
};

export const suppliersApi = {
  list: async (): Promise<Supplier[]> => {
    const response = await api.get<Supplier[]>("/api/v1/suppliers");
    return response.data;
  },
};
