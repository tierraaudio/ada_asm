import { ChartPie, History, PackageX, ShieldAlert } from "lucide-react";
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
import { periodCutoff, PeriodToggle, type Period } from "@/features/shared/charts/PeriodToggle";
import { cn } from "@/lib/utils/cn";

import type { StockEvent } from "@/features/components/types";

import type { SupplierPurchaseSummary } from "../api/modules-api";
import type { Module } from "../types";

interface HistorialFabricacionModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  module: Module;
  stockEvents: StockEvent[];
  supplierPurchases: SupplierPurchaseSummary[];
}

interface StockPoint {
  date: string;
  stock: number;
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
    (acc, e) => acc + (e.kind === "fabricated" ? e.quantity : -e.quantity),
    0,
  );
  let running = currentStock - sumSigned;
  return asc.map((e) => {
    running += e.kind === "fabricated" ? e.quantity : -e.quantity;
    return { date: e.occurred_at, stock: running, event: e };
  });
}

function CustomDot(props: { cx?: number; cy?: number; payload?: StockPoint }) {
  const { cx, cy, payload } = props;
  if (cx == null || cy == null || !payload) return null;
  const isFabricated = payload.event.kind === "fabricated";
  const fill = isFabricated ? "#22c55e" : "#ef4444";
  return <circle cx={cx} cy={cy} r={4} fill={fill} stroke="#fff" strokeWidth={1.5} />;
}

interface ChartTooltipPayload {
  payload: StockPoint;
}

function StockEventTooltip(props: { active?: boolean; payload?: ChartTooltipPayload[] }) {
  const { active, payload } = props;
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0]?.payload;
  if (!point) return null;
  const { stock, event } = point;
  const isFabricated = event.kind === "fabricated";
  const unit = event.unit_cost != null ? Number(event.unit_cost) : null;
  const total = event.total_cost != null ? Number(event.total_cost) : null;

  return (
    <div className="min-w-[200px] rounded-md border border-border bg-white p-3 text-sm shadow-md">
      <p className="text-base font-semibold text-text-primary">
        {formatDdMmYyyy(event.occurred_at)}
      </p>
      <p className="mt-1 text-text-primary">
        Stock: <span className="font-medium">{stock} uds</span>
      </p>
      {isFabricated ? (
        <>
          <p className="mt-1 font-semibold text-emerald-600">+ {event.quantity} fabricados</p>
          {unit != null && <p className="text-text-secondary">Coste/ud: €{unit.toFixed(2)}</p>}
          {total != null && <p className="text-text-secondary">Total lote: {formatEur(total)}</p>}
        </>
      ) : (
        <>
          <p className="mt-1 font-semibold text-red-600">-{event.quantity} entregados</p>
          <p className="text-text-secondary">Cliente: {event.customer_name_snapshot ?? "—"}</p>
          {event.customer_id_holded && (
            <p className="text-xs text-text-secondary">
              Holded ID: <span className="font-mono">{event.customer_id_holded}</span>
            </p>
          )}
        </>
      )}
    </div>
  );
}

function SupplierBarTooltip(props: {
  active?: boolean;
  payload?: Array<{ payload: SupplierPurchaseSummary }>;
}) {
  const { active, payload } = props;
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return (
    <div className="min-w-[180px] rounded-md border border-border bg-white p-3 text-sm shadow-md">
      <p className="font-semibold text-text-primary">{row.supplier_name}</p>
      <p className="text-text-secondary">
        <span className="mr-1 inline-block size-2 rounded-sm bg-emerald-500" />
        Cantidad: <span className="font-medium text-text-primary">{row.qty} uds</span>
      </p>
      <p className="text-text-secondary">
        <span className="mr-1 inline-block size-2 rounded-sm bg-sky-500" />
        Coste total:{" "}
        <span className="font-medium text-text-primary">{formatEur(Number(row.cost))}</span>
      </p>
    </div>
  );
}

/**
 * Weighted FIFO cost of the units that make up the current module stock,
 * walking fabricated events from most-recent backwards. Mirrors the
 * components' "Coste medio del stock actual" logic.
 */
function weightedStockCost(
  events: StockEvent[],
  currentStock: number,
): { weightedUnit: number; coveredUnits: number } {
  if (currentStock <= 0) return { weightedUnit: 0, coveredUnits: 0 };
  const fabricatedDesc = events
    .filter((e) => e.kind === "fabricated")
    .sort((a, b) => (a.occurred_at < b.occurred_at ? 1 : -1));
  let remaining = currentStock;
  let weightedSum = 0;
  let coveredUnits = 0;
  for (const f of fabricatedDesc) {
    if (remaining <= 0) break;
    const unit = f.unit_cost != null ? Number(f.unit_cost) : 0;
    const take = Math.min(f.quantity, remaining);
    weightedSum += unit * take;
    coveredUnits += take;
    remaining -= take;
  }
  const weightedUnit = coveredUnits > 0 ? weightedSum / coveredUnits : 0;
  return { weightedUnit, coveredUnits };
}

