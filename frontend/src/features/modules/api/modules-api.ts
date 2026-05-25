import { api } from "@/lib/api/client";
import type { Paginated, StockEvent } from "@/features/components/types";

import type {
  Module,
  ModuleChild,
  ModuleFilters,
  ModulePriceHistory,
  ModuleSummary,
  PaginatedModules,
} from "../types";

export interface SupplierPurchaseSummary {
  supplier_id: string | null;
  supplier_name: string;
  qty: number;
  cost: string;
}

const BASE = "/api/v1/modules";

export interface ModuleCreatePayload {
  sku: string;
  name: string;
  description?: string | null;
  version?: string;
  fabricante?: string | null;
  location?: string | null;
  tipo_almacenamiento?: string | null;
  stock?: number;
  notas?: string | null;
  fecha_creacion?: string | null;
}

export type ModuleUpdatePayload = Partial<ModuleCreatePayload>;

export interface AddChildPayload {
  child_module_id?: string;
  child_component_id?: string;
  quantity: number;
  notes?: string | null;
  sort_order?: number;
}

export interface UpdateChildPayload {
  quantity?: number;
  notes?: string | null;
  sort_order?: number;
}

export const modulesApi = {
  list: async (
    filters: ModuleFilters,
    page: number,
    pageSize: number,
  ): Promise<PaginatedModules> => {
    const params = new URLSearchParams();
    params.set("page", String(page));
    params.set("page_size", String(pageSize));
    if (filters.q?.trim()) params.set("q", filters.q.trim());
    const response = await api.get<PaginatedModules>(BASE, { params });
    return response.data;
  },

  get: async (id: string): Promise<Module> => {
    const response = await api.get<Module>(`${BASE}/${id}`);
    return response.data;
  },

  create: async (payload: ModuleCreatePayload): Promise<Module> => {
    const response = await api.post<Module>(BASE, payload);
    return response.data;
  },

  update: async (id: string, payload: ModuleUpdatePayload): Promise<Module> => {
    const response = await api.patch<Module>(`${BASE}/${id}`, payload);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`${BASE}/${id}`);
  },

  addChild: async (id: string, payload: AddChildPayload): Promise<ModuleChild> => {
    const response = await api.post<ModuleChild>(`${BASE}/${id}/children`, payload);
    return response.data;
  },

  updateChild: async (
    id: string,
    childId: string,
    payload: UpdateChildPayload,
  ): Promise<ModuleChild> => {
    const response = await api.patch<ModuleChild>(`${BASE}/${id}/children/${childId}`, payload);
    return response.data;
  },

  removeChild: async (id: string, childId: string): Promise<void> => {
    await api.delete(`${BASE}/${id}/children/${childId}`);
  },

  listPriceHistory: async (
    id: string,
    period: "week" | "month" | "year" = "year",
  ): Promise<ModulePriceHistory> => {
    const response = await api.get<ModulePriceHistory>(`${BASE}/${id}/price-history`, {
      params: { period },
    });
    return response.data;
  },

  listStockEvents: async (id: string, page = 1, pageSize = 200): Promise<Paginated<StockEvent>> => {
    const response = await api.get<Paginated<StockEvent>>(`${BASE}/${id}/stock-events`, {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },

  listComponentPurchasesSummary: async (id: string): Promise<SupplierPurchaseSummary[]> => {
    const response = await api.get<SupplierPurchaseSummary[]>(
      `${BASE}/${id}/component-purchases-summary`,
    );
    return response.data;
  },
};

export type { ModuleSummary };
