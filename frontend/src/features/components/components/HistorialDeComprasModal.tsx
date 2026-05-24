import { ArrowUpRight, ChartPie, History, PackageX, ShieldAlert, TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils/cn";

import type {
  ComponentDetail,
  StockEvent,
  Supplier,
  SupplierPrice,
  SupplierStockSnapshot,
} from "../types";
import { periodCutoff, PeriodToggle, type Period } from "@/features/shared/charts/PeriodToggle";

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
  /** YYYY-MM-DD */
  date: string;
  /** Running stock after this event. */
  stock: number;
  /** Render value for the green dot (purchase). */
  purchase?: number | undefined;
  /** Render value for the red dot (consumption). */
  consumption?: number | undefined;
  /** Original event payload — drives the tooltip. */
  event: StockEvent;
}

function formatDdMmYyyy(iso: string): string {
  const datePart = iso.split("T")[0] ?? iso;
  const [y = "????", m = "??", d = "??"] = datePart.split("-");
  return `${d}/${m}/${y}`;
}

function formatEur(value: number | null | undefined, fractionDigits = 2): string {
  if (value == null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("es-ES", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(value);
}

function buildStockSeries(events: StockEvent[], currentStock: number): StockPoint[] {
  const asc = [...events].sort((a, b) =>
    a.occurred_at < b.occurred_at ? -1 : a.occurred_at > b.occurred_at ? 1 : 0,
  );
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
      event: e,
    };
  });
}

interface ChartTooltipPayload {
  payload: StockPoint;
}

function CustomDot(props: { cx?: number; cy?: number; payload?: StockPoint }) {
  const { cx, cy, payload } = props;
  if (cx == null || cy == null || !payload) return null;
  const isPurchase = payload.event.kind === "purchase";
  const fill = isPurchase ? "#22c55e" : "#ef4444";
  return <circle cx={cx} cy={cy} r={4} fill={fill} stroke="#fff" strokeWidth={1.5} />;
}

function StockEventTooltip(props: { active?: boolean; payload?: ChartTooltipPayload[] }) {
  const { active, payload } = props;
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0]?.payload;
  if (!point) return null;
  const { stock, event } = point;
  const isPurchase = event.kind === "purchase";
  const unit = event.unit_cost != null ? Number(event.unit_cost) : null;
  const total = event.total_cost != null ? Number(event.total_cost) : null;

  return (
    <div className="min-w-[180px] rounded-md border border-border bg-white p-3 text-sm shadow-md">
      <p className="text-base font-semibold text-text-primary">
        {formatDdMmYyyy(event.occurred_at)}
      </p>
      <p className="mt-1 text-text-primary">
        Stock: <span className="font-medium">{stock} uds</span>
      </p>
      {isPurchase ? (
        <>
          <p className="mt-1 font-semibold text-emerald-600">+ {event.quantity} compradas</p>
          <p className="text-text-secondary">Proveedor: {event.supplier_name ?? "—"}</p>
          {unit != null && <p className="text-text-secondary">Precio: €{unit.toFixed(2)}/ud</p>}
          {total != null && <p className="text-text-secondary">Total: {formatEur(total)}</p>}
        </>
      ) : (
        <>
          <p className="mt-1 font-semibold text-red-600">-{event.quantity} usadas</p>
          <p className="text-text-secondary">Proyecto: {event.project_name_snapshot ?? "—"}</p>
        </>
      )}
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
  return [...byName.values()].sort((a, b) => b.cost - a.cost);
}

/**
 * FIFO from most recent purchases summing to `currentStock`. Returns the
 * weighted average unit cost of the units that make up the current stock,
 * plus how many of those units were "above average" (used by the
 * "stock acumulado a precio alto" alert).
 */
