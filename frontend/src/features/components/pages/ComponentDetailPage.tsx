import { ArrowLeft, Edit3 } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { DashboardLayout } from "@/app/layout/DashboardLayout";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import { ComponentHeaderCard } from "../components/ComponentHeaderCard";
import { NatoScoringSection } from "../components/NatoScoringSection";
import { useComponentDetail } from "../hooks/use-component-detail";
import { useSuppliers } from "../hooks/use-suppliers";

type ModalKey = "historial" | "clasificar" | null;

export function ComponentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const detailQuery = useComponentDetail(id);
  const suppliersQuery = useSuppliers();
  const [openModal, setOpenModal] = useState<ModalKey>(null);

  if (!id || detailQuery.isLoading) {
    return (
      <DashboardLayout>
        <p className="text-sm text-text-secondary">Cargando componente…</p>
      </DashboardLayout>
    );
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <DashboardLayout>
        <p className="text-sm text-destructive">No se encontró el componente.</p>
      </DashboardLayout>
    );
  }

  const component = detailQuery.data;
  const suppliers = suppliersQuery.data ?? [];

  return (
    <DashboardLayout>
      <div className="mx-auto flex w-full max-w-[1920px] flex-col gap-6">
        <header className="flex items-center justify-between">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => navigate("/components")}
          >
            <ArrowLeft className="size-4" />
            Volver al catálogo
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => navigate(`/components/${component.id}/edit`)}
          >
            <Edit3 className="size-4" />
            Editar Componente
          </Button>
        </header>

        <ComponentHeaderCard
          component={component}
          suppliers={suppliers}
          rightSlot={
            <div className="w-full md:w-[480px]">
              <NatoScoringSection
                scoring={component.current_nato_scoring}
                onOpenHistorialDeCompras={() => setOpenModal("historial")}
                onOpenClasificarComponente={() => setOpenModal("clasificar")}
              />
            </div>
          }
        />

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_1.5fr_1fr]">
          <SectionPlaceholder
            title="Precios de hoy"
            description="Tabla por supplier × cantidad (1u/10u/100u/1000u). Conecta con GET /api/v1/components/{id}/supplier-prices en la siguiente iteración."
          />
          <SectionPlaceholder
            title="Histórico de precios"
            description="Gráfica de líneas por supplier con toggles 10/100/1000 uds y Semana/Mes/Año. Datos ya seedeados en supplier_prices."
          />
          <SectionPlaceholder
            title="Stock disponible en proveedores"
            description="Gráfica multi-línea por supplier × tiempo. Datos ya seedeados en supplier_stocks."
          />
        </div>
      </div>

      <PlaceholderModal
        open={openModal === "historial"}
        onOpenChange={(open) => !open && setOpenModal(null)}
        title="Historial de compras"
        body={
          <>
            <p>
              Próxima iteración: gráfica "Stock interno con eventos" + tabla compras +
              estadísticas + alertas y recomendaciones (Figma node 47:20273).
            </p>
            <p>
              Datos ya disponibles en <code>stock_events</code> (purchase + consumption)
              y <code>supplier_prices</code>.
            </p>
          </>
        }
      />
      <PlaceholderModal
        open={openModal === "clasificar"}
        onOpenChange={(open) => !open && setOpenModal(null)}
        title="Clasificar Componente"
        body={
          <>
            <p>
              Próxima iteración: formulario para crear un nuevo scoring OTAN — score,
              tier, fecha, classifications (sub-partes) y alternatives.
            </p>
            <p>
              Endpoint listo: <code>POST /api/v1/components/{component.id}/nato-scorings</code>.
            </p>
          </>
        }
      />
    </DashboardLayout>
  );
}

function SectionPlaceholder({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <section className="flex h-64 flex-col rounded-lg border border-dashed border-border bg-white p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-text-secondary">
        {title}
      </h3>
      <p className="text-xs text-text-secondary">{description}</p>
    </section>
  );
}

function PlaceholderModal({
  open,
  onOpenChange,
  title,
  body,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  body: React.ReactNode;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription className="space-y-2 text-sm">{body}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
            Cerrar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
