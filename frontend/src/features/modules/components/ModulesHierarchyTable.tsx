import { Box, ChevronDown, ChevronRight, Eye, Trash2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { ConfirmDeleteDialog } from "@/features/components/components/ConfirmDeleteDialog";
import { iconForFamily } from "@/features/components/family-icons";
import { NatoScoreBadge } from "@/features/shared/badges/NatoScoreBadge";
import { StockStatusBadge } from "@/features/shared/badges/StockStatusBadge";
import { formatEuros } from "@/lib/format/currency";
import { cn } from "@/lib/utils/cn";

import { useModuleDetail } from "../hooks/use-module-detail";
import { useDeleteModule } from "../hooks/use-module-mutations";
import type { Module, ModuleChild, ModuleSummary } from "../types";

interface ModulesHierarchyTableProps {
  /** Top-level rows — used by the list page (rows are root modules). */
  rows?: ModuleSummary[];
  /** Direct edges — used by the module detail "Contiene" section so module
   *  + component children render as a unified tree. */
  directChildren?: ModuleChild[];
  /** When true, expanding a row lazily loads the module detail (children). */
  expandable?: boolean;
  /** Empty-state message shown when both rows and directChildren are empty. */
  emptyMessage?: string;
}

/**
 * Threshold for stock alerts on a module. Mirrors the components convention
 * (`tier * 5`) using the worst aggregated tier across descendants, defaulting
 * to 5 when no scoring is available.
 */
function stockMinForModule(m: ModuleSummary): number {
  const tier = m.aggregated_tier ?? 4;
  return tier * 5;
}

export function ModulesHierarchyTable({
  rows,
  directChildren,
  expandable = true,
  emptyMessage = "Sin módulos.",
}: ModulesHierarchyTableProps) {
  const hasTopLevelModules = (rows?.length ?? 0) > 0;
  const hasDirectChildren = (directChildren?.length ?? 0) > 0;
  const isEmpty = !hasTopLevelModules && !hasDirectChildren;
  return (
    <div className="overflow-hidden rounded-md border border-border bg-white">
      <table className="w-full table-fixed text-sm">
        <colgroup>
          <col className="w-[30%]" />
          <col className="w-[9%]" />
          <col className="w-[11%]" />
          <col className="w-[9%]" />
          <col className="w-[7%]" />
          <col className="w-[10%]" />
          <col className="w-[10%]" />
          <col className="w-[8%]" />
          <col className="w-[6%]" />
        </colgroup>
        <thead>
          <tr className="bg-muted/30 text-xs font-bold uppercase tracking-wide text-text-secondary">
            <th className="px-3 py-2 text-left">Nombre</th>
            <th className="px-3 py-2 text-left">Familia</th>
            <th className="px-3 py-2 text-left">SKU</th>
            <th className="px-3 py-2 text-left">Ubicación</th>
            <th className="px-3 py-2 text-left">Versión</th>
            <th className="px-3 py-2 text-left">Precio</th>
            <th className="px-3 py-2 text-left">Stock</th>
            <th className="px-3 py-2 text-left">NATO</th>
            <th className="px-3 py-2 text-right">Acciones</th>
          </tr>
        </thead>
        <tbody>
          {isEmpty ? (
            <tr>
              <td colSpan={9} className="px-3 py-6 text-center text-sm text-text-secondary">
                {emptyMessage}
              </td>
            </tr>
          ) : hasTopLevelModules ? (
            rows!.map((m) => <ModuleRow key={m.id} module={m} depth={0} expandable={expandable} />)
          ) : (
            directChildren!.map((c) => <ChildRow key={c.id} child={c} depth={0} />)
          )}
        </tbody>
      </table>
    </div>
  );
}

interface ModuleRowProps {
  module: ModuleSummary;
  depth: number;
  expandable: boolean;
}

function ModuleRow({ module, depth, expandable }: ModuleRowProps) {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(false);
  const detailQuery = useModuleDetail(expanded && expandable ? module.id : undefined);
  const deleteMutation = useDeleteModule();
  const stockMin = stockMinForModule(module);

  return (
    <>
      <tr className="border-t border-border hover:bg-muted/20">
        <td className="px-3 py-2">
          <div className="flex items-center gap-2" style={{ paddingLeft: depth * 20 }}>
            {expandable ? (
              <button
                type="button"
                aria-label={expanded ? "Colapsar" : "Expandir"}
                onClick={() => setExpanded((s) => !s)}
                className="inline-flex size-5 items-center justify-center rounded text-text-secondary hover:text-text-primary"
              >
                {expanded ? (
                  <ChevronDown className="size-4" />
                ) : (
                  <ChevronRight className="size-4" />
                )}
              </button>
            ) : (
              <span className="inline-block size-5" />
            )}
            <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-md bg-muted text-text-secondary">
              <Box className="size-3.5" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-text-primary">{module.name}</p>
              {module.description && (
                <p className="truncate text-xs text-text-secondary">{module.description}</p>
              )}
            </div>
          </div>
        </td>
        <td className="px-3 py-2 text-text-secondary">{module.family}</td>
        <td className="px-3 py-2 font-mono text-xs text-text-secondary">{module.sku}</td>
        <td className="px-3 py-2 font-mono text-xs text-text-secondary">
          {module.location ?? "—"}
        </td>
        <td className="px-3 py-2 text-text-secondary">{module.version}</td>
        <td className="px-3 py-2 font-semibold text-brand">
          {module.precio_total != null ? formatEuros(module.precio_total) : "—"}
        </td>
        <td className="px-3 py-2">
          <StockStatusBadge stock={module.stock} stockMin={stockMin} supplierStock={[]} />
        </td>
        <td className="px-3 py-2">
          {module.aggregated_nato_score ? (
            <NatoScoreBadge value={module.aggregated_nato_score} />
          ) : (
            <span className="text-xs text-text-secondary">—</span>
          )}
        </td>
        <td className="px-3 py-2">
          <div className="flex items-center justify-end gap-1">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-7"
              aria-label="Ver módulo"
              onClick={() => navigate(`/modules/${module.id}`)}
            >
              <Eye className="size-4 text-text-secondary" />
            </Button>
            <ConfirmDeleteDialog
              trigger={
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="size-7"
                  aria-label="Eliminar módulo"
                >
                  <Trash2 className="size-4 text-red-600" />
                </Button>
              }
              onConfirm={() => deleteMutation.mutateAsync(module.id)}
            />
          </div>
        </td>
      </tr>
      {expanded && detailQuery.data && <ChildrenRows parent={detailQuery.data} depth={depth + 1} />}
      {expanded && detailQuery.isLoading && (
        <tr>
          <td colSpan={9} className="px-3 py-2 pl-12 text-xs text-text-secondary">
            Cargando hijos…
          </td>
        </tr>
      )}
    </>
  );
}

function ChildrenRows({ parent, depth }: { parent: Module; depth: number }) {
  return (
    <>
      {parent.children.map((c) => (
        <ChildRow key={c.id} child={c} depth={depth} />
      ))}
    </>
  );
}

function ChildRow({ child, depth }: { child: ModuleChild; depth: number }) {
  const navigate = useNavigate();
  if (child.child_module) {
    return <ModuleRow module={child.child_module} depth={depth} expandable />;
  }
  const c = child.child_component;
  if (!c) {
    return (
      <tr className="border-t border-border">
        <td colSpan={9} className="px-3 py-2 pl-12 text-xs text-text-secondary">
          (hijo eliminado)
        </td>
      </tr>
    );
  }
  const FamilyIcon = iconForFamily(c.family);
  // For component children inside the table, use the component's tier to
  // compute the stock floor (matching the components list page convention).
  const componentStockMin = c.tier * 5;
  return (
    <tr className={cn("border-t border-border hover:bg-muted/20")}>
      <td className="px-3 py-2">
        <div className="flex items-center gap-2" style={{ paddingLeft: depth * 20 + 25 }}>
          <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-md bg-brand/10 text-brand">
            <FamilyIcon className="size-3.5" />
          </span>
          <span className="min-w-0 flex-1 truncate text-sm text-text-primary">{c.name}</span>
        </div>
      </td>
      <td className="px-3 py-2 text-text-secondary">{c.family}</td>
      <td className="px-3 py-2 font-mono text-xs text-text-secondary">{c.sku ?? "—"}</td>
      <td className="px-3 py-2 font-mono text-xs text-text-secondary">{c.location ?? "—"}</td>
      <td className="px-3 py-2 text-text-secondary">—</td>
      <td className="px-3 py-2 font-semibold text-brand">
        {c.current_price_per_100_eur != null ? formatEuros(c.current_price_per_100_eur) : "—"}
      </td>
      <td className="px-3 py-2">
        <StockStatusBadge stock={c.stock} stockMin={componentStockMin} supplierStock={[]} />
      </td>
      <td className="px-3 py-2">
        <NatoScoreBadge value={c.nato_score} />
      </td>
      <td className="px-3 py-2">
        <div className="flex items-center justify-end gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-7"
            aria-label="Ver componente"
            onClick={() => navigate(`/components/${c.id}`)}
          >
            <Eye className="size-4 text-text-secondary" />
          </Button>
        </div>
      </td>
    </tr>
  );
}
