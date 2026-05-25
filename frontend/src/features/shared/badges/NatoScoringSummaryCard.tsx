import { Eye, Info } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils/cn";

import type { NatoScoreValue, TierValue } from "../enums";
import { NatoScoreBadge } from "./NatoScoreBadge";
import { TierBadge } from "./TierBadge";

interface EmptyState {
  message: string;
  actionLabel: string;
  onAction: () => void;
  actionIcon?: ReactNode;
}

export interface NatoScoringSummaryCardProps {
  /** Aggregated or own scoring. `null` triggers the empty state. */
  score: NatoScoreValue | null;
  tier: TierValue | null;
  /** ISO date — shown as "Caduca: DD/MM/YY". `null` hides the line. */
  expiresAt?: string | null | undefined;
  /** Optional "Ver detalle" callback. When omitted, the button is hidden. */
  onViewDetail?: (() => void) | undefined;
  /** Optional audit info tooltip (e.g. "Última clasificación" or "Peor score viene de X"). */
  auditTooltipTitle?: string | undefined;
  auditTooltipBody?: ReactNode | undefined;
  /** Rendered when `score` is null (e.g. component without scoring). */
  emptyState?: EmptyState | undefined;
}

function formatDdMmYy(iso: string): string {
  const datePart = iso.split("T")[0] ?? iso;
  const [y = "????", m = "??", d = "??"] = datePart.split("-");
  return `${d}/${m}/${y.slice(2)}`;
}

/**
 * Reusable Scoring OTAN side card. Lives next to the asset header on both
 * `ComponentDetailPage` and `ModuleDetailPage` so the visual language stays
 * identical across the catalogue.
 *
 * Composes `NatoScoreBadge` + `TierBadge` (both in `helpMode="full"`) with
 * the standard "Caduca: DD/MM/YY" line and an optional audit tooltip.
 */
export function NatoScoringSummaryCard({
  score,
  tier,
  expiresAt,
  onViewDetail,
  auditTooltipTitle,
  auditTooltipBody,
  emptyState,
}: NatoScoringSummaryCardProps) {
  if (score == null || tier == null) {
    return (
      <section className="rounded-lg border border-border bg-white p-4">
        <header className="mb-3 flex items-center gap-2">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">
            Scoring OTAN
          </h3>
        </header>
        <p className="text-sm text-text-secondary">
          {emptyState?.message ?? "Sin clasificación OTAN activa."}
        </p>
        {emptyState && (
          <div className="mt-3 flex justify-end">
            <Button type="button" size="sm" onClick={emptyState.onAction}>
              {emptyState.actionIcon}
              {emptyState.actionLabel}
            </Button>
          </div>
        )}
      </section>
    );
  }

  const expired = expiresAt ? new Date(expiresAt) < new Date() : false;

  return (
    <section className="rounded-lg border border-border bg-white p-4">
      <header className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">
          Scoring OTAN
        </h3>
        {onViewDetail && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={onViewDetail}
          >
            <Eye className="size-3.5" />
            Ver detalle
          </Button>
        )}
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <NatoScoreBadge value={score} helpMode="full" natoExpiresAt={expiresAt ?? null} />
        <span className="text-text-secondary">|</span>
        <TierBadge value={tier} helpMode="full" />
        {expiresAt && (
          <>
            <span className="text-text-secondary">|</span>
            <span
              className={cn(
                "text-sm",
                expired ? "font-medium text-red-600" : "text-text-secondary",
              )}
            >
              Caduca: {formatDdMmYy(expiresAt)}
            </span>
          </>
        )}
        {auditTooltipTitle && auditTooltipBody && (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                aria-label={auditTooltipTitle}
                className="inline-flex size-5 items-center justify-center text-text-secondary hover:text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Info className="size-3.5" />
              </button>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs">
              <p className="font-semibold text-text-primary">{auditTooltipTitle}</p>
              <div className="text-text-secondary">{auditTooltipBody}</div>
            </TooltipContent>
          </Tooltip>
        )}
      </div>
    </section>
  );
}
