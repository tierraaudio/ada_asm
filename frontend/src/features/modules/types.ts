import type { ComponentSummary } from "@/features/components/types";
import type { NatoScoreValue, TierValue } from "@/features/shared/enums";

/** High-level classification of a module — distinct from the component family. */
export const MODULE_FAMILY_VALUES = ["Board", "Device", "Bundle", "Case"] as const;
export type ModuleFamilyValue = (typeof MODULE_FAMILY_VALUES)[number];

export interface ModuleAggregates {
  precio_total: string | null;
  aggregated_nato_score: NatoScoreValue | null;
  aggregated_tier: TierValue | null;
  aggregated_expires_at: string | null;
  buildable_stock: number;
}

export interface ModuleSummary extends ModuleAggregates {
  id: string;
  sku: string;
  name: string;
  description: string | null;
  version: string;
  family: ModuleFamilyValue;
  fabricante: string | null;
  location: string | null;
  tipo_almacenamiento: string | null;
  stock: number;
  notas: string | null;
  fecha_creacion: string | null;
  created_at: string;
  updated_at: string;
}

export interface ModuleChild {
  id: string;
  parent_module_id: string;
  child_module_id: string | null;
  child_component_id: string | null;
  quantity: number;
  sort_order: number;
  notes: string | null;
  /** Hydrated server-side; exactly one of these is non-null per edge. */
  child_module: ModuleSummary | null;
  child_component: ComponentSummary | null;
}

export interface Module extends ModuleSummary {
  children: ModuleChild[];
  parents: ModuleSummary[];
}

export interface ModulePriceHistoryPoint {
  date: string;
  price: string;
}

export interface ModulePriceHistory {
  module_id: string;
  period: "week" | "month" | "year";
  series: ModulePriceHistoryPoint[];
}

export interface ModuleFilters {
  q?: string;
}

export interface PaginatedModules {
  items: ModuleSummary[];
  total: number;
  page: number;
  page_size: number;
}
