import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
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

import { ComponentAlertsPanel } from "../components/ComponentAlertsPanel";
import { ComponentDetailTabs } from "../components/ComponentDetailTabs";
import { ComponentHeaderCard } from "../components/ComponentHeaderCard";
import { ConfirmDeleteDialog } from "../components/ConfirmDeleteDialog";
import { useComponent } from "../hooks/use-component";
import { useDeleteComponent } from "../hooks/use-component-mutations";
import { useComponentPurchases } from "../hooks/use-component-purchases";

export function ComponentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const componentQuery = useComponent(id);
  const purchasesQuery = useComponentPurchases(id, 1, 100);
  const deleteMutation = useDeleteComponent();

  const stockSeries = useMemo(() => {
    const items = purchasesQuery.data?.items ?? [];
    const sorted = [...items].sort(
      (a, b) =>
        new Date(a.purchased_at).getTime() - new Date(b.purchased_at).getTime(),
    );
    let cumulative = 0;
    return sorted.map((p) => {
      cumulative += p.quantity;
      return { date: p.purchased_at, stock: cumulative };
    });
  }, [purchasesQuery.data]);

  if (componentQuery.isLoading || !id) {
    return (
      <DashboardLayout>
        <p className="text-sm text-text-secondary">Cargando componente…</p>
      </DashboardLayout>
    );
  }
  if (componentQuery.isError || !componentQuery.data) {
    return (
      <DashboardLayout>
        <p className="text-sm text-destructive">No se encontró el componente.</p>
      </DashboardLayout>
    );
  }

  const component = componentQuery.data;

  return (
    <DashboardLayout>
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <div className="flex items-center justify-between">
          <Button variant="ghost" onClick={() => navigate("/components")}>
            ← Volver al catálogo
          </Button>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => navigate(`/components/${id}/edit`)}
            >
              Editar
            </Button>
            <ConfirmDeleteDialog
              trigger={<Button variant="destructive">Eliminar</Button>}
              onConfirm={async () => {
                await deleteMutation.mutateAsync(id);
                navigate("/components");
              }}
            />
          </div>
        </div>

        <ComponentHeaderCard component={component} />
        <ComponentDetailTabs componentId={id} />

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr_1fr]">
          <section className="rounded-lg border border-border bg-white p-6 shadow-sm">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-text-secondary">
              Descripción
            </h2>
            <p className="mb-6 text-sm text-text-primary">
              {component.description ?? "Sin descripción."}
            </p>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-text-secondary">
              Evolución del stock
            </h2>
            <div className="h-64 w-full">
              {stockSeries.length === 0 ? (
                <p className="text-sm text-text-secondary">
                  Aún no hay compras registradas.
                </p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={stockSeries}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="date" fontSize={12} stroke="#6b7280" />
                    <YAxis fontSize={12} stroke="#6b7280" />
                    <Tooltip />
                    <Line
                      type="monotone"
                      dataKey="stock"
                      stroke="#0ea5e9"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </section>
          <ComponentAlertsPanel
            component={component}
            purchases={purchasesQuery.data?.items ?? []}
          />
        </div>
      </div>
    </DashboardLayout>
  );
}