function weightedStockCost(
  events: StockEvent[],
  currentStock: number,
): { weightedUnit: number; coveredUnits: number } {
  if (currentStock <= 0) return { weightedUnit: 0, coveredUnits: 0 };
  const purchasesDesc = events
    .filter((e) => e.kind === "purchase")
    .sort((a, b) => (a.occurred_at < b.occurred_at ? 1 : -1));
  let remaining = currentStock;
  let weightedSum = 0;
  let coveredUnits = 0;
  for (const p of purchasesDesc) {
    if (remaining <= 0) break;
    const unit = p.unit_cost != null ? Number(p.unit_cost) : 0;
    const take = Math.min(p.quantity, remaining);
    weightedSum += unit * take;
    coveredUnits += take;
    remaining -= take;
  }
  const weightedUnit = coveredUnits > 0 ? weightedSum / coveredUnits : 0;
  return { weightedUnit, coveredUnits };
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

  // 4) Stock acumulado a precio alto — weighted stock cost > current preferred 100u price.
  if (pref && component.stock > 0) {
    const { weightedUnit } = weightedStockCost(events, component.stock);
    const latestPref = prices
      .filter((p) => p.supplier_id === pref && p.qty_tier === 100)
      .sort((a, b) => (a.valid_from < b.valid_from ? 1 : -1))[0];
    const currentPref = latestPref ? Number(latestPref.price) : null;
    if (currentPref != null && weightedUnit > currentPref) {
      const pct = ((weightedUnit - currentPref) / currentPref) * 100;
      out.push({
        id: "stock_caro",
        severity: "info",
        title: "Stock acumulado a precio alto",
        detail: `El coste medio del stock actual (${formatEur(weightedUnit)}) está un ${pct.toFixed(0)}% por encima del precio actual (${formatEur(currentPref)}).`,
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

interface BarTooltipPayload {
  dataKey: string;
  name: string;
  value: number;
  color: string;
  payload: SupplierAggregate;
}

function SupplierBarTooltip(props: { active?: boolean; payload?: BarTooltipPayload[] }) {
  const { active, payload } = props;
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return (
    <div className="min-w-[160px] rounded-md border border-border bg-white p-3 text-sm shadow-md">
      <p className="font-semibold text-text-primary">{row.supplierName}</p>
      <p className="text-text-secondary">
        <span className="mr-1 inline-block size-2 rounded-sm bg-emerald-500" />
        Cantidad: <span className="font-medium text-text-primary">{row.qty} uds</span>
      </p>
      <p className="text-text-secondary">
        <span className="mr-1 inline-block size-2 rounded-sm bg-sky-500" />
        Coste total: <span className="font-medium text-text-primary">{formatEur(row.cost)}</span>
      </p>
    </div>
  );
}

export function HistorialDeComprasModal({
  open,
  onOpenChange,
  component,
  stockEvents,
  suppliers,
  supplierPrices,
  supplierStocks,
}: HistorialDeComprasModalProps) {
  const [stockPeriod, setStockPeriod] = useState<Period>("year");
  const filteredStockEvents = useMemo(() => {
    const cutoff = periodCutoff(stockPeriod);
    return stockEvents.filter((e) => new Date(e.occurred_at) >= cutoff);
  }, [stockEvents, stockPeriod]);
  const series = useMemo(
    () => buildStockSeries(filteredStockEvents, component.stock),
    [filteredStockEvents, component.stock],
  );
  const supplierAggregates = useMemo(
    () => aggregatePurchasesBySupplier(stockEvents),
    [stockEvents],
  );

  const purchases = stockEvents.filter((e) => e.kind === "purchase");
  const totalInvested = purchases.reduce((acc, e) => acc + Number(e.total_cost ?? 0), 0);
  const totalUnitsPurchased = purchases.reduce((acc, e) => acc + e.quantity, 0);
  const componentAvgUnit = totalUnitsPurchased > 0 ? totalInvested / totalUnitsPurchased : 0;
  const { weightedUnit: stockAvgUnit } = useMemo(
    () => weightedStockCost(stockEvents, component.stock),
    [stockEvents, component.stock],
  );
  const totalInStock = stockAvgUnit * component.stock;

  const alerts = useMemo(
    () => buildAlerts(component, stockEvents, supplierPrices, supplierStocks, suppliers),
    [component, stockEvents, supplierPrices, supplierStocks, suppliers],
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] w-[min(90vw,1240px)] max-w-none overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-lg">
            Historial de compras —{" "}
            <span className="font-mono text-text-secondary">{component.mpn}</span>{" "}
            <span className="text-text-secondary">·</span> {component.name}
          </DialogTitle>
        </DialogHeader>

        {/* Stock interno con eventos */}
        <section className="rounded-lg border border-border p-4">
          <div className="mb-2 flex items-center justify-between gap-3">
            <h3 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-text-secondary">
              <History className="size-4" />
              Stock interno con eventos
            </h3>
            <PeriodToggle value={stockPeriod} onChange={setStockPeriod} />
          </div>
          <div className="h-64">
            {series.length === 0 ? (
              <p className="flex h-full items-center justify-center text-sm text-text-secondary">
                Sin eventos en el rango seleccionado.
              </p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={series} margin={{ top: 10, right: 16, bottom: 0, left: -8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis
                    dataKey="date"
                    fontSize={11}
                    stroke="#6b7280"
                    tickFormatter={(v: string) => {
                      const [, m = "??", d = "??"] = v.split("-");
                      return `${d}/${m}`;
                    }}
                  />
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

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* Proveedor más comprado */}
          <section className="rounded-lg border border-border p-4">
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-text-secondary">
              <ChartPie className="size-4 text-brand" />
              Proveedor más comprado
            </h3>
            <div className="h-72">
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
                    <Tooltip content={<SupplierBarTooltip />} cursor={{ fill: "#f3f4f6" }} />
                    <Legend
                      wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
                      formatter={(value: string) =>
                        value === "qty" ? "Cantidad (uds)" : "Coste total (€)"
                      }
                    />
                    <Bar dataKey="qty" name="qty" fill="#22c55e" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="cost" name="cost" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </section>

          {/* Estadísticas de compra */}
          <section className="rounded-lg border border-border p-4">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-text-secondary">
              <ChartPie className="size-4 text-brand" />
              Estadísticas de compra
            </h3>
            <div className="space-y-3">
              <StatBlock
                label="Coste medio del componente"
                value={formatEur(componentAvgUnit)}
                helper="Basado en todas las compras"
              />
              <StatBlock
                label="Coste medio del stock actual"
                value={formatEur(stockAvgUnit)}
                helper="Media ponderada del stock en almacén"
              />
              <StatBlock
                label="Total invertido en stock"
                value={formatEur(totalInStock)}
                helper={`${component.stock} unidades × ${formatEur(stockAvgUnit)} promedio`}
                emphasis
              />
            </div>
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
      </DialogContent>
    </Dialog>
  );
}

function StatBlock({
  label,
  value,
  helper,
  emphasis = false,
}: {
  label: string;
  value: string;
  helper: string;
  emphasis?: boolean;
}) {
  return (
    <div className="rounded-md border border-border bg-white px-4 py-3">
      <p className="text-xs text-text-secondary">{label}</p>
      <p
        className={cn(
          "mt-1 text-2xl font-semibold leading-none",
          emphasis ? "text-brand" : "text-text-primary",
        )}
      >
        {value}
      </p>
      <p className="mt-1 text-xs text-text-secondary">{helper}</p>
    </div>
  );
}
