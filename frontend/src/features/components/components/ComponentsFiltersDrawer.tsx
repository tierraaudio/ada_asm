import { useMemo } from "react";

import { NATO_SCORE_LABELS, TIER_LABELS } from "@/features/shared/rubrics";
import {
  FiltersDrawer,
  type FilterGroup,
  type FiltersValue,
} from "@/features/shared/filters/FiltersDrawer";

import {
  NATO_SCORE_VALUES,
  TIER_VALUES,
  type ComponentFilters,
  type NatoScoreValue,
  type Supplier,
  type TierValue,
} from "../types";

export interface ComponentsFiltersDrawerProps {
  value: ComponentFilters;
  onApply: (next: ComponentFilters) => void;
  onClear: () => void;
  familyOptions: string[];
  suppliers: Supplier[];
}

/**
 * Thin wrapper around the generic `<FiltersDrawer>` that declares the
 * components-specific groups and adapts the typed `ComponentFilters` shape
 * to/from the drawer's opaque `FiltersValue` record.
 */
export function ComponentsFiltersDrawer({
  value,
  onApply,
  onClear,
  familyOptions,
  suppliers,
}: ComponentsFiltersDrawerProps) {
  const groups = useMemo<FilterGroup[]>(
    () => [
      {
        key: "families",
        title: "Familia",
        options: familyOptions.map((f) => ({ value: f, label: f })),
      },
      {
        key: "supplier_ids",
        title: "Supplier preferente",
        options: suppliers.map((s) => ({ value: s.id, label: s.name })),
      },
      {
        key: "tiers",
        title: "TIER",
        options: TIER_VALUES.map((t) => ({ value: t, label: TIER_LABELS[t] })),
      },
      {
        key: "nato_scores",
        title: "Scoring OTAN",
        options: NATO_SCORE_VALUES.map((s) => ({ value: s, label: NATO_SCORE_LABELS[s] })),
      },
    ],
    [familyOptions, suppliers],
  );

  const drawerValue: FiltersValue = useMemo(
    () => ({
      families: value.families ?? [],
      supplier_ids: value.supplier_ids ?? [],
      tiers: value.tiers ?? [],
      nato_scores: value.nato_scores ?? [],
    }),
    [value],
  );

  const handleApply = (next: FiltersValue) => {
    // Strip empty arrays so the upstream URL/state stays clean and matches the
    // pre-refactor `ComponentsFiltersDrawer` contract.
    const merged: ComponentFilters = { ...value };
    const families = (next.families as string[] | undefined) ?? [];
    const supplierIds = (next.supplier_ids as string[] | undefined) ?? [];
    const tiers = (next.tiers as TierValue[] | undefined) ?? [];
    const natoScores = (next.nato_scores as NatoScoreValue[] | undefined) ?? [];

    if (families.length > 0) merged.families = families;
    else delete merged.families;
    if (supplierIds.length > 0) merged.supplier_ids = supplierIds;
    else delete merged.supplier_ids;
    if (tiers.length > 0) merged.tiers = tiers;
    else delete merged.tiers;
    if (natoScores.length > 0) merged.nato_scores = natoScores;
    else delete merged.nato_scores;

    onApply(merged);
  };

  return (
    <FiltersDrawer
      groups={groups}
      value={drawerValue}
      onApply={handleApply}
      onClear={onClear}
      legend="Combinan con AND. Cada bloque acumula con OR."
    />
  );
}
