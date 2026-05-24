import { AlertTriangle, ArrowUpRight, PackageX, ShieldAlert, TrendingUp } from "lucide-react";
import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils/cn";

import type {
  ComponentDetail,
  StockEvent,
  Supplier,
  SupplierPrice,
  SupplierStockSnapshot,
} from "../types";

interface HistorialDeComprasModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  component: ComponentDetail;
  stockEvents: StockEvent[];
  suppliers: Supplier[];
  supplierPrices: SupplierPrice[];
  supplierStocks: SupplierStockSnapshot[];
}

interface StockPoint {
  date: string;
  stock: number;
  purchase?: number | undefined;
  consumption?: number | undefined;
  label?: string | undefined;
}

function buildStockSeries(events: StockEvent[], currentStock: number): StockPoint[] {
  // Sort ascending by occurred_at.
  const asc = [...events].sort((a, b) =>
    a.occurred_at < b.occurred_at ? -1 : a.occurred_at > b.occurred_at ? 1 : 0,
  );
  // Pick a baseline so the running total ends at `currentStock`.
  const sumSigned = asc.reduce(
    (acc, e) => acc + (e.kind === "purchase" ? e.quantity : -e.quantity),
    0,
  );
  let running = currentStock - sumSigned;
  return asc.map((e) => {
    running += e.kind === "purchase" ? e.quantity : -e.quantity;
    return {
      date: e.occurred_at,
      stock: running,
      purchase: e.kind === "purchase" ? running : undefined,
      consumption: e.kind === "consumption" ? running : undefined,
      label:
        e.kind === "purchase"
          ? `+${e.quantity} de ${e.supplier_name ?? "supplier"}`
          : `−${e.quantity} → ${e.project_name_snapshot ?? "proyecto"}`,
    };
  });
}

interface ChartTooltipPayload {
  payload: StockPoint;
}

function CustomDot(props: { cx?: number; cy?: number; payload?: StockPoint }) {
  const { cx, cy, payload } = props;
  if (cx == null || cy == null || !payload) return null;
  const isPurchase = payload.purchase !== undefined;
  const fill = isPurchase ? "#22c55e" : "#ef4444";
  return <circle cx={cx} cy={cy} r={4} fill={fill} stroke="#fff" strokeWidth={1.5} />;
}

function StockEventTooltip(props: { active?: boolean; payload?: ChartTooltipPayload[] }) {
  const { active, payload } = props;
  if (!active || !payload || payload.length === 0) return null;
  const p = payload[0]?.payload;
  if (!p) return null;
  return (
    <div className="rounded-md border border-border bg-white p-2 text-xs shadow">
      <p className="font-semibold text-text-primary">{p.date}</p>
      <p className="text-text-secondary">Stock: {p.stock} uds</p>
      {p.label && <p className="text-text-secondary">{p.label}</p>}
    </div>
  );
}

interface SupplierAggregate {
  supplierName: string;
  qty: number;
  cost: number;
}

function aggregatePurchasesBySupplier(events: StockEvent[]): SupplierAggregate[] {
  const byName = new Map<string, SupplierAggregate>();
  for (const e of events) {
    if (e.kind !== "purchase") continue;
    const name = e.supplier_name ?? "—";
    const current = byName.get(name) ?? { supplierName: name, qty: 0, cost: 0 };
    current.qty += e.quantity;
    current.cost += Number(e.total_cost ?? 0);
    byName.set(name, current);
  }
  return [...byName.values()].sort((a, b) => b.qty - a.qty);
}

function formatEur(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("es-ES", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 2,
  }).format(value);
}

