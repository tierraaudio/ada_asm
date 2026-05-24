import { AlertCircle, CheckCircle2, XCircle } from "lucide-react";
import type { HTMLAttributes } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils/cn";

export type StockStatus = "ok" | "warning" | "critical";

export interface SupplierStockInfo {
  supplier: string;
  quantity: number;
}

export interface StockStatusBadgeProps extends HTMLAttributes<HTMLSpanElement> {
  stock: number;
  /** Effective minimum (defaults to tier*5 at higher level). */
  stockMin: number;
  /** Latest supplier inventory per supplier — used for ámbar / KO copy. */
  supplierStock?: SupplierStockInfo[];
}

export function computeStockStatus(
  stock: number,
  stockMin: number,
  supplierStock: SupplierStockInfo[] = [],
): StockStatus {
  if (stock >= stockMin) return "ok";
  const supplierHasStock = supplierStock.some((s) => s.quantity > 0);
  if (stock === 0 && !supplierHasStock) return "critical";
  return "warning";
}

const STATUS_META: Record<StockStatus, { Icon: typeof CheckCircle2; classes: string }> = {
  ok: {
    Icon: CheckCircle2,
    classes: "text-emerald-600",
  },
  warning: {
    Icon: AlertCircle,
    classes: "text-amber-600",
  },
  critical: {
    Icon: XCircle,
    classes: "text-red-600",
  },
};

function buildHoverContent(
  status: StockStatus,
  stock: number,
  supplierStock: SupplierStockInfo[],
): { title: string; titleClass: string; lines: string[] } {
  if (status === "ok") {
    return {
      title: "Stock suficiente",
      titleClass: "text-emerald-700",
      lines: [`Tienes ${stock} uds en almacén.`],
    };
  }
  if (status === "warning") {
    const available = supplierStock.filter((s) => s.quantity > 0);
    const lines =
      available.length > 0
        ? [
            `Tienes ${stock} uds en almacén, pero:`,
            ...available.map((s) => `• ${s.supplier}: ${s.quantity} uds disponibles`),
          ]
        : [`Stock interno bajo (${stock} uds).`];
    return { title: "Detalle de alertas:", titleClass: "text-amber-700", lines };
  }
  return {
    title: "Detalle de alertas:",
    titleClass: "text-red-700",
    lines: [`Sin stock interno (${stock} uds).`, "Sin disponibilidad en proveedores de confianza."],
  };
}

export function StockStatusBadge({
  stock,
  stockMin,
  supplierStock = [],
  className,
  ...props
}: StockStatusBadgeProps) {
  const status = computeStockStatus(stock, stockMin, supplierStock);
  const { Icon, classes } = STATUS_META[status];
  const hover = buildHoverContent(status, stock, supplierStock);

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          // Passive info trigger — focus also opens the tooltip for keyboard users.
          // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
          tabIndex={0}
          aria-label={`Stock: ${stock} uds (${status})`}
          className={cn(
            "inline-flex cursor-help items-center gap-1.5 text-sm font-medium text-text-primary",
            "outline-none focus-visible:ring-2 focus-visible:ring-ring",
            className,
          )}
          {...props}
        >
          <span>{stock} uds</span>
          <Icon className={cn("size-4", classes)} aria-hidden />
        </span>
      </TooltipTrigger>
      <TooltipContent align="end" className="w-64">
        <p className={cn("mb-1 font-semibold", hover.titleClass)}>{hover.title}</p>
        <ul className="space-y-0.5 text-text-secondary">
          {hover.lines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </TooltipContent>
    </Tooltip>
  );
}
