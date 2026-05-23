import { ExternalLink } from "lucide-react";

import { formatEuros } from "@/lib/format/currency";

import type { Component } from "../types";
import { NatoScoreBadge } from "./NatoScoreBadge";
import { TierBadge } from "./TierBadge";

interface FieldProps {
  label: string;
  value: React.ReactNode;
}

function Field({ label, value }: FieldProps) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs uppercase tracking-wide text-text-secondary">{label}</dt>
      <dd className="text-sm font-medium text-text-primary">{value ?? "—"}</dd>
    </div>
  );
}

export function ComponentHeaderCard({ component }: { component: Component }) {
  return (
    <section className="rounded-lg border border-border bg-white p-6 shadow-sm">
      <div className="flex flex-col gap-1">
        <span className="text-xs font-semibold uppercase tracking-wide text-text-secondary">
          MPN
        </span>
        <h1 className="text-2xl font-semibold text-text-primary">{component.mpn}</h1>
        <p className="text-base text-text-secondary">{component.name}</p>
      </div>
      <dl className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        <Field label="SKU" value={component.sku} />
        <Field label="Familia" value={component.family} />
        <Field label="Ubicación" value={component.location} />
        <Field label="Supplier" value={component.supplier} />
        <Field label="Precio (100u)" value={formatEuros(component.price_per_100)} />
        <Field label="Stock" value={`${component.stock} u`} />
        <Field label="Tier" value={<TierBadge value={component.tier} />} />
        <Field label="Scoring OTAN" value={<NatoScoreBadge value={component.nato_score} />} />
        <Field
          label="País de origen"
          value={component.country_of_origin ?? "—"}
        />
        {component.datasheet_url && (
          <Field
            label="Datasheet"
            value={
              <a
                href={component.datasheet_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-brand hover:underline"
              >
                Abrir <ExternalLink className="size-3" />
              </a>
            }
          />
        )}
      </dl>
    </section>
  );
}
