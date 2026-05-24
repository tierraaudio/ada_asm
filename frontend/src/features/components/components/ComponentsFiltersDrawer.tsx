import { Filter } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils/cn";

import { NATO_SCORE_LABELS, TIER_LABELS } from "../rubrics";
import {
  NATO_SCORE_VALUES,
  TIER_VALUES,
  type ComponentFilters,
  type NatoScoreValue,
  type Supplier,
  type TierValue,
} from "../types";

export interface ComponentsFiltersDrawerProps {
  /** The currently-applied filters (URL-backed). */
  value: ComponentFilters;
  onApply: (next: ComponentFilters) => void;
  onClear: () => void;
  /** Distinct family options (derived from the visible page). */
  familyOptions: string[];
  /** All suppliers (from /api/v1/suppliers). */
  suppliers: Supplier[];
}

function toggle<T>(arr: T[] | undefined, value: T): T[] {
  const next = new Set(arr ?? []);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return Array.from(next);
}

function activeFilterCount(filters: ComponentFilters): number {
  return (
    (filters.families?.length ?? 0) +
    (filters.supplier_ids?.length ?? 0) +
    (filters.tiers?.length ?? 0) +
    (filters.nato_scores?.length ?? 0) +
    (filters.locations?.length ?? 0)
  );
}

export function ComponentsFiltersDrawer({
  value,
  onApply,
  onClear,
  familyOptions,
  suppliers,
}: ComponentsFiltersDrawerProps) {
  const [open, setOpen] = useState(false);
  // Local draft state — only commits on Apply.
  const [draft, setDraft] = useState<ComponentFilters>(value);

  // Sync draft when the popover (re)opens, so re-opening reflects the current
  // applied filters and doesn't show a stale draft from a previous cancel.
  function handleOpenChange(next: boolean) {
    if (next) setDraft(value);
    setOpen(next);
  }

  const count = activeFilterCount(value);

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-10"
          aria-label="Abrir filtros"
        >
          <Filter className="size-4" />
          Filtros
          {count > 0 && (
            <span className="ml-1 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-brand px-1.5 text-xs font-semibold text-white">
              {count}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[28rem] p-0">
        <div className="border-b border-border px-4 py-3">
          <h3 className="text-sm font-semibold text-text-primary">Filtros</h3>
          <p className="text-xs text-text-secondary">
            Combinan con AND. Cada bloque acumula con OR.
          </p>
        </div>

        <div className="max-h-[24rem] overflow-y-auto px-4 py-3 text-sm">
          <FilterSection title="Familia">
            <ChipGrid
              options={familyOptions.map((f) => ({ value: f, label: f }))}
              selected={draft.families ?? []}
              onToggle={(v) => setDraft({ ...draft, families: toggle(draft.families, v) })}
            />
          </FilterSection>

          <FilterSection title="Supplier preferente">
            <ChipGrid
              options={suppliers.map((s) => ({ value: s.id, label: s.name }))}
              selected={draft.supplier_ids ?? []}
              onToggle={(v) => setDraft({ ...draft, supplier_ids: toggle(draft.supplier_ids, v) })}
            />
          </FilterSection>

          <FilterSection title="TIER">
            <ChipGrid
              options={TIER_VALUES.map((t) => ({ value: t, label: TIER_LABELS[t] }))}
              selected={draft.tiers ?? []}
              onToggle={(v) => setDraft({ ...draft, tiers: toggle(draft.tiers, v as TierValue) })}
            />
          </FilterSection>

          <FilterSection title="Scoring OTAN">
            <ChipGrid
              options={NATO_SCORE_VALUES.map((s) => ({
                value: s,
                label: NATO_SCORE_LABELS[s],
              }))}
              selected={draft.nato_scores ?? []}
              onToggle={(v) =>
                setDraft({
                  ...draft,
                  nato_scores: toggle(draft.nato_scores, v as NatoScoreValue),
                })
              }
            />
          </FilterSection>
        </div>

        <div className="flex items-center justify-between border-t border-border px-4 py-3">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              onClear();
              setDraft({});
              setOpen(false);
            }}
          >
            Limpiar filtros
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={() => {
              onApply(draft);
              setOpen(false);
            }}
          >
            Aplicar
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}

function FilterSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-4">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-secondary">
        {title}
      </h4>
      {children}
    </section>
  );
}

interface ChipGridProps<T extends string | number> {
  options: Array<{ value: T; label: string }>;
  selected: T[];
  onToggle: (value: T) => void;
}

function ChipGrid<T extends string | number>({ options, selected, onToggle }: ChipGridProps<T>) {
  if (options.length === 0) {
    return <p className="text-xs text-text-secondary">Sin opciones disponibles.</p>;
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((opt) => {
        const active = selected.includes(opt.value);
        return (
          <button
            key={String(opt.value)}
            type="button"
            onClick={() => onToggle(opt.value)}
            className={cn(
              "inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium transition-colors",
              active
                ? "border-brand bg-brand/10 text-brand"
                : "border-border bg-white text-text-secondary hover:border-text-secondary hover:text-text-primary",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