function buildAlerts(
  events: StockEvent[],
  fabricationAvgUnit: number,
  stockAvgUnit: number,
): Array<{ id: string; severity: "warning" | "info"; title: string; detail: string }> {
  const out: Array<{
    id: string;
    severity: "warning" | "info";
    title: string;
    detail: string;
  }> = [];
  const fabricated = events.filter((e) => e.kind === "fabricated");
  const delivered = events.filter((e) => e.kind === "delivered");

  if (fabricated.length >= 2 && stockAvgUnit > fabricationAvgUnit) {
    const pct = ((stockAvgUnit - fabricationAvgUnit) / fabricationAvgUnit) * 100;
    out.push({
      id: "stock_caro",
      severity: "info",
      title: "Stock acumulado a coste alto",
      detail: `El coste medio del stock actual (${formatEur(stockAvgUnit)}) está un ${pct.toFixed(0)}% por encima del coste medio histórico (${formatEur(fabricationAvgUnit)}).`,
    });
  }

  if (delivered.length === 0 && fabricated.length > 0) {
    out.push({
      id: "no_deliveries",
      severity: "warning",
      title: "Sin entregas registradas",
      detail: "El módulo se ha fabricado pero todavía no se ha entregado a ningún cliente.",
    });
  }

  return out;
}

const SEVERITY_META = {
  warning: { Icon: PackageX, cls: "border-amber-200 bg-amber-50 text-amber-800" },
  info: { Icon: ShieldAlert, cls: "border-sky-200 bg-sky-50 text-sky-800" },
} as const;

export function HistorialFabricacionModal({
  open,
  onOpenChange,
  module,
  stockEvents,
  supplierPurchases,
}: HistorialFabricacionModalProps) {
  const [stockPeriod, setStockPeriod] = useState<Period>("year");

  const filteredEvents = useMemo(() => {
    const cutoff = periodCutoff(stockPeriod);
    return stockEvents.filter((e) => new Date(e.occurred_at) >= cutoff);
  }, [stockEvents, stockPeriod]);

  const series = useMemo(
    () => buildStockSeries(filteredEvents, module.stock),
    [filteredEvents, module.stock],
  );

  const fabricated = stockEvents.filter((e) => e.kind === "fabricated");
  const totalInvested = fabricated.reduce((acc, e) => acc + Number(e.total_cost ?? 0), 0);
  const totalUnitsFabricated = fabricated.reduce((acc, e) => acc + e.quantity, 0);
  const fabricationAvgUnit = totalUnitsFabricated > 0 ? totalInvested / totalUnitsFabricated : 0;
  const { weightedUnit: stockAvgUnit } = useMemo(
    () => weightedStockCost(stockEvents, module.stock),
    [stockEvents, module.stock],
  );
  const totalInStock = stockAvgUnit * module.stock;

  const alerts = useMemo(
    () => buildAlerts(stockEvents, fabricationAvgUnit, stockAvgUnit),
    [stockEvents, fabricationAvgUnit, stockAvgUnit],
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] w-[min(90vw,1240px)] max-w-none overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-lg">
            Histórico de fabricación —{" "}
            <span className="font-mono text-text-secondary">{module.sku}</span>{" "}
            <span className="text-text-secondary">·</span> {module.name}
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
              Fabricado
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="inline-block size-2 rounded-full bg-red-500" />
              Entregado
            </span>
          </p>
        </section>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* Proveedor más comprado (agregado desde los hijos componente) */}
          <section className="rounded-lg border border-border p-4">
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-text-secondary">
              <ChartPie className="size-4 text-brand" />
              Proveedor más comprado (componentes)
            </h3>
            <div className="h-72">
              {supplierPurchases.length === 0 ? (
                <p className="flex h-full items-center justify-center text-sm text-text-secondary">
                  Sin compras de componentes registradas.
                </p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={supplierPurchases.map((s) => ({
                      ...s,
                      qty: s.qty,
                      cost: Number(s.cost),
                    }))}
                    margin={{ top: 10, right: 16, bottom: 0, left: -8 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="supplier_name" fontSize={11} stroke="#6b7280" />
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

          {/* Estadísticas de fabricación */}
          <section className="rounded-lg border border-border p-4">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-text-secondary">
              <ChartPie className="size-4 text-brand" />
              Estadísticas de fabricación
            </h3>
            <div className="space-y-3">
              <StatBlock
                label="Coste medio de fabricación"
                value={formatEur(fabricationAvgUnit)}
                helper="Basado en todas las fabricaciones"
              />
              <StatBlock
                label="Coste medio de fabricación del stock actual"
                value={formatEur(stockAvgUnit)}
                helper="Media ponderada (FIFO) sobre los lotes que componen el stock vigente"
              />
              <StatBlock
                label="Total invertido en fabricación"
                value={formatEur(totalInStock)}
                helper={`${module.stock} unidades × ${formatEur(stockAvgUnit)} promedio`}
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
