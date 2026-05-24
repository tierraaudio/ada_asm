/**
 * Cross-feature enums (used by `components`, `modules`, and any future feature
 * that classifies physical parts in the same domain).
 *
 * Re-exported from `features/components/types.ts` for backwards compatibility
 * with existing imports.
 */

export const TIER_VALUES = [1, 2, 3, 4] as const;
export type TierValue = (typeof TIER_VALUES)[number];

export const NATO_SCORE_VALUES = ["A+", "A", "B", "C", "D", "F"] as const;
export type NatoScoreValue = (typeof NATO_SCORE_VALUES)[number];

export const TIPO_ALMACENAMIENTO_VALUES = ["Gaveta", "Almacén"] as const;
export type TipoAlmacenamientoValue = (typeof TIPO_ALMACENAMIENTO_VALUES)[number];
