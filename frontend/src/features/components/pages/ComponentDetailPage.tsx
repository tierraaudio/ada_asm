import { Edit3, History, Trash2, X } from "lucide-react";
import { useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

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
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

import { ComponentHeaderCard } from "../components/ComponentHeaderCard";
import { ConfirmDeleteDialog } from "../components/ConfirmDeleteDialog";
import { HistorialDeComprasModal } from "../components/HistorialDeComprasModal";
import { HistoricoPreciosChart } from "@/features/shared/charts/HistoricoPreciosChart";
import { NatoScoringModal } from "../components/NatoScoringModal";
import { NatoScoringSection } from "../components/NatoScoringSection";
import { PreciosDeHoyTable } from "../components/PreciosDeHoyTable";
import { StockDisponibleChart } from "../components/StockDisponibleChart";
import { useComponentDetail } from "../hooks/use-component-detail";
import { useDeleteComponent } from "../hooks/use-component-mutations";
import { useComponentParents } from "../hooks/use-component-parents";
import { useStockEvents, useSupplierPrices, useSupplierStocks } from "../hooks/use-supplier-data";
import { useSuppliers } from "../hooks/use-suppliers";
import { ModulesHierarchyTable } from "@/features/modules/components/ModulesHierarchyTable";
import { useComponentProjectsUsing } from "@/features/projects/hooks/use-projects-using";
import { ProjectsHierarchyRow } from "@/features/shared/badges/ProjectsHierarchyRow";
import { useDetailNavPush } from "@/features/shared/nav/DetailNavControls";
import { useDetailNavStack } from "@/features/shared/nav/DetailNavStack";
import { DetailPageHeader } from "@/features/shared/nav/DetailPageHeader";

type ModalKey = "historial" | "scoring" | "clasificar" | null;

export function ComponentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const detailQuery = useComponentDetail(id);
  const deleteMutation = useDeleteComponent();
  const { reset: resetNavStack } = useDetailNavStack();
  const suppliersQuery = useSuppliers();
  const pricesQuery = useSupplierPrices(id);
  const stocksQuery = useSupplierStocks(id);
  const stockEventsQuery = useStockEvents(id);
  const parentsQuery = useComponentParents(id);
  const projectsUsingQuery = useComponentProjectsUsing(id);
  const [openModal, setOpenModal] = useState<ModalKey>(null);
  // Set when the user landed here from an ingest attempt whose MPN already
  // existed — we redirect to the existing component and explain why.
  const ingestExistingMpn =
    (location.state as { ingestExistingMpn?: string } | null)?.ingestExistingMpn ?? null;
  const [showExistingBanner, setShowExistingBanner] = useState(Boolean(ingestExistingMpn));
  useDetailNavPush();

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
        <DetailPageHeader
          closeTo="/components"
          rightSlot={
            <>
              <ConfirmDeleteDialog
                trigger={
                  <Button type="button" variant="outline" size="sm">
                    <Trash2 className="size-4 text-red-600" />
                    Eliminar
                  </Button>
                }
                title={`¿Eliminar el componente «${component.name}»?`}
                description="Esta acción no se puede deshacer. El componente desaparece del catálogo y se borran sus relaciones con módulos y proyectos."
                confirmLabel="Eliminar"
                onConfirm={async () => {
                  await deleteMutation.mutateAsync(component.id);
                  resetNavStack();
                  navigate("/components");
                }}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => navigate(`/components/${component.id}/edit`)}
              >
                <Edit3 className="size-4" />
                Editar Componente
              </Button>
            </>
          }
        />

        {showExistingBanner && ingestExistingMpn && (
          <div className="flex items-center justify-between gap-3 rounded-md border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">
            <span>
              Este componente ya existe (MPN{" "}
              <span className="font-semibold">{ingestExistingMpn}</span>).
            </span>
            <button
              type="button"
              onClick={() => setShowExistingBanner(false)}
              aria-label="Cerrar aviso"
              className="text-sky-600 transition-colors hover:text-sky-800"
            >
              <X className="size-4" />
            </button>
          </div>
        )}

        <ComponentHeaderCard
          component={component}
          suppliers={suppliers}
          stockActionSlot={
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  aria-label="Historial de compras"
                  onClick={() => setOpenModal("historial")}
                  className="inline-flex size-6 items-center justify-center rounded-md border border-border bg-white text-text-secondary transition-colors hover:border-brand/40 hover:text-brand focus:outline-none focus-visible:ring-2 focus-visible:ring-brand"
                >
                  <History className="size-3.5" />
                </button>
              </TooltipTrigger>
              <TooltipContent>Historial de compras</TooltipContent>
            </Tooltip>
          }
          rightSlot={
            <NatoScoringSection
              scoring={scoring}
              onOpenClasificarComponente={() => setOpenModal(scoring ? "scoring" : "clasificar")}
            />
          }
        />

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_1.3fr_1.3fr]">
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

        <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-secondary">
            Pertenece a
          </h2>
          <ModulesHierarchyTable
            rows={parentsQuery.data ?? []}
            expandable
            emptyMessage={
              parentsQuery.isLoading
                ? "Cargando módulos…"
                : "Este componente no pertenece a ningún módulo."
            }
          />
        </section>

        <section className="rounded-lg border border-border bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-secondary">
            Usado en proyectos
          </h2>
          {projectsUsingQuery.isLoading ? (
            <p className="px-3 py-2 text-sm text-text-secondary">Cargando proyectos…</p>
          ) : projectsUsingQuery.data && projectsUsingQuery.data.length > 0 ? (
            <div>
              {projectsUsingQuery.data.map((p) => (
                <ProjectsHierarchyRow key={p.id} project={p} />
              ))}
            </div>
          ) : (
            <p className="px-3 py-2 text-sm text-text-secondary">
              Este componente no se usa todavía en ningún proyecto.
            </p>
          )}
        </section>
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
