import { Box, ChevronDown, ChevronRight, Component as ComponentIcon, Eye } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { NatoScoreBadge } from "@/features/shared/badges/NatoScoreBadge";
import { formatEuros } from "@/lib/format/currency";
import { cn } from "@/lib/utils/cn";

import { useModuleDetail } from "../hooks/use-module-detail";
import type { Module, ModuleChild, ModuleSummary } from "../types";

interface ModulesHierarchyTableProps {
  rows: ModuleSummary[];
  /** When true, expanding a row lazily loads the module detail (children).
   *  When false (used inside detail "Contiene"), the rows are direct
   *  children passed pre-hydrated and no expansion happens. */
  expandable?: boolean;
}

export function ModulesHierarchyTable({ rows, expandable = true }: ModulesHierarchyTableProps) {
  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <table className="w-full text-sm">
        <colgroup>
          <col className="w-[32%]" />
          <col className="w-[10%]" />
          <col className="w-[12%]" />
          <col className="w-[10%]" />
          <col className="w-[8%]" />
          <col className="w-[10%]" />
          <col className="w-[10%]" />
          <col className="w-[8%]" />
        </colgroup>
        <thead>
          <tr className="bg-muted/40 text-xs uppercase tracking-wide text-text-secondary">
            <th className="px-3 py-2 text-left font-semibold">Nombre</th>
            <th className="px-3 py-2 text-left font-semibold">Tipo</th>
            <th className="px-3 py-2 text-left font-semibold">SKU</th>
            <th className="px-3 py-2 text-left font-semibold">Ubicación</th>
            <th className="px-3 py-2 text-left font-semibold">Versión</th>
            <th className="px-3 py-2 text-left font-semibold">Precio</th>
            <th className="px-3 py-2 text-left font-semibold">Stock</th>
            <th className="px-3 py-2 text-left font-semibold">NATO</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={8} className="px-3 py-6 text-center text-sm text-text-secondary">
                Sin módulos.
              </td>
            </tr>
          ) : (
            rows.map((m) => <ModuleRow key={m.id} module={m} depth={0} expandable={expandable} />)
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

  return (
    <>
      <tr className="border-t border-border hover:bg-muted/30">
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
            <span className="inline-flex size-5 items-center justify-center rounded-md bg-brand/10 text-brand">
              <Box className="size-3.5" />
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-text-primary">{module.name}</p>
              {module.description && (
                <p className="truncate text-xs text-text-secondary">{module.description}</p>
              )}
            </div>
          </div>
        </td>
        <td className="px-3 py-2 text-text-secondary">Módulo</td>
        <td className="px-3 py-2 font-mono text-xs text-text-secondary">{module.sku}</td>
        <td className="px-3 py-2 font-mono text-xs text-text-secondary">
          {module.location ?? "—"}
        </td>
        <td className="px-3 py-2 text-text-secondary">{module.version}</td>
        <td className="px-3 py-2 font-semibold text-brand">
          {module.precio_total != null ? formatEuros(module.precio_total) : "—"}
        </td>
        <td className="px-3 py-2 text-text-secondary">
          {module.stock} <span className="text-xs">uds</span>
        </td>
        <td className="px-3 py-2">
          <div className="flex items-center justify-between gap-2">
            {module.aggregated_nato_score ? (
              <NatoScoreBadge value={module.aggregated_nato_score} showIcon={false} />
            ) : (
              <span className="text-xs text-text-secondary">—</span>
            )}
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 px-2"
              aria-label="Ver módulo"
              onClick={() => navigate(`/modules/${module.id}`)}
            >
              <Eye className="size-4" />
            </Button>
          </div>
        </td>
      </tr>
      {expanded && detailQuery.data && <ChildrenRows parent={detailQuery.data} depth={depth + 1} />}
      {expanded && detailQuery.isLoading && (
        <tr>
          <td colSpan={8} className="px-3 py-2 pl-12 text-xs text-text-secondary">
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
        <td colSpan={8} className="px-3 py-2 pl-12 text-xs text-text-secondary">
          (hijo eliminado)
        </td>
      </tr>
    );
  }
  return (
    <tr className={cn("border-t border-border hover:bg-muted/30")}>
      <td className="px-3 py-2">
        <div className="flex items-center gap-2" style={{ paddingLeft: depth * 20 + 25 }}>
          <span className="inline-flex size-5 items-center justify-center rounded text-text-secondary">
            <ComponentIcon className="size-3.5" />
          </span>
          <span className="text-sm text-text-primary">{c.name}</span>
        </div>
      </td>
      <td className="px-3 py-2 text-text-secondary">Componente</td>
      <td className="px-3 py-2 font-mono text-xs text-text-secondary">{c.sku ?? "—"}</td>
      <td className="px-3 py-2 font-mono text-xs text-text-secondary">—</td>
      <td className="px-3 py-2 text-text-secondary">—</td>
      <td className="px-3 py-2 font-semibold text-brand">
        {c.current_price_per_100_eur != null ? formatEuros(c.current_price_per_100_eur) : "—"}
      </td>
      <td className="px-3 py-2 text-text-secondary">
        {c.stock} <span className="text-xs">uds</span>
      </td>
      <td className="px-3 py-2">
        <div className="flex items-center justify-between gap-2">
          <NatoScoreBadge value={c.nato_score} showIcon={false} />
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 px-2"
            aria-label="Ver componente"
            onClick={() => navigate(`/components/${c.id}`)}
          >
            <Eye className="size-4" />
          </Button>
        </div>
      </td>
    </tr>
  );
}
