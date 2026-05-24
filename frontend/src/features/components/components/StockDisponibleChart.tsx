import { useMemo } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { Supplier, SupplierStockSnapshot } from "../types";

const SUPPLIER_COLOURS = [
  "#e91e8c",
  "#0f172a",
  "#0ea5e9",
  "#22c55e",
  "#f59e0b",
];

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
): ChartPoint[] {
  const name = new Map(suppliers.map((s) => [s.id, s.name]));
  const byDate = new Map<string, ChartPoint>();
  for (const snap of snapshots) {
    const point = byDate.get(snap.snapshot_at) ?? { date: snap.snapshot_at };
    const sup = name.get(snap.supplier_id);
    if (sup) point[sup] = snap.quantity;
    byDate.set(snap.snapshot_at, point);
  }
  return [...byDate.values()].sort((a, b) => (a.date < b.date ? -1 : 1));
}

export function StockDisponibleChart({
  snapshots,
  suppliers,
}: StockDisponibleChartProps) {
  const data = useMemo(() => buildSeries(snapshots, suppliers), [snapshots, suppliers]);
  const names = useMemo(() => suppliers.map((s) => s.name), [suppliers]);

  if (data.length === 0) {
    return (
      <p className="flex h-full items-center justify-center text-sm text-text-secondary">
        Sin snapshots de stock todavía.
      </p>
    );
  }

  return (
    <div className="h-full min-h-[220px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 16, bottom: 0, left: -8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="date" fontSize={11} stroke="#6b7280" />
          <YAxis fontSize={11} stroke="#6b7280" />
          <Tooltip
            formatter={(v) => `${v} uds`}
            labelFormatter={(label) => `Fecha: ${label as string}`}
          />
          <Legend />
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
  );
}
