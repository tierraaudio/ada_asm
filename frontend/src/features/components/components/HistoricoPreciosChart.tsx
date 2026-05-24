import { useMemo, useState } from "react";
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

import { cn } from "@/lib/utils/cn";

import type { Supplier, SupplierPrice } from "../types";

type QtyTier = 1 | 10 | 100 | 1000;
type Period = "week" | "month" | "year";

interface HistoricoPreciosChartProps {
  prices: SupplierPrice[];
  suppliers: Supplier[];
}

// Stable colour per supplier — matches the legend dots in the Figma.
const SUPPLIER_COLOURS = [
  "#e91e8c", // brand pink (DigiKey usually)
  "#0f172a", // slate-900
  "#0ea5e9", // sky-500
  "#22c55e", // green-500
  "#f59e0b", // amber-500
];

function periodCutoff(period: Period): Date {
  const now = new Date();
  const out = new Date(now);
  if (period === "week") out.setDate(now.getDate() - 7);
  else if (period === "month") out.setMonth(now.getMonth() - 1);
  else out.setFullYear(now.getFullYear() - 1);
  return out;
}

interface ChartPoint {
  date: string;
  [supplierName: string]: string | number;
}

function buildChartData(
  prices: SupplierPrice[],
  suppliers: Supplier[],
  qtyTier: QtyTier,
  period: Period,
): ChartPoint[] {
  const supplierName = new Map(suppliers.map((s) => [s.id, s.name]));
  const cutoff = periodCutoff(period);
  const byDate = new Map<string, ChartPoint>();
  for (const p of prices) {
    if (p.qty_tier !== qtyTier) continue;
    if (new Date(p.valid_from) < cutoff) continue;
    const point = byDate.get(p.valid_from) ?? { date: p.valid_from };
    const name = supplierName.get(p.supplier_id);
    if (name) point[name] = Number(p.price);
    byDate.set(p.valid_from, point);
  }
  return [...byDate.values()].sort((a, b) => (a.date < b.date ? -1 : 1));
}

function ToggleGroup<T extends string | number>({
  options,
  value,
  onChange,
}: {
  options: Array<{ value: T; label: string }>;
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex rounded-md border border-border bg-white p-0.5">
      {options.map((opt) => (
        <button
          key={String(opt.value)}
          type="button"
          onClick={() => onChange(opt.value)}
          className={cn(
            "rounded px-3 py-1 text-xs font-medium transition-colors",
            value === opt.value ? "bg-brand text-white" : "text-text-secondary hover:bg-muted",
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

export function HistoricoPreciosChart({ prices, suppliers }: HistoricoPreciosChartProps) {
  const [qtyTier, setQtyTier] = useState<QtyTier>(100);
  const [period, setPeriod] = useState<Period>("year");
  const data = useMemo(
    () => buildChartData(prices, suppliers, qtyTier, period),
    [prices, suppliers, qtyTier, period],
  );
  const supplierNames = useMemo(() => suppliers.map((s) => s.name), [suppliers]);

  return (
    <div className="flex h-full flex-col">
      <div className="mb-3 flex flex-wrap items-center justify-end gap-2">
        <ToggleGroup
          value={qtyTier}
          onChange={(v) => setQtyTier(v as QtyTier)}
          options={[
            { value: 1, label: "1 ud" },
            { value: 10, label: "10 uds" },
            { value: 100, label: "100 uds" },
            { value: 1000, label: "1000 uds" },
          ]}
        />
        <ToggleGroup
          value={period}
          onChange={(v) => setPeriod(v as Period)}
          options={[
            { value: "week", label: "Semana" },
            { value: "month", label: "Mes" },
            { value: "year", label: "Año" },
          ]}
        />
      </div>
      <div className="min-h-[220px] flex-1">
        {data.length === 0 ? (
          <p className="flex h-full items-center justify-center text-sm text-text-secondary">
            Sin datos en el rango seleccionado.
          </p>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 10, right: 16, bottom: 0, left: -8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="date" fontSize={11} stroke="#6b7280" />
              <YAxis
                fontSize={11}
                stroke="#6b7280"
                tickFormatter={(v: number) => `€${v.toFixed(2)}`}
              />
              <Tooltip
                formatter={(v) => `€${Number(v).toFixed(4)}`}
                labelFormatter={(label) => `Fecha: ${label as string}`}
              />
              <Legend />
              {supplierNames.map((name, idx) => (
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
        )}
      </div>
    </div>
  );
}
