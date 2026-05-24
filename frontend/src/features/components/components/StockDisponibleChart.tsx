import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { Supplier, SupplierStockSnapshot } from "../types";
import { periodCutoff, PeriodToggle, type Period } from "./PeriodToggle";

const SUPPLIER_COLOURS = ["#e91e8c", "#0f172a", "#0ea5e9", "#22c55e", "#f59e0b"];

interface StockDisponibleChartProps {
  snapshots: SupplierStockSnapshot[];
  suppliers: Supplier[];
}

interface ChartPoint {
  date: string;
  [supplierName: string]: string | number;
}

function buildSeries(
  snapshots: SupplierStockSnapshot[],
  suppliers: Supplier[],
  period: Period,
): ChartPoint[] {
  const cutoff = periodCutoff(period);
  const name = new Map(suppliers.map((s) => [s.id, s.name]));
  const byDate = new Map<string, ChartPoint>();
  for (const snap of snapshots) {
    if (new Date(snap.snapshot_at) < cutoff) continue;
    const point = byDate.get(snap.snapshot_at) ?? { date: snap.snapshot_at };
    const sup = name.get(snap.supplier_id);
    if (sup) point[sup] = snap.quantity;
    byDate.set(snap.snapshot_at, point);
  }
  return [...byDate.values()].sort((a, b) => (a.date < b.date ? -1 : 1));
}

export function StockDisponibleChart({ snapshots, suppliers }: StockDisponibleChartProps) {
  const [period, setPeriod] = useState<Period>("year");
  const data = useMemo(
    () => buildSeries(snapshots, suppliers, period),
    [snapshots, suppliers, period],
  );
  const names = useMemo(() => suppliers.map((s) => s.name), [suppliers]);

  return (
    <div className="flex h-full min-h-[220px] flex-col">
      <div className="mb-3 flex justify-end">
        <PeriodToggle value={period} onChange={setPeriod} />
      </div>
      {data.length === 0 ? (
        <p className="flex h-full items-center justify-center text-sm text-text-secondary">
          Sin snapshots de stock en el rango seleccionado.
        </p>
      ) : (
        <>
          <div className="min-h-0 flex-1">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data} margin={{ top: 10, right: 16, bottom: 4, left: -8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="date" fontSize={11} stroke="#6b7280" />
                <YAxis fontSize={11} stroke="#6b7280" />
                <Tooltip
                  formatter={(v) => `${v} uds`}
                  labelFormatter={(label) => `Fecha: ${label as string}`}
                />
                {names.map((name, idx) => (
                  <Line
                    key={name}
                    type="monotone"
                    dataKey={name}
                    stroke={SUPPLIER_COLOURS[idx % SUPPLIER_COLOURS.length] ?? "#999"}
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-text-secondary">
            {names.map((name, idx) => (
              <li key={name} className="inline-flex items-center gap-1.5 whitespace-nowrap">
                <span
                  aria-hidden
                  className="inline-block size-2 rounded-full"
                  style={{
                    backgroundColor: SUPPLIER_COLOURS[idx % SUPPLIER_COLOURS.length] ?? "#999",
                  }}
                />
                {name}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
