import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { formatEuros } from "@/lib/format/currency";

import type { Module, ModuleChild } from "../types";

/** Breakdown of `precio_total` over the direct children, ready for a tooltip. */
function priceLines(module: Module): Array<{ label: string; line: string }> {
  return module.children.map((c) => formatChildPriceLine(c));
}

function formatChildPriceLine(c: ModuleChild): { label: string; line: string } {
  if (c.child_component) {
    const unit = c.child_component.current_price_per_100_eur;
    const unitFmt = unit != null ? formatEuros(unit) : "—";
    const subtotal = unit != null ? formatEuros(Number(unit) * c.quantity) : "—";
    return {
      label: c.child_component.name,
      line: `${c.quantity} × ${unitFmt} = ${subtotal}`,
    };
  }
  if (c.child_module) {
    const total = c.child_module.precio_total;
    const totalFmt = total != null ? formatEuros(total) : "—";
    const subtotal = total != null ? formatEuros(Number(total) * c.quantity) : "—";
    return {
      label: c.child_module.name,
      line: `${c.quantity} × ${totalFmt} = ${subtotal}`,
    };
  }
  return { label: "—", line: "—" };
}

interface PriceTotalTooltipProps {
  module: Module;
}

export function PriceTotalTooltip({ module }: PriceTotalTooltipProps) {
  const lines = priceLines(module);
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="cursor-help font-semibold text-brand">
          {module.precio_total != null ? formatEuros(module.precio_total) : "—"}
        </span>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="max-w-sm">
        <p className="mb-1 text-sm font-semibold text-text-primary">Desglose</p>
        {lines.length === 0 ? (
          <p className="text-xs text-text-secondary">Sin hijos para agregar.</p>
        ) : (
          <ul className="space-y-1 text-xs">
            {lines.map((l, idx) => (
              <li key={idx} className="text-text-secondary">
                <span className="text-text-primary">{l.label}:</span> {l.line}
              </li>
            ))}
          </ul>
        )}
      </TooltipContent>
    </Tooltip>
  );
}

interface BuildableTooltipProps {
  stock: number;
  buildable: number;
}

export function BuildableTooltip({ stock, buildable }: BuildableTooltipProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="cursor-help">
          {stock} <span className="text-text-secondary">unidades</span>
        </span>
      </TooltipTrigger>
      <TooltipContent side="bottom">
        <p className="text-xs">
          <span className="text-text-primary">Ensamblados: </span>
          <span className="font-semibold">{stock}</span>
        </p>
        <p className="text-xs text-text-secondary">
          Puedes ensamblar {buildable} más con el stock actual de componentes.
        </p>
      </TooltipContent>
    </Tooltip>
  );
}
