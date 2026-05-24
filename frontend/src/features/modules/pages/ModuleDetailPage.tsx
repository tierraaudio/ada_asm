import { Edit3, X } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { DashboardLayout } from "@/app/layout/DashboardLayout";
import { Button } from "@/components/ui/button";

import { ModuleHeaderCard } from "../components/ModuleHeaderCard";
import { ModulePriceHistoryModal } from "../components/ModulePriceHistoryModal";
import { ModulesHierarchyTable } from "../components/ModulesHierarchyTable";
import { useModuleDetail } from "../hooks/use-module-detail";
import type { ModuleSummary } from "../types";

export function ModuleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const query = useModuleDetail(id);
  const [priceHistoryOpen, setPriceHistoryOpen] = useState(false);

  if (!id || query.isLoading) {
    return (
      <DashboardLayout>
        <p className="text-sm text-text-secondary">Cargando módulo…</p>
      </DashboardLayout>
    );
  }
  if (query.isError || !query.data) {
    return (
      <DashboardLayout>
        <p className="text-sm text-destructive">No se encontró el módulo.</p>
      </DashboardLayout>
    );
  }
  const module = query.data;

  // Render the direct children as a hierarchy table (with expandable subtrees).
  const childRows: ModuleSummary[] = module.children
    .filter((c) => c.child_module !== null)
    .map((c) => c.child_module!) as ModuleSummary[];
  const directComponents = module.children.filter((c) => c.child_component !== null);

  return (
    <DashboardLayout>
      <div className="mx-auto flex w-full max-w-[1920px] flex-col gap-6">
        <header className="flex items-center justify-between">
          <button
            type="button"
            aria-label="Cerrar"
            onClick={() => navigate("/modules")}
            className="inline-flex size-9 items-center justify-center rounded-md text-text-secondary hover:bg-muted hover:text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-brand"
          >
            <X className="size-5" />
          </button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => navigate(`/modules/${module.id}/edit`)}
          >
            <Edit3 className="size-4" />
            Editar Módulo
          </Button>
        </header>

        <ModuleHeaderCard module={module} onOpenPriceHistory={() => setPriceHistoryOpen(true)} />

        <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-secondary">
            Contiene
          </h2>
          {childRows.length === 0 && directComponents.length === 0 ? (
            <p className="text-sm text-text-secondary">Este módulo no tiene hijos.</p>
          ) : (
            <>
              {childRows.length > 0 && <ModulesHierarchyTable rows={childRows} expandable />}
              {directComponents.length > 0 && (
                <div className="mt-3 overflow-hidden rounded-lg border border-border">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-muted/40 text-xs uppercase tracking-wide text-text-secondary">
                        <th className="px-3 py-2 text-left">Componente</th>
                        <th className="px-3 py-2 text-left">SKU</th>
                        <th className="px-3 py-2 text-left">Cantidad</th>
                        <th className="px-3 py-2 text-left">Precio</th>
                        <th className="px-3 py-2 text-left">Stock</th>
                      </tr>
                    </thead>
                    <tbody>
                      {directComponents.map((c) => {
                        const cc = c.child_component!;
                        return (
                          <tr key={c.id} className="border-t border-border hover:bg-muted/30">
                            <td className="px-3 py-2 text-text-primary">{cc.name}</td>
                            <td className="px-3 py-2 font-mono text-xs text-text-secondary">
                              {cc.sku ?? "—"}
                            </td>
                            <td className="px-3 py-2 text-text-secondary">{c.quantity}</td>
                            <td className="px-3 py-2 text-brand">
                              {cc.current_price_per_100_eur ?? "—"}
                            </td>
                            <td className="px-3 py-2 text-text-secondary">{cc.stock}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </section>

        <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-secondary">
            Pertenece a
          </h2>
          {module.parents.length === 0 ? (
            <p className="text-sm text-text-secondary">
              Este módulo no pertenece a ningún módulo superior.
            </p>
          ) : (
            <ul className="flex flex-wrap gap-2">
              {module.parents.map((p) => (
                <li key={p.id}>
                  <button
                    type="button"
                    onClick={() => navigate(`/modules/${p.id}`)}
                    className="inline-flex items-center gap-2 rounded-md border border-border bg-white px-3 py-1.5 text-sm text-text-primary hover:border-brand hover:text-brand"
                  >
                    <span className="font-mono text-xs text-text-secondary">{p.sku}</span>
                    {p.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <ModulePriceHistoryModal
        open={priceHistoryOpen}
        onOpenChange={setPriceHistoryOpen}
        moduleId={module.id}
        moduleName={module.name}
        moduleSku={module.sku}
      />
    </DashboardLayout>
  );
}
