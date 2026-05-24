import { cn } from "@/lib/utils/cn";

import type { Supplier, SupplierPrice } from "../types";

interface PreciosDeHoyTableProps {
  prices: SupplierPrice[];
  suppliers: Supplier[];
  preferredSupplierId: string | null;
}

const QTY_TIERS: Array<SupplierPrice["qty_tier"]> = [1, 10, 100, 1000];

function latestBySupplierAndTier(prices: SupplierPrice[]): Map<string, SupplierPrice> {
  const map = new Map<string, SupplierPrice>();
  for (const p of prices) {
    const key = `${p.supplier_id}::${p.qty_tier}`;
    const current = map.get(key);
    if (!current || p.valid_from > current.valid_from) map.set(key, p);
  }
  return map;
}

function formatEur(price: string | undefined): string {
  if (!price) return "—";
  const n = Number(price);
  if (Number.isNaN(n)) return price;
  return `€${n.toFixed(2)}`;
}

export function PreciosDeHoyTable({
  prices,
  suppliers,
  preferredSupplierId,
}: PreciosDeHoyTableProps) {
  const latest = latestBySupplierAndTier(prices);
  // Order: preferred supplier first, then alphabetical.
  const ordered = [...suppliers].sort((a, b) => {
    if (a.id === preferredSupplierId) return -1;
    if (b.id === preferredSupplierId) return 1;
    return a.name.localeCompare(b.name);
  });

  return (
    <div className="space-y-3">
      {ordered.map((supplier) => {
        const isPreferred = supplier.id === preferredSupplierId;
        return (
          <div
            key={supplier.id}
            className={cn(
              "rounded-md border px-3 py-2",
              isPreferred
                ? "border-brand/40 bg-brand/5"
                : "border-border bg-white",
            )}
          >
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-sm font-semibold text-text-primary">
                {supplier.name}
              </span>
              {isPreferred && (
                <span className="rounded-md bg-brand px-2 py-0.5 text-xs font-semibold text-white">
                  Preferente
                </span>
              )}
            </div>
            <div className="grid grid-cols-4 gap-2">
              {QTY_TIERS.map((tier) => {
                const row = latest.get(`${supplier.id}::${tier}`);
                return (
                  <div key={tier} className="flex flex-col">
                    <span className="text-[10px] uppercase tracking-wide text-text-secondary">
                      {tier}u
                    </span>
                    <span
                      className={cn(
                        "text-sm font-medium",
                        isPreferred ? "text-brand" : "text-text-primary",
                      )}
                    >
                      {formatEur(row?.price)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
