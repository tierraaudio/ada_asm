import { AlertCircle, CheckCircle2, XCircle } from "lucide-react";
import type { HTMLAttributes } from "react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
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
): { title: string; lines: string[] } | null {
  if (status === "ok") return null;
  if (status === "warning") {
    const available = supplierStock.filter((s) => s.quantity > 0);
    const lines =
      available.length > 0
        ? available.map((s) => `• ${s.supplier}: ${s.quantity} uds disponibles`)
        : [`• Stock interno bajo (${stock} uds)`];
    return { title: "Detalle de alertas:", lines };
  }
  // critical
  return {
    title: "Detalle de alertas:",
    lines: [
      `• Sin stock interno (${stock} uds)`,
      "• Sin disponibilidad en proveedores de confianza",
    ],
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

  const badge = (
    <span
      aria-label={`Stock: ${stock} uds (${status})`}
      className={cn(
        "inline-flex items-center gap-1.5 text-sm font-medium text-text-primary",
        className,
      )}
      {...props}
    >
      <span>{stock} uds</span>
      <Icon className={cn("size-4", classes)} aria-hidden />
    </span>
  );

  if (hover === null) return badge;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button type="button" className="inline-flex">
          {badge}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-3 text-xs" align="end">
        <p
          className={cn(
            "mb-1 font-semibold",
            status === "warning" ? "text-amber-700" : "text-red-700",
          )}
        >
          {hover.title}
        </p>
        <ul className="space-y-0.5 text-text-secondary">
          {hover.lines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
