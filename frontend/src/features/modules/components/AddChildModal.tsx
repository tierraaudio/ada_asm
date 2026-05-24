import { Search } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useComponents } from "@/features/components/hooks/use-components";
import { cn } from "@/lib/utils/cn";

import { useModules } from "../hooks/use-modules";
import type { ModuleChild } from "../types";

type Tab = "components" | "modules";

interface AddChildModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  parentModuleId: string;
  /** Children already in the parent — used to grey "Ya añadido" rows. */
  existingChildren: ModuleChild[];
  onConfirm: (input: {
    child_module_id?: string;
    child_component_id?: string;
    quantity: number;
  }) => Promise<void>;
}

export function AddChildModal({
  open,
  onOpenChange,
  parentModuleId,
  existingChildren,
  onConfirm,
}: AddChildModalProps) {
  const [tab, setTab] = useState<Tab>("components");
  const [search, setSearch] = useState("");
  const [pending, setPending] = useState<{ id: string; kind: Tab } | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [submitting, setSubmitting] = useState(false);

  const componentsQuery = useComponents({
    filters: { q: search },
    page: 1,
    pageSize: 50,
  });
  const modulesQuery = useModules({ q: search }, 1, 50);

  const existingComponentIds = useMemo(
    () => new Set(existingChildren.map((c) => c.child_component_id).filter(Boolean) as string[]),
    [existingChildren],
  );
  const existingModuleIds = useMemo(
    () => new Set(existingChildren.map((c) => c.child_module_id).filter(Boolean) as string[]),
    [existingChildren],
  );

  const handleAdd = async () => {
    if (!pending) return;
    setSubmitting(true);
    try {
      await onConfirm(
        pending.kind === "components"
          ? { child_component_id: pending.id, quantity }
          : { child_module_id: pending.id, quantity },
      );
      setPending(null);
      setQuantity(1);
      onOpenChange(false);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] w-[min(95vw,800px)] max-w-none overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-lg">Añadir hijo</DialogTitle>
        </DialogHeader>

        <div className="flex gap-1 border-b border-border">
          {(["components", "modules"] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => {
                setTab(t);
                setPending(null);
              }}
              className={cn(
                "border-b-2 px-3 py-2 text-sm font-medium transition-colors",
                tab === t
                  ? "border-brand text-brand"
                  : "border-transparent text-text-secondary hover:text-text-primary",
              )}
            >
              {t === "components" ? "Componentes" : "Módulos"}
            </button>
          ))}
        </div>

        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-secondary" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={tab === "components" ? "Buscar componente…" : "Buscar módulo…"}
            className="h-10 w-full rounded-md border border-border bg-white pl-10 pr-3 text-sm text-text-primary placeholder:text-text-secondary/60 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30"
          />
        </div>

        <ul className="max-h-72 space-y-1 overflow-y-auto">
          {tab === "components"
            ? componentsQuery.data?.items.map((c) => {
                const already = existingComponentIds.has(c.id);
                const selected = pending?.id === c.id;
                return (
                  <li key={c.id}>
                    <button
                      type="button"
                      disabled={already}
                      onClick={() => setPending({ id: c.id, kind: "components" })}
                      className={cn(
                        "flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm transition-colors",
                        already
                          ? "border-border bg-muted/40 text-text-secondary"
                          : selected
                            ? "border-brand bg-brand/5"
                            : "border-border bg-white hover:border-brand",
                      )}
                    >
                      <div>
                        <p className="font-medium text-text-primary">{c.name}</p>
                        <p className="text-xs text-text-secondary">
                          <span className="font-mono">{c.mpn}</span>
                          {c.sku && (
                            <>
                              {" · "}
                              <span className="font-mono">{c.sku}</span>
                            </>
                          )}
                        </p>
                      </div>
                      {already && (
                        <span className="rounded-md bg-brand/10 px-2 py-0.5 text-xs font-semibold text-brand">
                          Ya añadido
                        </span>
                      )}
                    </button>
                  </li>
                );
              })
            : modulesQuery.data?.items
                .filter((m) => m.id !== parentModuleId)
                .map((m) => {
                  const already = existingModuleIds.has(m.id);
                  const selected = pending?.id === m.id;
                  return (
                    <li key={m.id}>
                      <button
                        type="button"
                        disabled={already}
                        onClick={() => setPending({ id: m.id, kind: "modules" })}
                        className={cn(
                          "flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm transition-colors",
                          already
                            ? "border-border bg-muted/40 text-text-secondary"
                            : selected
                              ? "border-brand bg-brand/5"
                              : "border-border bg-white hover:border-brand",
                        )}
                      >
                        <div>
                          <p className="font-medium text-text-primary">{m.name}</p>
                          <p className="text-xs text-text-secondary">
                            <span className="font-mono">{m.sku}</span> · {m.version}
                          </p>
                        </div>
                        {already && (
                          <span className="rounded-md bg-brand/10 px-2 py-0.5 text-xs font-semibold text-brand">
                            Ya añadido
                          </span>
                        )}
                      </button>
                    </li>
                  );
                })}
        </ul>

        {pending && (
          <div className="flex items-end gap-3 rounded-md border border-border bg-muted/30 p-3">
            <label className="flex flex-col gap-1">
              <span className="text-xs text-text-secondary">Cantidad</span>
              <input
                type="number"
                min={1}
                value={quantity}
                onChange={(e) => setQuantity(Math.max(1, Number(e.target.value)))}
                className="h-10 w-24 rounded-md border border-border bg-white px-2 text-sm focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30"
              />
            </label>
            <Button type="button" size="sm" onClick={handleAdd} disabled={submitting}>
              Añadir
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setPending(null)}>
              Cancelar
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
