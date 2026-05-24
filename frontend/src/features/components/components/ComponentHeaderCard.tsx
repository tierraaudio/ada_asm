import { Calendar, ExternalLink, MapPin, Package, Paperclip } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils/cn";

import type { ComponentDetail, Supplier } from "../types";

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

function formatDdMmYyyy(iso: string): string {
  const datePart = iso.split("T")[0] ?? iso;
  const [y = "????", m = "??", d = "??"] = datePart.split("-");
  return `${d}/${m}/${y}`;
}

interface ComponentHeaderCardProps {
  component: ComponentDetail;
  suppliers: Supplier[];
  /** Right-side block (Scoring OTAN section), pixel-aligned with the grid. */
  rightSlot?: ReactNode;
  /** Rendered in the row-3, col-4 cell (just below "Proveedor preferente"). */
  actionSlot?: ReactNode;
}

/**
 * Pixel-faithful header card for the component detail page (Figma 47:16048).
 *
 * Layout:
 *  - Top: SKU•MPN breadcrumb, title (big), description (subtle).
 *  - Below: 2-column horizontal split (lg+):
 *    - Left (1fr): 4-column property grid with 3 rows + a full-width Datasheet
 *      row. Only the labels that carry an icon in the design get one
 *      (Calendar / Package / MapPin / Paperclip).
 *    - Right (auto, ~360 px): the Scoring OTAN block (rightSlot).
 */
export function ComponentHeaderCard({
  component,
  suppliers,
  rightSlot,
  actionSlot,
}: ComponentHeaderCardProps) {
  const preferred = suppliers.find((s) => s.id === component.proveedor_preferente_id);
  return (
    <section className="rounded-lg border border-border bg-white p-6 shadow-sm">
      <div className="mb-6">
        <p className="text-xs uppercase tracking-wide text-text-secondary">
          {component.sku ? `${component.sku} • ` : ""}
          <span className="font-mono">{component.mpn}</span>
        </p>
        <h1 className="mt-1 text-2xl font-semibold text-text-primary">{component.name}</h1>
        {component.description && (
          <p className="mt-1 text-sm text-text-secondary">{component.description}</p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_auto]">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-4 md:grid-cols-4">
          <Field
            icon={<Calendar className="size-3.5" />}
            label="Fecha de creación"
            value={component.fecha_creacion ? formatDdMmYyyy(component.fecha_creacion) : "—"}
          />
          <Field
            icon={<Calendar className="size-3.5" />}
            label="Última modificación"
            value={formatDdMmYyyy(component.updated_at)}
          />
          <Field icon={<Package className="size-3.5" />} label="SKU" value={component.sku ?? "—"} />
          <Field
            icon={<Package className="size-3.5" />}
            label="MPN"
            value={<span className="font-mono text-xs">{component.mpn}</span>}
          />

          <Field
            icon={<MapPin className="size-3.5" />}
            label="Ubicación"
            value={component.location ?? "—"}
          />
          <Field
            icon={<Package className="size-3.5" />}
            label="Tipo almacenamiento"
            value={component.tipo_almacenamiento ?? "—"}
          />
          <Field icon={<Package className="size-3.5" />} label="Familia" value={component.family} />
          <Field
            label="Proveedor preferente"
            value={
              preferred ? (
                <span className="inline-flex items-center rounded-md border border-brand/30 bg-brand/10 px-2 py-0.5 text-xs font-semibold text-brand">
                  {preferred.name}
                </span>
              ) : (
                "—"
              )
            }
          />

          <Field label="Fabricante" value={component.fabricante ?? "—"} />
          <Field
            label="Stock"
            value={
              <span>
                {component.stock} <span className="text-text-secondary">unidades</span>
              </span>
            }
          />
          <Field label="Holded ID" value={component.holded_id ?? "—"} />
          <div className="flex items-end">{actionSlot}</div>

          <Field
            icon={<Paperclip className="size-3.5" />}
            label="Datasheet"
            value={
              component.datasheet_url ? (
                <a
                  href={component.datasheet_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 break-all text-brand hover:underline"
                >
                  {component.datasheet_url}
                  <ExternalLink className="size-3 shrink-0" />
                </a>
              ) : (
                "—"
              )
            }
            className="md:col-span-4"
          />
        </dl>

        {rightSlot && <div className="w-full lg:w-[360px]">{rightSlot}</div>}
      </div>
    </section>
  );
}
