import { Check, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { formatEuros } from "@/lib/format/currency";
import { cn } from "@/lib/utils/cn";

import type { ComponentDetail, ComponentSummary, NatoScoring } from "../types";
import { NatoScoreBadge } from "@/features/shared/badges/NatoScoreBadge";
import { TierBadge } from "@/features/shared/badges/TierBadge";

interface NatoScoringModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  component: ComponentDetail;
  scoring: NatoScoring;
  onOpenClasificarComponente: () => void;
}

function formatDdMmYyyy(iso: string): string {
  const datePart = iso.split("T")[0] ?? iso;
  const [y = "????", m = "??", d = "??"] = datePart.split("-");
  return `${d}/${m}/${y}`;
}

const COUNTRY_LABELS: Record<string, { name: string; flag: string }> = {
  ES: { name: "España", flag: "🇪🇸" },
  FR: { name: "Francia", flag: "🇫🇷" },
  DE: { name: "Alemania", flag: "🇩🇪" },
  IT: { name: "Italia", flag: "🇮🇹" },
  PL: { name: "Polonia", flag: "🇵🇱" },
  NL: { name: "Países Bajos", flag: "🇳🇱" },
  BE: { name: "Bélgica", flag: "🇧🇪" },
  PT: { name: "Portugal", flag: "🇵🇹" },
  GB: { name: "Reino Unido", flag: "🇬🇧" },
  US: { name: "Estados Unidos", flag: "🇺🇸" },
  CA: { name: "Canadá", flag: "🇨🇦" },
  JP: { name: "Japón", flag: "🇯🇵" },
  KR: { name: "Corea del Sur", flag: "🇰🇷" },
  TW: { name: "Taiwán", flag: "🇹🇼" },
  CN: { name: "China", flag: "🇨🇳" },
  RU: { name: "Rusia", flag: "🇷🇺" },
};

function renderCountry(code: string | null): React.ReactNode {
  if (!code) return <span className="text-text-secondary">—</span>;
  const meta = COUNTRY_LABELS[code.toUpperCase()];
  if (!meta) return <span className="text-text-secondary">{code}</span>;
  return (
    <span className="inline-flex items-center gap-1.5">
      <span aria-hidden>{meta.flag}</span>
      <span>{meta.name}</span>
    </span>
  );
}

interface AvailabilityMeta {
  label: string;
  cls: string;
}

function availabilityFor(stock: number): AvailabilityMeta {
  if (stock <= 0) return { label: "Sin stock", cls: "bg-red-50 text-red-700 border-red-200" };
  if (stock < 20)
    return { label: "Stock limitado", cls: "bg-amber-50 text-amber-700 border-amber-200" };
  return { label: "En stock", cls: "bg-emerald-50 text-emerald-700 border-emerald-200" };
}

