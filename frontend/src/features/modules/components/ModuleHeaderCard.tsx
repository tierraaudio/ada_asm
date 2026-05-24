import { Box, Calendar, LineChart, MapPin, Package } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { NatoScoreBadge } from "@/features/shared/badges/NatoScoreBadge";
import { TierBadge } from "@/features/shared/badges/TierBadge";
import { cn } from "@/lib/utils/cn";

import type { Module } from "../types";
import { BuildableTooltip, PriceTotalTooltip } from "./AggregateTooltips";

interface FieldProps {
  icon?: ReactNode;
  label: string;
  value: ReactNode;
  className?: string;
}

function Field({ icon, label, value, className }: FieldProps) {
  return (
    <div className={cn("flex flex-col gap-0.5", className)}>
      <dt className="flex items-center gap-1.5 text-xs uppercase tracking-wide text-text-secondary">
        {icon && <span className="text-text-secondary/70">{icon}</span>}
        {label}
      </dt>
      <dd className="text-sm font-medium text-text-primary">{value ?? "—"}</dd>
    </div>
  );
}

function formatDdMmYyyy(iso: string | null | undefined): string {
  if (!iso) return "—";
  const datePart = iso.split("T")[0] ?? iso;
  const [y = "????", m = "??", d = "??"] = datePart.split("-");
  return `${d}/${m}/${y}`;
}

interface ModuleHeaderCardProps {
  module: Module;
  onOpenPriceHistory: () => void;
}

export function ModuleHeaderCard({ module, onOpenPriceHistory }: ModuleHeaderCardProps) {
  return (
    <section className="rounded-lg border border-border bg-white p-6 shadow-sm">
      <div className="mb-6 flex items-start gap-3">
        <span className="mt-1 inline-flex size-10 items-center justify-center rounded-md bg-brand/10 text-brand">
          <Box className="size-5" />
        </span>
        <div>
          <p className="text-xs uppercase tracking-wide text-text-secondary">
            <span className="font-mono">{module.sku}</span>
          </p>
          <h1 className="mt-1 flex items-center gap-2 text-2xl font-semibold text-text-primary">
            {module.name}
            <span className="rounded-md bg-brand/10 px-2 py-0.5 text-xs font-semibold text-brand">
              {module.version}
            </span>
          </h1>
          {module.description && (
            <p className="mt-1 text-sm text-text-secondary">{module.description}</p>
          )}
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-x-6 gap-y-4 md:grid-cols-4">
        <Field
          icon={<Calendar className="size-3.5" />}
          label="Fecha de creación"
          value={formatDdMmYyyy(module.fecha_creacion)}
        />
        <Field
          icon={<Calendar className="size-3.5" />}
          label="Última modificación"
          value={formatDdMmYyyy(module.updated_at)}
        />
        <Field label="Versión" value={module.version} />
        <Field
          icon={<Package className="size-3.5" />}
          label="SKU"
          value={<span className="font-mono text-xs">{module.sku}</span>}
        />

        <Field label="Fabricante" value={module.fabricante ?? "—"} />
        <Field
          icon={<MapPin className="size-3.5" />}
          label="Ubicación"
          value={module.location ?? "—"}
        />
        <Field
          icon={<Package className="size-3.5" />}
          label="Tipo almacenamiento"
          value={module.tipo_almacenamiento ?? "—"}
        />
        <div className="flex items-end">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onOpenPriceHistory}
            className="w-full"
          >
            <LineChart className="size-4" />
            Ver histórico de precios
          </Button>
        </div>

        <Field
          label="Stock"
          value={<BuildableTooltip stock={module.stock} buildable={module.buildable_stock} />}
        />
        <Field label="Precio total" value={<PriceTotalTooltip module={module} />} />
        <Field
          label="NATO Scoring"
          className="md:col-span-2"
          value={
            module.aggregated_nato_score && module.aggregated_tier ? (
              <div className="flex flex-wrap items-center gap-2">
                <NatoScoreBadge
                  value={module.aggregated_nato_score}
                  helpMode="full"
                  natoExpiresAt={module.aggregated_expires_at}
                />
                <TierBadge value={module.aggregated_tier} helpMode="full" />
                {module.aggregated_expires_at && (
                  <span className="text-sm text-text-secondary">
                    Caduca: {formatDdMmYyyy(module.aggregated_expires_at)}
                  </span>
                )}
              </div>
            ) : (
              <span className="text-text-secondary">Sin componentes con scoring activo.</span>
            )
          }
        />
      </dl>
    </section>
  );
}
