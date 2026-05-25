import { Edit3, LineChart, X } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { DashboardLayout } from "@/app/layout/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { NatoScoringSummaryCard } from "@/features/shared/badges/NatoScoringSummaryCard";
import type { NatoScoreValue } from "@/features/shared/enums";

import { ModuleHeaderCard } from "../components/ModuleHeaderCard";
import { ModulePriceHistoryModal } from "../components/ModulePriceHistoryModal";
import { ModulesHierarchyTable } from "../components/ModulesHierarchyTable";
import { useModuleDetail } from "../hooks/use-module-detail";
import type { Module, ModuleSummary } from "../types";

const NATO_RANK: Record<NatoScoreValue, number> = {
  F: 0,
  D: 1,
  C: 2,
  B: 3,
  A: 4,
  "A+": 5,
};

/**
 * Build the audit tooltip body for the aggregated scoring on a module —
 * surfaces which descendant component contributes the worst NATO / Tier /
 * earliest expiry so the user can trace the source of the aggregate.
 */
function buildAuditTooltip(module: Module): {
  title: string;
  body: React.ReactNode;
} | null {
  // Find direct component children + recursively scan submodules' children
  // (depth 1 — enough for the tooltip; the underlying aggregate is recursive).
  const componentNames: Array<{
    name: string;
    nato: NatoScoreValue;
    tier: number;
    expires: string | null;
  }> = [];
  for (const edge of module.children) {
    if (edge.child_component) {
      componentNames.push({
        name: edge.child_component.name,
        nato: edge.child_component.nato_score,
        tier: edge.child_component.tier,
        expires: null, // not exposed in ComponentSummary; covered by module agg
      });
    } else if (edge.child_module) {
      componentNames.push({
        name: `${edge.child_module.name} (módulo)`,
        nato: edge.child_module.aggregated_nato_score ?? ("C" as NatoScoreValue),
        tier: edge.child_module.aggregated_tier ?? 4,
        expires: edge.child_module.aggregated_expires_at,
      });
    }
  }

  if (componentNames.length === 0) return null;

  const worstNato = [...componentNames].sort((a, b) => NATO_RANK[a.nato] - NATO_RANK[b.nato])[0]!;
  const worstTier = [...componentNames].sort((a, b) => a.tier - b.tier)[0]!;

  return {
    title: "Agregado de los hijos",
    body: (
      <>
        <p>
          Peor NATO: <strong>{worstNato.nato}</strong> · {worstNato.name}
        </p>
        <p>
          Peor Tier: <strong>Tier {worstTier.tier}</strong> · {worstTier.name}
        </p>
        {module.aggregated_expires_at && (
          <p className="mt-1">
            Caducidad más próxima: <strong>{module.aggregated_expires_at}</strong>
          </p>
        )}
      </>
    ),
  };
}

export function ModuleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const query = useModuleDetail(id);
  const [priceHistoryOpen, setPriceHistoryOpen] = useState(false);

  const auditTooltip = useMemo(
    () => (query.data ? buildAuditTooltip(query.data) : null),
    [query.data],
  );

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

        <ModuleHeaderCard
          module={module}
          stockActionSlot={
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  aria-label="Ver histórico de precios"
                  onClick={() => setPriceHistoryOpen(true)}
                  className="inline-flex size-6 items-center justify-center rounded-md border border-border bg-white text-text-secondary transition-colors hover:border-brand/40 hover:text-brand focus:outline-none focus-visible:ring-2 focus-visible:ring-brand"
                >
                  <LineChart className="size-3.5" />
                </button>
              </TooltipTrigger>
              <TooltipContent>Ver histórico de precios</TooltipContent>
            </Tooltip>
          }
          rightSlot={
            <NatoScoringSummaryCard
              score={module.aggregated_nato_score}
              tier={module.aggregated_tier}
              expiresAt={module.aggregated_expires_at}
              auditTooltipTitle={auditTooltip?.title}
              auditTooltipBody={auditTooltip?.body}
              emptyState={{
                message: "Este módulo no tiene componentes con scoring activo.",
                actionLabel: "Volver al catálogo",
                onAction: () => navigate("/modules"),
              }}
            />
          }
        />

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