export function NatoScoringModal({
  open,
  onOpenChange,
  component,
  scoring,
  onOpenClasificarComponente,
}: NatoScoringModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-h-[90vh] w-[min(95vw,1400px)] max-w-none overflow-y-auto"
        onOpenAutoFocus={(event) => event.preventDefault()}
      >
        <DialogHeader>
          <div className="flex items-start gap-3">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-brand/10 text-brand">
              <ShieldCheck className="size-5" />
            </span>
            <div className="flex-1">
              <DialogTitle className="text-lg">Detalle Scoring OTAN</DialogTitle>
              <p className="text-xs text-text-secondary">
                <span className="font-mono">{component.mpn}</span>{" "}
                <span className="text-text-secondary">·</span> {component.name}
              </p>
            </div>
          </div>
        </DialogHeader>

        {/* Resumen — 4 columnas + acción */}
        <section className="rounded-lg border border-border bg-muted/30 p-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_1.1fr_1fr_auto] lg:items-center">
            <ResumenCell label="Score OTAN">
              <NatoScoreBadge
                value={scoring.nato_score}
                helpMode="full"
                natoExpiresAt={scoring.expires_at}
                className="text-sm"
              />
            </ResumenCell>
            <ResumenCell label="TIER">
              <TierBadge value={scoring.tier} helpMode="full" className="text-sm" />
            </ResumenCell>
            <ResumenCell label="Caducidad">
              <span className="text-sm font-medium text-text-primary">
                {formatDdMmYyyy(scoring.expires_at)}
              </span>
            </ResumenCell>
            <ResumenCell label="Estado">
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-semibold",
                  scoring.status === "active"
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border-border bg-muted text-text-secondary",
                )}
              >
                {scoring.status === "active" ? "Verificado" : "Archivado"}
              </span>
            </ResumenCell>
            <div className="flex justify-end">
              <Button
                type="button"
                size="sm"
                onClick={() => {
                  onOpenChange(false);
                  onOpenClasificarComponente();
                }}
              >
                <ShieldCheck className="size-4" />
                Clasificar Componente
              </Button>
            </div>
          </div>
        </section>

        {/* Detalle de Clasificación */}
        <section>
          <h3 className="mb-2 text-sm font-semibold text-text-primary">Detalle de Clasificación</h3>
          {scoring.classifications.length === 0 ? (
            <p className="rounded-md border border-dashed border-border p-4 text-sm text-text-secondary">
              Sin clasificaciones registradas para este scoring.
            </p>
          ) : (
            <div className="overflow-hidden rounded-lg border border-border">
              <table className="w-full table-fixed text-sm">
                <colgroup>
                  <col className="w-[26%]" />
                  <col className="w-[16%]" />
                  <col className="w-[14%]" />
                  <col className="w-[8%]" />
                  <col className="w-[12%]" />
                  <col className="w-[24%]" />
                </colgroup>
                <thead>
                  <tr className="bg-muted/40 text-xs uppercase tracking-wide text-text-secondary">
                    <Th>Componente</Th>
                    <Th>Fabricante</Th>
                    <Th>Origen</Th>
                    <Th>Score</Th>
                    <Th>Verificado</Th>
                    <Th>Notas</Th>
                  </tr>
                </thead>
                <tbody>
                  {scoring.classifications.map((c) => (
                    <tr key={c.id} className="border-t border-border align-top">
                      <Td className="font-medium text-text-primary">{c.part_label}</Td>
                      <Td>{c.fabricante ?? "—"}</Td>
                      <Td>{renderCountry(c.country_of_origin)}</Td>
                      <Td>
                        {c.nato_score ? (
                          <NatoScoreBadge
                            value={c.nato_score}
                            helpMode="tooltip"
                            showIcon={false}
                          />
                        ) : (
                          <span className="text-text-secondary">—</span>
                        )}
                      </Td>
                      <Td>
                        {c.verificado ? (
                          <span className="inline-flex items-center gap-1 text-emerald-700">
                            <Check className="size-3.5" />
                            {formatDdMmYyyy(scoring.classified_at)}
                          </span>
                        ) : (
                          <span className="text-text-secondary">Sin verificar</span>
                        )}
                      </Td>
                      <Td className="text-text-secondary">{c.notas ?? "—"}</Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Otras Opciones OTAN */}
        <section>
          <h3 className="mb-2 text-sm font-semibold text-text-primary">Otras Opciones OTAN</h3>
          {scoring.alternatives.length === 0 ? (
            <p className="rounded-md border border-dashed border-border p-4 text-sm text-text-secondary">
              Sin alternativas registradas para este scoring.
            </p>
          ) : (
            <div className="overflow-hidden rounded-lg border border-border">
              <table className="w-full table-fixed text-sm">
                <colgroup>
                  <col className="w-[28%]" />
                  <col className="w-[16%]" />
                  <col className="w-[14%]" />
                  <col className="w-[8%]" />
                  <col className="w-[8%]" />
                  <col className="w-[12%]" />
                  <col className="w-[14%]" />
                </colgroup>
                <thead>
                  <tr className="bg-muted/40 text-xs uppercase tracking-wide text-text-secondary">
                    <Th>Componente Alternativo</Th>
                    <Th>Fabricante</Th>
                    <Th>Origen</Th>
                    <Th>Score</Th>
                    <Th>TIER</Th>
                    <Th>Precio</Th>
                    <Th>Disponibilidad</Th>
                  </tr>
                </thead>
                <tbody>
                  {scoring.alternatives.map((alt) => (
                    <AlternativeRow key={alt.id} alt={alt.alternative_component} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </DialogContent>
    </Dialog>
  );
}

function ResumenCell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-wide text-text-secondary">{label}</span>
      <div>{children}</div>
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="px-3 py-2 text-left font-semibold">{children}</th>;
}

function Td({ children, className }: { children: React.ReactNode; className?: string }) {
  return <td className={cn("px-3 py-2 align-top", className)}>{children}</td>;
}

function AlternativeRow({ alt }: { alt: ComponentSummary | null }) {
  if (!alt) {
    return (
      <tr className="border-t border-border">
        <Td className="text-text-secondary">
          <em>Componente eliminado</em>
        </Td>
        <Td>—</Td>
        <Td>—</Td>
        <Td>—</Td>
        <Td>—</Td>
        <Td>—</Td>
        <Td>—</Td>
      </tr>
    );
  }
  const availability = availabilityFor(alt.stock);
  return (
    <tr className="border-t border-border align-top">
      <Td className="font-medium text-text-primary">
        <span className="font-mono text-xs text-text-secondary">{alt.mpn}</span>
        {" — "}
        {alt.name}
      </Td>
      <Td>{alt.fabricante ?? "—"}</Td>
      <Td>{renderCountry(alt.country_of_origin)}</Td>
      <Td>
        <NatoScoreBadge value={alt.nato_score} helpMode="tooltip" showIcon={false} />
      </Td>
      <Td>
        <TierBadge value={alt.tier} helpMode="tooltip" />
      </Td>
      <Td className="whitespace-nowrap font-medium text-text-primary">
        {formatEuros(alt.current_price_per_100_eur)}
      </Td>
      <Td>
        <span
          className={cn(
            "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold",
            availability.cls,
          )}
        >
          {availability.label}
        </span>
      </Td>
    </tr>
  );
}
