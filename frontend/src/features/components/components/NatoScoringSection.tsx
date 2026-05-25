import { ShieldCheck } from "lucide-react";

import { NatoScoringSummaryCard } from "@/features/shared/badges/NatoScoringSummaryCard";

import type { NatoScoring } from "../types";

interface NatoScoringSectionProps {
  scoring: NatoScoring | null;
  /**
   * Triggered by the primary action: opens the Detalle Scoring OTAN modal when
   * an active scoring exists, or the Clasificar Componente form when not.
   * The caller decides which modal to render based on `scoring`.
   */
  onOpenClasificarComponente: () => void;
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
  onOpenClasificarComponente,
}: NatoScoringSectionProps) {
  if (!scoring) {
    return (
      <NatoScoringSummaryCard
        score={null}
        tier={null}
        emptyState={{
          message: "Este componente todavía no tiene una clasificación OTAN activa.",
          actionLabel: "Clasificar Componente",
          onAction: onOpenClasificarComponente,
          actionIcon: <ShieldCheck className="size-4" />,
        }}
      />
    );
  }

  return (
    <NatoScoringSummaryCard
      score={scoring.nato_score}
      tier={scoring.tier}
      expiresAt={scoring.expires_at}
      onViewDetail={onOpenClasificarComponente}
      auditTooltipTitle="Última clasificación"
      auditTooltipBody={
        <>
          <p>
            {scoring.classified_by_full_name ?? "Sin usuario asignado"}
            {" · "}
            {formatDdMmYyyyHm(scoring.created_at)}
          </p>
          {scoring.notes && <p className="mt-1">&laquo;{scoring.notes}&raquo;</p>}
        </>
      }
    />
  );
}
