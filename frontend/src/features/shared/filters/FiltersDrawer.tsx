import { Filter } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils/cn";

/**
 * Generic, domain-agnostic filters drawer. Used by the components catalogue
 * filters drawer and (soon) the modules' "Añadir componente" picker.
 *
 * `value` is an opaque `Record<groupKey, Array<unknown>>` — each group declares
 * the type of its option values; the consumer holds the typed shape externally.
 */

export interface FilterOption<T extends string | number> {
  value: T;
  label: string;
}

export interface FilterGroup<T extends string | number = string | number> {
  /** Stable id used as the key in the `value` record. */
  key: string;
  /** Section heading shown to the user. */
  title: string;
  options: Array<FilterOption<T>>;
}

export type FiltersValue = Record<string, Array<string | number>>;

export interface FiltersDrawerProps {
  groups: Array<FilterGroup>;
  value: FiltersValue;
  onApply: (next: FiltersValue) => void;
  onClear?: () => void;
  /** Short copy under the title — e.g. how the operators combine. */
  legend?: string;
  /** Override the popover alignment. Defaults to `"end"`. */
  align?: "start" | "center" | "end";
}

function activeCount(value: FiltersValue): number {
  return Object.values(value).reduce((acc, arr) => acc + (arr?.length ?? 0), 0);
}

function toggle<T>(arr: T[] | undefined, v: T): T[] {
  const next = new Set(arr ?? []);
  if (next.has(v)) next.delete(v);
  else next.add(v);
  return [...next];
}

export function FiltersDrawer({
  groups,
  value,
  onApply,
  onClear,
  legend,
  align = "end",
}: FiltersDrawerProps) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<FiltersValue>(value);

  function handleOpenChange(next: boolean) {
    if (next) setDraft(value); // re-sync on open so a previous "cancel" is forgotten
    setOpen(next);
  }

  const count = activeCount(value);

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
      <PopoverContent align={align} className="w-[28rem] p-0">
        <div className="border-b border-border px-4 py-3">
          <h3 className="text-sm font-semibold text-text-primary">Filtros</h3>
          {legend && <p className="text-xs text-text-secondary">{legend}</p>}
        </div>

        <div className="max-h-96 overflow-y-auto px-4 py-3 text-sm">
          {groups.map((group) => (
            <section key={group.key} className="mb-4">
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-secondary">
                {group.title}
              </h4>
              {group.options.length === 0 ? (
                <p className="text-xs text-text-secondary">Sin opciones disponibles.</p>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {group.options.map((opt) => {
                    const selected = draft[group.key]?.includes(opt.value) ?? false;
                    return (
                      <button
                        key={String(opt.value)}
                        type="button"
                        onClick={() =>
                          setDraft({
                            ...draft,
                            [group.key]: toggle(draft[group.key], opt.value),
                          })
                        }
                        className={cn(
                          "inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                          selected
                            ? "border-brand bg-brand/10 text-brand"
                            : "border-border bg-white text-text-secondary hover:border-text-secondary hover:text-text-primary",
                        )}
                      >
                        {opt.label}
                      </button>
                    );
                  })}
                </div>
              )}
            </section>
          ))}
        </div>

        <div className="flex items-center justify-between border-t border-border px-4 py-3">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              onClear?.();
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
