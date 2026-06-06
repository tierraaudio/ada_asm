import type { ComponentSummary } from "@/features/components/types";
import type { ModuleSummary } from "@/features/modules/types";
import type { NatoScoreValue, TierValue } from "@/features/shared/enums";

/** Status lifecycle — DB-enforced (CHECK constraint) + shared with the BE Pydantic. */
export const PROJECT_STATUS_VALUES = [
  "Presupuestado",
  "Esperando",
  "En proceso",
  "Completado",
  "Archivado",
] as const;
export type ProjectStatus = (typeof PROJECT_STATUS_VALUES)[number];

/** Tooltip body for each status — surfaced by ProjectStatusBadge on hover. */
export const PROJECT_STATUS_DESCRIPTIONS: Record<ProjectStatus, string> = {
  Presupuestado:
    "Cotización emitida al cliente. Aún no se ha empezado a fabricar; pendiente de validación.",
  Esperando: "A la espera de información, materiales o aprobación externa para avanzar.",
  "En proceso": "En curso. Compras y fabricación abiertas; aparece en el flujo de trabajo activo.",
  Completado: "Entregado al cliente. Conservamos histórico de costes y eventos.",
  Archivado: "Retirado de las listas por defecto. Se puede recuperar editando el estado.",
};

export interface Customer {
  id: string;
  holded_id: string;
  name: string;
  holded_url: string | null;
  notas: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectAggregates {
  precio_total: string | null;
  aggregated_nato_score: NatoScoreValue | null;
  aggregated_tier: TierValue | null;
  aggregated_expires_at: string | null;
  buildable_stock: number;
}

export interface ProjectSummary extends ProjectAggregates {
  id: string;
  code: string;
  name: string;
  description: string | null;
  status: ProjectStatus;
  customer_id: string | null;
  customer: Customer | null;
  icon: string | null;
  color: string | null;
  tags: string[];
  version: string | null;
  fecha_inicio: string | null;
  fecha_entrega_estimada: string | null;
  fecha_entrega_real: string | null;
  notas: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectInterestLink {
  id: string;
  project_id: string;
  name: string;
  url: string;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectChild {
  id: string;
  parent_project_id: string;
  child_module_id: string | null;
  child_component_id: string | null;
  quantity: number;
  sort_order: number;
  notes: string | null;
  child_module: ModuleSummary | null;
  child_component: ComponentSummary | null;
}

export interface Project extends ProjectSummary {
  children: ProjectChild[];
  interest_links: ProjectInterestLink[];
}

export interface ProjectPriceHistoryPoint {
  date: string;
  price: string;
}

export interface ProjectPriceHistory {
  project_id: string;
  period: "week" | "month" | "year";
  series: ProjectPriceHistoryPoint[];
}

export interface ProjectFilters {
  q?: string;
  statuses?: ProjectStatus[];
  customer_ids?: string[];
  include_archived?: boolean;
}

export interface PaginatedProjects {
  items: ProjectSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface ConfigResponse {
  holded_base_url: string;
}
