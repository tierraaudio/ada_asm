export const TIER_VALUES = ["A+", "A", "B", "C", "D"] as const;
export type TierValue = (typeof TIER_VALUES)[number];

export const NATO_SCORE_VALUES = [
  "100_otan",
  "otan",
  "allied_otan",
  "neutral",
  "high_risk",
  "no_otan",
] as const;
export type NatoScoreValue = (typeof NATO_SCORE_VALUES)[number];

export interface Component {
  id: string;
  mpn: string;
  sku: string | null;
  name: string;
  family: string;
  description: string | null;
  datasheet_url: string | null;
  location: string | null;
  supplier: string | null;
  price_per_100: string | null;
  stock: number;
  tier: TierValue;
  nato_score: NatoScoreValue;
  country_of_origin: string | null;
  created_at: string;
  updated_at: string;
}

export interface ComponentPurchase {
  id: string;
  component_id: string;
  purchased_at: string;
  quantity: number;
  supplier: string;
  unit_cost: string;
  total_cost: string;
  currency: string;
  created_at: string;
}

export interface ComponentFilters {
  q?: string;
  family?: string;
  supplier?: string;
  tier?: TierValue;
  nato_score?: NatoScoreValue;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
