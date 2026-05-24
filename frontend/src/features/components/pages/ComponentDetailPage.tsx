import { ArrowLeft, Edit3, History } from "lucide-react";
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
import { HistorialDeComprasModal } from "../components/HistorialDeComprasModal";
import { HistoricoPreciosChart } from "../components/HistoricoPreciosChart";
import { NatoScoringModal } from "../components/NatoScoringModal";
import { NatoScoringSection } from "../components/NatoScoringSection";
import { PreciosDeHoyTable } from "../components/PreciosDeHoyTable";
import { StockDisponibleChart } from "../components/StockDisponibleChart";
import { useComponentDetail } from "../hooks/use-component-detail";
import { useStockEvents, useSupplierPrices, useSupplierStocks } from "../hooks/use-supplier-data";
import { useSuppliers } from "../hooks/use-suppliers";

type ModalKey = "historial" | "scoring" | "clasificar" | null;

export function ComponentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const detailQuery = useComponentDetail(id);
  const suppliersQuery = useSuppliers();
  const pricesQuery = useSupplierPrices(id);
  const stocksQuery = useSupplierStocks(id);
  const stockEventsQuery = useStockEvents(id);
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
  const prices = pricesQuery.data ?? [];
  const stocks = stocksQuery.data ?? [];
  const stockEvents = stockEventsQuery.data?.items ?? [];
  const scoring = component.current_nato_scoring;

  return (
    <DashboardLayout>
      <div className="mx-auto flex w-full max-w-[1920px] flex-col gap-6">
        <header className="flex items-center justify-between">
          <Button type="button" variant="ghost" size="sm" onClick={() => navigate("/components")}>
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
          actionSlot={
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => setOpenModal("historial")}
            >
              <History className="size-4" />
              Historial de compras
            </Button>
          }
          rightSlot={
            <NatoScoringSection
              scoring={scoring}
              onOpenClasificarComponente={() => setOpenModal(scoring ? "scoring" : "clasificar")}
            />
          }
        />

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_1.6fr_1fr]">
          <DetailSection title="Precios de hoy">
            {pricesQuery.isLoading ? (
              <p className="text-sm text-text-secondary">Cargando precios…</p>
            ) : (
              <PreciosDeHoyTable
                prices={prices}
                suppliers={suppliers}
                preferredSupplierId={component.proveedor_preferente_id}
              />
            )}
          </DetailSection>

          <DetailSection title="Histórico de precios">
            {pricesQuery.isLoading ? (
              <p className="text-sm text-text-secondary">Cargando histórico…</p>
            ) : (
              <HistoricoPreciosChart prices={prices} suppliers={suppliers} />
            )}
          </DetailSection>

          <DetailSection title="Stock disponible en proveedores">
            {stocksQuery.isLoading ? (
              <p className="text-sm text-text-secondary">Cargando stock…</p>
            ) : (
              <StockDisponibleChart snapshots={stocks} suppliers={suppliers} />
            )}
          </DetailSection>
        </div>
      </div>

      <HistorialDeComprasModal
        open={openModal === "historial"}
        onOpenChange={(open) => !open && setOpenModal(null)}
        component={component}
        stockEvents={stockEvents}
        suppliers={suppliers}
        supplierPrices={prices}
        supplierStocks={stocks}
      />

      {scoring && (
        <NatoScoringModal
          open={openModal === "scoring"}
          onOpenChange={(open) => !open && setOpenModal(null)}
          component={component}
          scoring={scoring}
          onOpenClasificarComponente={() => setOpenModal("clasificar")}
        />
      )}

      <PlaceholderModal
        open={openModal === "clasificar"}
        onOpenChange={(open) => !open && setOpenModal(null)}
        title="Clasificar Componente"
        body={
          <>
            <p>
              Próxima iteración: formulario para crear nuevo scoring OTAN — score, tier,
              classifications (sub-partes) y alternatives (Figma 47:21897).
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

function DetailSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex h-[480px] flex-col rounded-lg border border-border bg-white p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-secondary">
        {title}
      </h3>
      <div className="flex-1 overflow-hidden">{children}</div>
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