function buildAlerts(
  component: ComponentDetail,
  events: StockEvent[],
  prices: SupplierPrice[],
  stocks: SupplierStockSnapshot[],
  suppliers: Supplier[],
): Array<{
  id: string;
  severity: "warning" | "info" | "critical";
  title: string;
  detail: string;
}> {
  const out: Array<{
    id: string;
    severity: "warning" | "info" | "critical";
    title: string;
    detail: string;
  }> = [];
  const supplierName = new Map(suppliers.map((s) => [s.id, s.name]));

  // 1) Precio en tendencia ascendente — compare oldest vs newest qty_tier=100
  // for the preferred supplier.
  const pref = component.proveedor_preferente_id;
  if (pref) {
    const prefPrices = prices
      .filter((p) => p.supplier_id === pref && p.qty_tier === 100)
      .sort((a, b) => (a.valid_from < b.valid_from ? -1 : 1));
    if (prefPrices.length >= 2) {
      const first = prefPrices[0]!;
      const last = prefPrices[prefPrices.length - 1]!;
      const oldest = Number(first.price);
      const newest = Number(last.price);
      const change = oldest > 0 ? ((newest - oldest) / oldest) * 100 : 0;
      if (change > 0) {
        out.push({
          id: "precio_asc",
          severity: "warning",
          title: "Precio en tendencia ascendente",
          detail: `El precio en ${supplierName.get(pref) ?? "el proveedor preferente"} ha subido un ${change.toFixed(0)}% en el último periodo.`,
        });
      }
    }
  }

  // 2) Rotura de stock en supplier X — latest snapshot has quantity=0.
  const latestBySupplier = new Map<string, SupplierStockSnapshot>();
  for (const s of stocks) {
    const current = latestBySupplier.get(s.supplier_id);
    if (!current || s.snapshot_at > current.snapshot_at) {
      latestBySupplier.set(s.supplier_id, s);
    }
  }
  for (const [supId, snap] of latestBySupplier) {
    if (snap.quantity === 0) {
      out.push({
        id: `rotura_${supId}`,
        severity: "critical",
        title: `Rotura de stock en ${supplierName.get(supId) ?? "supplier"}`,
        detail: `Sin existencias desde ${snap.snapshot_at}.`,
      });
    }
  }

  // 3) Demanda creciente — count consumption events last 30 vs prior 30 days.
  const now = Date.now();
  const thirtyDaysAgo = now - 30 * 86400000;
  const sixtyDaysAgo = now - 60 * 86400000;
  const recent = events.filter(
    (e) => e.kind === "consumption" && new Date(e.occurred_at).getTime() >= thirtyDaysAgo,
  ).length;
  const prior = events.filter((e) => {
    if (e.kind !== "consumption") return false;
    const t = new Date(e.occurred_at).getTime();
    return t >= sixtyDaysAgo && t < thirtyDaysAgo;
  }).length;
  if (recent > prior && recent > 0) {
    out.push({
      id: "demanda",
      severity: "info",
      title: "Demanda creciente detectada",
      detail: `${recent} consumos en los últimos 30 días (frente a ${prior} el mes anterior).`,
    });
  }

  // 4) Stock acumulado a precio alto — average purchase cost > current preferred 100u price.
  const purchases = events.filter((e) => e.kind === "purchase");
  if (purchases.length > 0 && pref) {
    const avgUnit =
      purchases.reduce((acc, e) => acc + Number(e.unit_cost ?? 0), 0) / purchases.length;
    const latestPref = prices
      .filter((p) => p.supplier_id === pref && p.qty_tier === 100)
      .sort((a, b) => (a.valid_from < b.valid_from ? 1 : -1))[0];
    const currentPref = latestPref ? Number(latestPref.price) : null;
    if (currentPref !== null && avgUnit > currentPref) {
      const pct = ((avgUnit - currentPref) / currentPref) * 100;
      out.push({
        id: "stock_caro",
        severity: "info",
        title: "Stock acumulado a precio alto",
        detail: `El coste medio de compra (${formatEur(avgUnit)}) está un ${pct.toFixed(0)}% por encima del precio actual.`,
      });
    }
  }

  return out;
}

const SEVERITY_META = {
  warning: { Icon: TrendingUp, cls: "border-amber-200 bg-amber-50 text-amber-800" },
  info: { Icon: ArrowUpRight, cls: "border-sky-200 bg-sky-50 text-sky-800" },
  critical: { Icon: PackageX, cls: "border-red-200 bg-red-50 text-red-800" },
} as const;

