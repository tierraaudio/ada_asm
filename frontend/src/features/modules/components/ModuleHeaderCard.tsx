import { Box, Calendar, MapPin, Package } from "lucide-react";
import type { ReactNode } from "react";

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
  /** Right-side block (Scoring OTAN card), pixel-aligned with the grid. */
  rightSlot?: ReactNode;
  /** Rendered inline inside the Stock cell, just before "X unidades". */
  stockActionSlot?: ReactNode;
}

/**
 * Pixel-faithful header card for the module detail page. Mirrors
 * `ComponentHeaderCard` so the catalogue feels consistent end-to-end:
 *
 * - Top: SKU breadcrumb + title (with version pill) + description.
 * - Below: 2-column horizontal split (lg+):
 *   - Left (1fr): 4-column property grid with 3 rows.
 *   - Right (auto, ~360 px): the Scoring OTAN block (rightSlot).
 *
 * `stockActionSlot` mirrors components — used to drop an icon-button
 * (e.g. price-history) next to the Stock value.
 */
export function ModuleHeaderCard({ module, rightSlot, stockActionSlot }: ModuleHeaderCardProps) {
  return (
    <section className="rounded-lg border border-border bg-white p-6 shadow-sm">
      <div className="mb-6 flex items-start gap-3">
        <span className="mt-1 inline-flex size-10 shrink-0 items-center justify-center rounded-md bg-muted text-text-secondary">
          <Box className="size-5" />
        </span>
        <div>
          <p className="text-xs uppercase tracking-wide text-text-secondary">
            <span className="font-mono">{module.sku}</span>
          </p>
          <h1 className="mt-1 flex flex-wrap items-center gap-2 text-2xl font-semibold text-text-primary">
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

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_auto]">
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
          <Field
            icon={<Package className="size-3.5" />}
            label="SKU"
            value={<span className="font-mono text-xs">{module.sku}</span>}
          />
          <Field label="Versión" value={module.version} />

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
          <Field label="Fabricante" value={module.fabricante ?? "—"} />
          <Field
            label="Stock"
            value={
              <span className="inline-flex items-center gap-2">
                {stockActionSlot}
                <BuildableTooltip stock={module.stock} buildable={module.buildable_stock} />
              </span>
            }
          />

          <Field label="Precio total" value={<PriceTotalTooltip module={module} />} />
          <div aria-hidden />
          <div aria-hidden />
          <div aria-hidden />
        </dl>

        {rightSlot && <div className="w-full lg:w-[360px]">{rightSlot}</div>}
      </div>
    </section>
  );
}
