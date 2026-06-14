// Shared enums (TIER, NATO_SCORE, TIPO_ALMACENAMIENTO) live in
// `features/shared/enums.ts` so other features (modules, projects) can
// consume them without depending on the components feature.
import {
  NATO_SCORE_VALUES,
  TIER_VALUES,
  TIPO_ALMACENAMIENTO_VALUES,
} from "@/features/shared/enums";
import type { NatoScoreValue, TierValue, TipoAlmacenamientoValue } from "@/features/shared/enums";

export { NATO_SCORE_VALUES, TIER_VALUES, TIPO_ALMACENAMIENTO_VALUES };
export type { NatoScoreValue, TierValue, TipoAlmacenamientoValue };

// FAMILY_* is components-specific (modules don't have a "family" axis).
export const FAMILY_VALUES = [
  "Microcontroladores",
  "Sensores",
  "Conectores",
  "Resistencias",
  "Condensadores",
  "Inductores",
  "Diodos",
  "Transistores",
  "Módulos",
  "Fuentes de alimentación",
] as const;
export type FamilyValue = (typeof FAMILY_VALUES)[number];

export interface Supplier {
  id: string;
  name: string;
}

export interface SupplierStockSummaryEntry {
  supplier_id: string;
  supplier_name: string;
  quantity: number;
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
  notas: string | null;
  stock: number;
  stock_min: number | null;
  tier: TierValue;
  nato_score: NatoScoreValue;
  country_of_origin: string | null;
  proveedor_preferente_id: string | null;
  /** Blended supplier-derived fields (change `ingest-component-from-mpn`). */
  lifecycle_status: string | null;
  last_buy_date: string | null;
  discontinued: boolean | null;
  end_of_life: boolean | null;
  moq: number | null;
  order_multiple: number | null;
  lead_time_days: number | null;
  unit_weight_kg: string | null;
  image_url: string | null;
  /** True when the family could not be inferred and awaits manual review. */
  family_needs_review: boolean;
  /** Latest 100u price from the preferred supplier (read-only, server-computed). */
  current_price_per_100_eur: string | null;
  /** Latest snapshot per supplier — fed into <StockStatusBadge>. Empty array
   *  means no supplier inventory has ever been recorded (not "unknown"). */
  supplier_stock_summary: SupplierStockSummaryEntry[];
  created_at: string;
  updated_at: string;
}

/** Structured summary returned by `POST /components/ingest` (change
 *  `ingest-component-from-mpn`) so the UI can show what was auto-populated. */
export interface IngestionReport {
  status: "ok" | "ok_with_warnings";
  mpn: string;
  sku: string;
  sources_consulted: string[];
  sources_succeeded: string[];
  sources_contributed: string[];
  family: {
    inferred: string | null;
    needs_review: boolean;
    decided_by: string | null;
    match_type: string | null;
    raw_category: string | null;
    confidence: number | null;
  };
  datasheet: {
    outcome: "archived" | "link_only" | "none";
    source: string | null;
    url: string | null;
    blob_path: string | null;
    size_bytes: number | null;
  };
  fields_populated: string[];
  fields_missing: string[];
  counts: Record<string, number>;
  manual_overrides_applied: string[];
  warnings: string[];
}

export interface IngestComponentResponse {
  component: Component;
  report: IngestionReport;
}

export interface ScoringClassification {
  id: string;
  nato_scoring_id: string;
  part_label: string;
  fabricante: string | null;
  country_of_origin: string | null;
  nato_score: NatoScoreValue | null;
  verificado: boolean;
  notas: string | null;
  reference_component_id: string | null;
  reference_url: string | null;
  sort_order: number;
}

export interface ComponentSummary {
  id: string;
  mpn: string;
  sku: string | null;
  name: string;
  family: string;
  fabricante: string | null;
  location: string | null;
  country_of_origin: string | null;
  nato_score: NatoScoreValue;
  tier: TierValue;
  stock: number;
  current_price_per_100_eur: string | null;
  supplier_stock_summary: SupplierStockSummaryEntry[];
}

export interface ScoringAlternative {
  id: string;
  nato_scoring_id: string;
  alternative_component_id: string;
  notes: string | null;
  sort_order: number;
  /** Hydrated server-side; null if the referenced component was deleted. */
  alternative_component: ComponentSummary | null;
}

export type StockEventKind = "purchase" | "consumption" | "fabricated" | "delivered";

export interface StockEvent {
  id: string;
  /** XOR — exactly one of these is non-null per event. */
  component_id: string | null;
  module_id: string | null;
  kind: StockEventKind;
  quantity: number;
  occurred_at: string;
  notes: string | null;
  supplier_id: string | null;
  /** JOIN with suppliers.name (server-set). */
  supplier_name: string | null;
  unit_cost: string | null;
  total_cost: string | null;
  currency: string;
  project_id: string | null;
  project_name_snapshot: string | null;
  /** delivered-only — link to Holded customer + denormalised name. */
  customer_id_holded: string | null;
  customer_name_snapshot: string | null;
  created_at: string;
  updated_at: string;
}

export type NatoScoringStatus = "active" | "archived";

export interface NatoScoring {
  id: string;
  component_id: string;
  nato_score: NatoScoreValue;
  tier: TierValue;
  classified_at: string;
  expires_at: string;
  classified_by_user_id: string | null;
  classified_by_full_name: string | null;
  status: NatoScoringStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
  classifications: ScoringClassification[];
  alternatives: ScoringAlternative[];
}

export interface ComponentDetail extends Component {
  current_nato_scoring: NatoScoring | null;
}

export interface SupplierPrice {
  id: string;
  component_id: string;
  supplier_id: string;
  qty_tier: 1 | 10 | 100 | 1000;
  price: string;
  valid_from: string;
}

export interface SupplierStockSnapshot {
  id: string;
  component_id: string;
  supplier_id: string;
  quantity: number;
  snapshot_at: string;
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
