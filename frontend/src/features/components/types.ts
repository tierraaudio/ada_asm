export const TIER_VALUES = [1, 2, 3, 4] as const;
export type TierValue = (typeof TIER_VALUES)[number];

export const NATO_SCORE_VALUES = ["A+", "A", "B", "C", "D", "F"] as const;
export type NatoScoreValue = (typeof NATO_SCORE_VALUES)[number];

export interface Supplier {
  id: string;
  name: string;
}

export interface Component {
  id: string;
  mpn: string;
  sku: string | null;
  name: string;
  family: string;
  description: string | null;
  datasheet_url: string | null;
  location: string | null;
  fabricante: string | null;
  tipo_almacenamiento: string | null;
  holded_id: string | null;
  fecha_creacion: string | null;
  verificado: boolean;
  notas: string | null;
  stock: number;
  stock_min: number | null;
  tier: TierValue;
  nato_score: NatoScoreValue;
  country_of_origin: string | null;
  proveedor_preferente_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ComponentFilters {
  q?: string;
  families?: string[];
  supplier_ids?: string[];
  tiers?: TierValue[];
  nato_scores?: NatoScoreValue[];
  locations?: string[];
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

/** Effective threshold = explicit stock_min OR tier*5 (mirrors backend default). */
export function effectiveStockMin(component: Pick<Component, "tier" | "stock_min">): number {
  return component.stock_min ?? component.tier * 5;
}