export function HistorialDeComprasModal({
  open,
  onOpenChange,
  component,
  stockEvents,
  suppliers,
  supplierPrices,
  supplierStocks,
}: HistorialDeComprasModalProps) {
  const series = useMemo(
    () => buildStockSeries(stockEvents, component.stock),
    [stockEvents, component.stock],
  );
  const supplierAggregates = useMemo(
    () => aggregatePurchasesBySupplier(stockEvents),
    [stockEvents],
  );
  const purchases = stockEvents.filter((e) => e.kind === "purchase");
  const totalInvested = purchases.reduce((acc, e) => acc + Number(e.total_cost ?? 0), 0);
  const totalUnitsPurchased = purchases.reduce((acc, e) => acc + e.quantity, 0);
  const avgUnitCost = totalUnitsPurchased > 0 ? totalInvested / totalUnitsPurchased : 0;
  const alerts = useMemo(
    () => buildAlerts(component, stockEvents, supplierPrices, supplierStocks, suppliers),
    [component, stockEvents, supplierPrices, supplierStocks, suppliers],
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] w-[min(90vw,1100px)] max-w-none overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-lg">
            Historial de compras —{" "}
            <span className="font-mono text-text-secondary">{component.mpn}</span>{" "}
            <span className="text-text-secondary">·</span> {component.name}
          </DialogTitle>
        </DialogHeader>

        {/* Stock interno con eventos */}
        <section className="rounded-lg border border-border p-4">
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-text-secondary">
            Stock interno con eventos
          </h3>
          <div className="h-64">
            {series.length === 0 ? (
              <p className="flex h-full items-center justify-center text-sm text-text-secondary">
                Sin eventos registrados todavía.
              </p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={series} margin={{ top: 10, right: 16, bottom: 0, left: -8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="date" fontSize={11} stroke="#6b7280" />
                  <YAxis fontSize={11} stroke="#6b7280" />
                  <Tooltip content={<StockEventTooltip />} />
                  <Line
                    type="monotone"
                    dataKey="stock"
                    stroke="#0ea5e9"
                    strokeWidth={2}
                    dot={<CustomDot />}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
          <p className="mt-2 text-xs text-text-secondary">
            <span className="mr-3 inline-flex items-center gap-1">
              <span className="inline-block size-2 rounded-full bg-emerald-500" />
              Compra
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="inline-block size-2 rounded-full bg-red-500" />
              Consumo
            </span>
          </p>
        </section>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.4fr_1fr]">
          {/* Proveedor más comprado */}
          <section className="rounded-lg border border-border p-4">
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-text-secondary">
              Proveedor más comprado
            </h3>
            <div className="h-56">
              {supplierAggregates.length === 0 ? (
                <p className="flex h-full items-center justify-center text-sm text-text-secondary">
                  Sin compras registradas.
                </p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={supplierAggregates}
                    margin={{ top: 10, right: 16, bottom: 0, left: -8 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="supplierName" fontSize={11} stroke="#6b7280" />
                    <YAxis fontSize={11} stroke="#6b7280" />
                    <Tooltip
                      formatter={(value, name) => {
                        if (name === "qty") return [`${String(value)} uds`, "Cantidad"];
                        return [formatEur(Number(value)), "Coste total"];
                      }}
                    />
                    <Legend />
                    <Bar dataKey="qty" name="Cantidad" fill="#e91e8c" radius={[4, 4, 0, 0]}>
                      {supplierAggregates.map((s, idx) => (
                        <Cell key={s.supplierName} fill={idx === 0 ? "#e91e8c" : "#0ea5e9"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </section>

          {/* Estadísticas de compra */}
          <section className="rounded-lg border border-border p-4">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-secondary">
              Estadísticas de compra
            </h3>
            <dl className="space-y-3 text-sm">
              <Stat label="Coste total del componente" value={formatEur(totalInvested)} />
              <Stat
                label="Coste medio del componente"
                value={
                  <span>
                    {formatEur(avgUnitCost)}{" "}
                    <span className="text-xs text-text-secondary">
                      ({totalUnitsPurchased} uds compradas)
                    </span>
                  </span>
                }
              />
              <Stat
                label="Total invertido"
                value={
                  <span className="text-base font-semibold text-brand">
                    {formatEur(totalInvested)}
                  </span>
                }
              />
              <p className="text-xs text-text-secondary">
                Basado en todas las compras registradas (no incluye consumos).
              </p>
            </dl>
          </section>
        </div>

        {/* Alertas y recomendaciones */}
        <section className="rounded-lg border border-border p-4">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-text-secondary">
            <ShieldAlert className="size-4" />
            Alertas y recomendaciones
          </h3>
          {alerts.length === 0 ? (
            <p className="text-sm text-text-secondary">Sin alertas activas.</p>
          ) : (
            <ul className="space-y-2">
              {alerts.map((a) => {
                const meta = SEVERITY_META[a.severity];
                const Icon = meta.Icon;
                return (
                  <li
                    key={a.id}
                    className={cn(
                      "flex items-start gap-2 rounded-md border px-3 py-2 text-sm",
                      meta.cls,
                    )}
                  >
                    <Icon className="mt-0.5 size-4 shrink-0" />
                    <div>
                      <p className="font-semibold">{a.title}</p>
                      <p className="text-xs opacity-90">{a.detail}</p>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
            Cerrar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-xs uppercase tracking-wide text-text-secondary">{label}</dt>
      <dd className="text-sm font-medium text-text-primary">{value}</dd>
    </div>
  );
}

// Silence unused-import warning if AlertTriangle is removed later.
void AlertTriangle;
