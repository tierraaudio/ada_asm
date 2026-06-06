import { api } from "@/lib/api/client";
import type { Paginated, StockEvent } from "@/features/components/types";

import type {
  PaginatedProjects,
  Project,
  ProjectChild,
  ProjectFilters,
  ProjectInterestLink,
  ProjectPriceHistory,
  ProjectStatus,
  ProjectSummary,
} from "../types";

const BASE = "/api/v1/projects";

export interface ProjectCreatePayload {
  code: string;
  name: string;
  description?: string | null;
  status?: ProjectStatus;
  customer_id?: string | null;
  icon?: string | null;
  color?: string | null;
  tags?: string[];
  version?: string | null;
  fecha_inicio?: string | null;
  fecha_entrega_estimada?: string | null;
  fecha_entrega_real?: string | null;
  notas?: string | null;
}

export type ProjectUpdatePayload = Partial<ProjectCreatePayload>;

export interface AddProjectChildPayload {
  child_module_id?: string;
  child_component_id?: string;
  quantity: number;
  notes?: string | null;
  sort_order?: number;
}

export interface UpdateProjectChildPayload {
  quantity?: number;
  notes?: string | null;
  sort_order?: number;
}

export const projectsApi = {
  list: async (
    filters: ProjectFilters,
    page: number,
    pageSize: number,
  ): Promise<PaginatedProjects> => {
    const params = new URLSearchParams();
    params.set("page", String(page));
    params.set("page_size", String(pageSize));
    if (filters.q?.trim()) params.set("q", filters.q.trim());
    if (filters.include_archived) params.set("include_archived", "true");
    for (const s of filters.statuses ?? []) params.append("status", s);
    for (const c of filters.customer_ids ?? []) params.append("customer_id", c);
    const response = await api.get<PaginatedProjects>(BASE, { params });
    return response.data;
  },

  get: async (id: string): Promise<Project> => {
    const response = await api.get<Project>(`${BASE}/${id}`);
    return response.data;
  },

  create: async (payload: ProjectCreatePayload): Promise<Project> => {
    const response = await api.post<Project>(BASE, payload);
    return response.data;
  },

  update: async (id: string, payload: ProjectUpdatePayload): Promise<Project> => {
    const response = await api.patch<Project>(`${BASE}/${id}`, payload);
    return response.data;
  },

  softDelete: async (id: string): Promise<void> => {
    await api.delete(`${BASE}/${id}`);
  },

  addChild: async (id: string, payload: AddProjectChildPayload): Promise<ProjectChild> => {
    const response = await api.post<ProjectChild>(`${BASE}/${id}/children`, payload);
    return response.data;
  },

  updateChild: async (
    id: string,
    childId: string,
    payload: UpdateProjectChildPayload,
  ): Promise<ProjectChild> => {
    const response = await api.patch<ProjectChild>(`${BASE}/${id}/children/${childId}`, payload);
    return response.data;
  },

  removeChild: async (id: string, childId: string): Promise<void> => {
    await api.delete(`${BASE}/${id}/children/${childId}`);
  },

  addInterestLink: async (
    id: string,
    payload: { name: string; url: string; sort_order?: number },
  ): Promise<ProjectInterestLink> => {
    const response = await api.post<ProjectInterestLink>(
      `${BASE}/${id}/interest-links`,
      payload,
    );
    return response.data;
  },

  updateInterestLink: async (
    id: string,
    linkId: string,
    payload: { name?: string; url?: string; sort_order?: number },
  ): Promise<ProjectInterestLink> => {
    const response = await api.patch<ProjectInterestLink>(
      `${BASE}/${id}/interest-links/${linkId}`,
      payload,
    );
    return response.data;
  },

  removeInterestLink: async (id: string, linkId: string): Promise<void> => {
    await api.delete(`${BASE}/${id}/interest-links/${linkId}`);
  },

  listPriceHistory: async (
    id: string,
    period: "week" | "month" | "year" = "year",
  ): Promise<ProjectPriceHistory> => {
    const response = await api.get<ProjectPriceHistory>(`${BASE}/${id}/price-history`, {
      params: { period },
    });
    return response.data;
  },

  listStockEvents: async (
    id: string,
    page = 1,
    pageSize = 200,
  ): Promise<Paginated<StockEvent>> => {
    const response = await api.get<Paginated<StockEvent>>(`${BASE}/${id}/stock-events`, {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },
};

/** Cross-feature: projects that hold a given component as a direct child. */
export async function listComponentProjectsUsing(componentId: string): Promise<ProjectSummary[]> {
  const response = await api.get<ProjectSummary[]>(
    `/api/v1/components/${componentId}/projects-using`,
  );
  return response.data;
}

/** Cross-feature: projects that hold a given module as a direct child. */
export async function listModuleProjectsUsing(moduleId: string): Promise<ProjectSummary[]> {
  const response = await api.get<ProjectSummary[]>(
    `/api/v1/modules/${moduleId}/projects-using`,
  );
  return response.data;
}
