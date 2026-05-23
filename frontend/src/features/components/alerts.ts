import type { Component, ComponentPurchase } from "./types";

export interface ComponentAlert {
  id: string;
  severity: "info" | "warning" | "critical";
  message: string;
}

const STALE_SUPPLIER_DAYS = 180;
const LOW_STOCK_THRESHOLD = 10;

function daysSince(date: string): number {
  const purchased = new Date(date).getTime();
  const now = Date.now();
  return Math.floor((now - purchased) / (1000 * 60 * 60 * 24));
}

export function lowStockAlert(component: Component): ComponentAlert | null {
  if (component.stock >= LOW_STOCK_THRESHOLD) return null;
  return {
    id: "low_stock",
    severity: "warning",
    message: `Stock bajo (${component.stock} u). Considera reabastecer.`,
  };
}

export function staleSupplierAlert(
  purchases: ComponentPurchase[],
): ComponentAlert | null {
  if (purchases.length === 0) return null;
  const mostRecent = purchases.reduce((latest, p) =>
    new Date(p.purchased_at) > new Date(latest.purchased_at) ? p : latest,
  );
  const age = daysSince(mostRecent.purchased_at);
  if (age <= STALE_SUPPLIER_DAYS) return null;
  return {
    id: "stale_supplier",
    severity: "info",
    message: `Última compra hace ${age} días — revisa precios y disponibilidad.`,
  };
}

export function noPurchasesAlert(
  purchases: ComponentPurchase[],
): ComponentAlert | null {
  if (purchases.length > 0) return null;
  return {
    id: "no_purchases",
    severity: "info",
    message: "Aún no hay compras registradas para este componente.",
  };
}

export function computeAlerts(
  component: Component,
  purchases: ComponentPurchase[],
): ComponentAlert[] {
  return [
    lowStockAlert(component),
    staleSupplierAlert(purchases),
    noPurchasesAlert(purchases),
  ].filter((alert): alert is ComponentAlert => alert !== null);
}
