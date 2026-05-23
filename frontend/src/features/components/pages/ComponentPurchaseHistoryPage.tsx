import { useParams, useSearchParams } from "react-router-dom";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { DashboardLayout } from "@/app/layout/DashboardLayout";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatEuros } from "@/lib/format/currency";

import { ComponentDetailTabs } from "../components/ComponentDetailTabs";
import { ComponentHeaderCard } from "../components/ComponentHeaderCard";
import { useComponent } from "../hooks/use-component";
import { useComponentPurchases } from "../hooks/use-component-purchases";

const PAGE_SIZE = 25;

export function ComponentPurchaseHistoryPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const page = Number(searchParams.get("page") ?? "1") || 1;

  const componentQuery = useComponent(id);
  const purchasesQuery = useComponentPurchases(id, page, PAGE_SIZE);

  if (!id || componentQuery.isLoading) {
    return (
      <DashboardLayout>
        <p className="text-sm text-text-secondary">Cargando componente…</p>
      </DashboardLayout>
    );
  }
  if (!componentQuery.data) {
    return (
      <DashboardLayout>
        <p className="text-sm text-destructive">No se encontró el componente.</p>
      </DashboardLayout>
    );
  }

  const items = purchasesQuery.data?.items ?? [];
  const total = purchasesQuery.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // Chart wants ascending dates.
  const chartData = [...items]
    .sort(
      (a, b) =>
        new Date(a.purchased_at).getTime() - new Date(b.purchased_at).getTime(),
    )
    .map((p) => ({ date: p.purchased_at, unit_cost: Number(p.unit_cost) }));

  function gotoPage(target: number) {
    const next = new URLSearchParams(searchParams);
    if (target <= 1) next.delete("page");
    else next.set("page", String(target));
    setSearchParams(next);
  }

  return (
    <DashboardLayout>
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <ComponentHeaderCard component={componentQuery.data} />
        <ComponentDetailTabs componentId={id} />

        <section className="rounded-lg border border-border bg-white p-6 shadow-sm">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-text-secondary">
            Evolución del coste unitario
          </h2>
          <div className="h-64 w-full">
            {chartData.length === 0 ? (
              <p className="text-sm text-text-secondary">
                Aún no hay compras registradas.
              </p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="date" fontSize={12} stroke="#6b7280" />
                  <YAxis fontSize={12} stroke="#6b7280" />
                  <Tooltip
                    formatter={(value) => formatEuros(value as number)}
                    labelFormatter={(label) => `Fecha: ${label as string}`}
                  />
                  <Line
                    type="monotone"
                    dataKey="unit_cost"
                    stroke="#0ea5e9"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>

        <section className="rounded-md border border-border bg-white">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Fecha</TableHead>
                <TableHead className="text-right">Cantidad</TableHead>
                <TableHead>Proveedor</TableHead>
                <TableHead className="text-right">Costo unitario</TableHead>
                <TableHead className="text-right">Costo total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-text-secondary">
                    Aún no hay compras registradas
                  </TableCell>
                </TableRow>
              ) : (
                items.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell>{p.purchased_at}</TableCell>
                    <TableCell className="text-right">{p.quantity}</TableCell>
                    <TableCell>{p.supplier}</TableCell>
                    <TableCell className="text-right">
                      {formatEuros(p.unit_cost)}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatEuros(p.total_cost)}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </section>

        {pageCount > 1 && (
          <div className="flex items-center justify-end gap-3 text-sm text-text-secondary">
            <span>
              Página {page} de {pageCount}
            </span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => gotoPage(page - 1)}
              disabled={page <= 1}
            >
              Anterior
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => gotoPage(page + 1)}
              disabled={page >= pageCount}
            >
              Siguiente
            </Button>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
