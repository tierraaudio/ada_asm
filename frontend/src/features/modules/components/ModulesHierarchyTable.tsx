import { Box, ChevronDown, ChevronRight, Trash2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { ConfirmDeleteDialog } from "@/features/components/components/ConfirmDeleteDialog";
import {
  descriptionForFamily,
  iconForFamily,
  labelForFamily,
} from "@/features/components/family-icons";
import { FamilyChip } from "@/features/shared/badges/FamilyChip";
import { TruncatedText } from "@/features/shared/ui/TruncatedText";
import { NatoScoreBadge } from "@/features/shared/badges/NatoScoreBadge";
import { StockStatusBadge } from "@/features/shared/badges/StockStatusBadge";
import { formatEuros } from "@/lib/format/currency";
import { cn } from "@/lib/utils/cn";

import type { ComponentSummary } from "@/features/components/types";

import { useModuleDetail } from "../hooks/use-module-detail";
import {
  MODULE_FAMILY_DESCRIPTIONS,
  type Module,
  type ModuleSummary,
} from "../types";

/**
 * Structural shape both `ModuleChild` and `ProjectChild` satisfy. The table
 * only renders the visual hierarchy + per-row actions; the `parent_*_id`
 * field never reaches the DOM, so we can stay agnostic about parent kind.
 */
interface HierarchyChild {
  id: string;
  child_module_id: string | null;
  child_component_id: string | null;
  quantity: number;
  sort_order: number;
  child_module: ModuleSummary | null;
  child_component: ComponentSummary | null;
}

interface ModulesHierarchyTableProps {
  /** Top-level rows — used by the list page (rows are root modules). */
  rows?: ModuleSummary[];
  /** Direct edges — used by the module detail "Contiene" section so module
   *  + component children render as a unified tree. */
  directChildren?: HierarchyChild[];
  /** When true, expanding a row lazily loads the module detail (children). */
  expandable?: boolean;
  /** Empty-state message shown when both rows and directChildren are empty. */
  emptyMessage?: string;
  /** When provided, the per-row trash action removes the parent→child
   *  relationship instead of deleting the underlying entity. Only honoured
   *  for `directChildren` rows. */
  onRemoveChild?: (relationshipId: string) => void;
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
  onRemoveChild,
}: ModulesHierarchyTableProps) {
  const hasTopLevelModules = (rows?.length ?? 0) > 0;
  const hasDirectChildren = (directChildren?.length ?? 0) > 0;
  const isEmpty = !hasTopLevelModules && !hasDirectChildren;
  // Actions column is rendered only when the table is in "edit-mode" — i.e.
  // the caller wires `onRemoveChild` so the trash icon can detach a parent
  // relationship inline. Otherwise the row is just clickable to navigate.
  const showActions = Boolean(onRemoveChild);
  const totalColumns = showActions ? 9 : 8;
  return (
    <div className="overflow-hidden rounded-md border border-border bg-white">
      <table className="w-full table-fixed text-sm">
        <colgroup>
          {showActions ? (
            <>
              <col className="w-[24%]" />
              <col className="w-[14%]" />
              <col className="w-[10%]" />
              <col className="w-[10%]" />
              <col className="w-[7%]" />
              <col className="w-[11%]" />
              <col className="w-[10%]" />
              <col className="w-[8%]" />
              <col className="w-[6%]" />
            </>
          ) : (
            <>
              <col className="w-[28%]" />
              <col className="w-[15%]" />
              <col className="w-[11%]" />
              <col className="w-[11%]" />
              <col className="w-[7%]" />
              <col className="w-[10%]" />
              <col className="w-[10%]" />
              <col className="w-[8%]" />
            </>
          )}
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
            {showActions && <th className="px-3 py-2 text-right">Acciones</th>}
          </tr>
        </thead>
        <tbody>
          {isEmpty ? (
            <tr>
              <td colSpan={totalColumns} className="px-3 py-6 text-center text-sm text-text-secondary">
                {emptyMessage}
              </td>
            </tr>
          ) : hasTopLevelModules ? (
            rows!.map((m) => (
              <ModuleRow key={m.id} module={m} depth={0} expandable={expandable} />
            ))
          ) : (
            directChildren!.map((c) => (
              <ChildRow
                key={c.id}
                child={c}
                depth={0}
                {...(onRemoveChild ? { onRemove: () => onRemoveChild(c.id) } : {})}
              />
            ))
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
  /** When provided, the trash action removes the parent→child relationship via
   *  this callback instead of deleting the module itself. */
  onRemove?: () => void;
}

function ModuleRow({ module, depth, expandable, onRemove }: ModuleRowProps) {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(false);
  const detailQuery = useModuleDetail(expanded && expandable ? module.id : undefined);
  const stockMin = stockMinForModule(module);
  const showActions = Boolean(onRemove);

  return (
    <>
      <tr
        role="button"
        tabIndex={0}
        onClick={() => navigate(`/modules/${module.id}`)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            navigate(`/modules/${module.id}`);
          }
        }}
        className="cursor-pointer border-t border-border hover:bg-muted/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand/40"
      >
        <td className="px-3 py-2">
          <div className="flex items-center gap-2" style={{ paddingLeft: depth * 20 }}>
            {expandable ? (
              <button
                type="button"
                aria-label={expanded ? "Colapsar" : "Expandir"}
                onClick={(e) => {
                  e.stopPropagation();
                  setExpanded((s) => !s);
                }}
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
              <TruncatedText
                as="p"
                text={module.name}
                className="text-sm font-medium text-text-primary"
              />
              {module.description && (
                <TruncatedText
                  as="p"
                  text={module.description}
                  className="text-xs text-text-secondary"
                />
              )}
            </div>
          </div>
        </td>
        <td className="overflow-hidden px-3 py-2">
          <FamilyChip
            value={module.family}
            description={MODULE_FAMILY_DESCRIPTIONS[module.family]}
          />
        </td>
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
        {showActions && (
          <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-end gap-1">
              <ConfirmDeleteDialog
                trigger={
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-7"
                    aria-label="Quitar de este padre"
                  >
                    <Trash2 className="size-4 text-red-600" />
                  </Button>
                }
                title={`¿Quitar «${module.name}» de este padre?`}
                description="Solo se elimina la relación; el módulo se conserva en el catálogo."
                confirmLabel="Quitar"
                onConfirm={async () => {
                  onRemove?.();
                }}
              />
            </div>
          </td>
        )}
      </tr>
      {expanded && detailQuery.data && <ChildrenRows parent={detailQuery.data} depth={depth + 1} />}
      {expanded && detailQuery.isLoading && (
        <tr>
          <td
            colSpan={showActions ? 9 : 8}
            className="px-3 py-2 pl-12 text-xs text-text-secondary"
          >
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

function ChildRow({
  child,
  depth,
  onRemove,
}: {
  child: HierarchyChild;
  depth: number;
  onRemove?: () => void;
}) {
  const navigate = useNavigate();
  if (child.child_module) {
    return (
      <ModuleRow
        module={child.child_module}
        depth={depth}
        expandable
        {...(onRemove ? { onRemove } : {})}
      />
    );
  }
  const c = child.child_component;
  if (!c) {
    return (
      <tr className="border-t border-border">
        <td
          colSpan={onRemove ? 9 : 8}
          className="px-3 py-2 pl-12 text-xs text-text-secondary"
        >
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
    <tr
      role="button"
      tabIndex={0}
      onClick={() => navigate(`/components/${c.id}`)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          navigate(`/components/${c.id}`);
        }
      }}
      className={cn(
        "cursor-pointer border-t border-border hover:bg-muted/20",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand/40",
      )}
    >
      <td className="px-3 py-2">
        <div className="flex items-center gap-2" style={{ paddingLeft: depth * 20 + 25 }}>
          <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-md bg-brand/10 text-brand">
            <FamilyIcon className="size-3.5" />
          </span>
          <TruncatedText
            text={c.name}
            className="min-w-0 flex-1 text-sm text-text-primary"
          />
        </div>
      </td>
      <td className="overflow-hidden px-3 py-2">
        <FamilyChip
          value={c.family}
          label={labelForFamily(c.family)}
          description={descriptionForFamily(c.family)}
        />
      </td>
      <td className="px-3 py-2 font-mono text-xs text-text-secondary">{c.sku ?? "—"}</td>
      <td className="px-3 py-2 font-mono text-xs text-text-secondary">{c.location ?? "—"}</td>
      <td className="px-3 py-2 text-text-secondary">—</td>
      <td className="px-3 py-2 font-semibold text-brand">
        {c.current_price_per_100_eur != null ? formatEuros(c.current_price_per_100_eur) : "—"}
      </td>
      <td className="px-3 py-2">
        <StockStatusBadge
          stock={c.stock}
          stockMin={componentStockMin}
          supplierStock={c.supplier_stock_summary.map((s) => ({
            supplier: s.supplier_name,
            quantity: s.quantity,
          }))}
        />
      </td>
      <td className="px-3 py-2">
        <NatoScoreBadge value={c.nato_score} />
      </td>
      {onRemove && (
        <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-end gap-1">
            <ConfirmDeleteDialog
              trigger={
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="size-7"
                  aria-label="Quitar de este padre"
                >
                  <Trash2 className="size-4 text-red-600" />
                </Button>
              }
              title={`¿Quitar «${c.name}» de este padre?`}
              description="Solo se elimina la relación; el componente se conserva en el catálogo."
              confirmLabel="Quitar"
              onConfirm={async () => onRemove()}
            />
          </div>
        </td>
      )}
    </tr>
  );
}
