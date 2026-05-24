import { History, Info, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils/cn";

import type { NatoScoring } from "../types";
import { NatoScoreBadge } from "./NatoScoreBadge";
import { TierBadge } from "./TierBadge";

interface NatoScoringSectionProps {
  scoring: NatoScoring | null;
  onOpenHistorialDeCompras: () => void;
  onOpenClasificarComponente: () => void;
}

function formatDdMmYy(iso: string): string {
  const datePart = iso.split("T")[0] ?? iso;
  const [y = "????", m = "??", d = "??"] = datePart.split("-");
  return `${d}/${m}/${y.slice(2)}`;
}

function formatDdMmYyyyHm(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

export function NatoScoringSection({
  scoring,
  onOpenHistorialDeCompras,
  onOpenClasificarComponente,
}: NatoScoringSectionProps) {
  if (!scoring) {
    return (
      <section className="rounded-lg border border-border bg-white p-4">
        <header className="mb-3 flex items-center gap-2">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">
            Scoring OTAN
          </h3>
        </header>
        <p className="text-sm text-text-secondary">
          Este componente todavía no tiene una clasificación OTAN activa.
        </p>
        <div className="mt-3 flex justify-end">
          <Button type="button" size="sm" onClick={onOpenClasificarComponente}>
            <ShieldCheck className="size-4" />
            Clasificar Componente
          </Button>
        </div>
      </section>
    );
  }

  const expired = new Date(scoring.expires_at) < new Date();

  return (
    <section className="rounded-lg border border-border bg-white p-4">
      <header className="mb-3 flex items-center gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">
          Scoring OTAN
        </h3>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <NatoScoreBadge
          value={scoring.nato_score}
          helpMode="full"
          natoExpiresAt={scoring.expires_at}
        />
        <span className="text-text-secondary">|</span>
        <TierBadge value={scoring.tier} helpMode="full" />
        <span className="text-text-secondary">|</span>
        <span
          className={cn("text-sm", expired ? "font-medium text-red-600" : "text-text-secondary")}
        >
          Caduca: {formatDdMmYy(scoring.expires_at)}
        </span>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              aria-label="Detalle de auditoría del scoring"
              className="inline-flex size-5 items-center justify-center text-text-secondary hover:text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Info className="size-3.5" />
            </button>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs">
            <p className="font-semibold text-text-primary">Última clasificación</p>
            <p className="text-text-secondary">
              {scoring.classified_by_full_name ?? "Sin usuario asignado"}
              {" · "}
              {formatDdMmYyyyHm(scoring.created_at)}
            </p>
            {scoring.notes && (
              <p className="mt-1 text-text-secondary">&laquo;{scoring.notes}&raquo;</p>
            )}
          </TooltipContent>
        </Tooltip>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-end gap-2">
        <Button type="button" variant="outline" size="sm" onClick={onOpenHistorialDeCompras}>
          <History className="size-4" />
          Historial de compras
        </Button>
        <Button type="button" size="sm" onClick={onOpenClasificarComponente}>
          <ShieldCheck className="size-4" />
          Clasificar Componente
        </Button>
      </div>
    </section>
  );
}
