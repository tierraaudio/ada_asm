import { ExternalLink } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils/cn";

import type { ComponentDetail, Supplier } from "../types";

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs uppercase tracking-wide text-text-secondary">{label}</dt>
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
  rightSlot?: ReactNode;
}

export function ComponentHeaderCard({
  component,
  suppliers,
  rightSlot,
}: ComponentHeaderCardProps) {
  const preferred = suppliers.find((s) => s.id === component.proveedor_preferente_id);
  return (
    <section className="rounded-lg border border-border bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <p className="text-xs uppercase tracking-wide text-text-secondary">
            {component.sku ? `${component.sku} • ` : ""}
            <span className="font-mono">{component.mpn}</span>
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-text-primary">
            {component.name}
          </h1>
          {component.description && (
            <p className="mt-1 text-sm text-text-secondary">{component.description}</p>
          )}
        </div>
        {rightSlot && <div className="shrink-0">{rightSlot}</div>}
      </div>

      <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-4 md:grid-cols-3 lg:grid-cols-4">
        <Field
          label="Fecha de creación"
          value={component.fecha_creacion ? formatDdMmYyyy(component.fecha_creacion) : "—"}
        />
        <Field label="Última modificación" value={formatDdMmYyyy(component.updated_at)} />
        <Field label="SKU" value={component.sku ?? "—"} />
        <Field
          label="MPN"
          value={<span className="font-mono text-xs">{component.mpn}</span>}
        />
        <Field label="Ubicación" value={component.location ?? "—"} />
        <Field
          label="Tipo almacenamiento"
          value={component.tipo_almacenamiento ?? "—"}
        />
        <Field label="Familia" value={component.family} />
        <Field
          label="Proveedor preferente"
          value={
            preferred ? (
              <span
                className={cn(
                  "inline-flex items-center rounded-md border border-brand/30 bg-brand/10 px-2 py-0.5 text-xs font-semibold text-brand",
                )}
              >
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
        <Field
          label="Datasheet"
          value={
            component.datasheet_url ? (
              <a
                href={component.datasheet_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-brand hover:underline"
              >
                Abrir <ExternalLink className="size-3" />
              </a>
            ) : (
              "—"
            )
          }
        />
      </dl>
    </section>
  );
}
