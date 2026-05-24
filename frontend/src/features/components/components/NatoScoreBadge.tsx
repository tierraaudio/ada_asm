import { Shield } from "lucide-react";
import type { HTMLAttributes } from "react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils/cn";

import { NATO_HELP_INTRO, NATO_HELP_TITLE, NATO_SCORE_LABELS, NATO_SCORE_RUBRIC } from "../rubrics";
import { NATO_SCORE_VALUES } from "../types";
import type { NatoScoreValue } from "../types";

/**
 * Colour bands from the Figma list page (47:15264).
 */
const NATO_CLASSES: Record<NatoScoreValue, string> = {
  "A+": "bg-emerald-100 text-emerald-700 border-emerald-200",
  A: "bg-emerald-50 text-emerald-700 border-emerald-200",
  B: "bg-sky-50 text-sky-700 border-sky-200",
  C: "bg-amber-50 text-amber-700 border-amber-200",
  D: "bg-orange-50 text-orange-700 border-orange-200",
  F: "bg-red-50 text-red-700 border-red-200",
};

export type NatoScoreBadgeHelpMode = "tooltip" | "full";

export interface NatoScoreBadgeProps extends HTMLAttributes<HTMLSpanElement> {
  value: NatoScoreValue;
  showIcon?: boolean;
  /** Default true. Set false when nesting inside another popover/legend. */
  withTooltip?: boolean;
  /**
   * `tooltip` (default, used in lists) — single-line tooltip with the rubric.
   * `full` (used in detail screen) — click-popover with the full Niveles de
   * clasificación list + optional "Caduca el: …" footer.
   */
  helpMode?: NatoScoreBadgeHelpMode;
  /** ISO date string; rendered as the "Caduca el: DD/MM/YYYY" footer in `full` mode. */
  natoExpiresAt?: string | null;
}

function formatDdMmYyyy(iso: string): string {
  // Accepts "YYYY-MM-DD" or ISO timestamp.
  const datePart = iso.split("T")[0] ?? iso;
  const [y = "????", m = "??", d = "??"] = datePart.split("-");
  return `${d}/${m}/${y}`;
}

export function NatoScoreBadge({
  value,
  showIcon = true,
  withTooltip = true,
  helpMode = "tooltip",
  natoExpiresAt,
  className,
  ...props
}: NatoScoreBadgeProps) {
  const badge = (
    <span
      aria-label={`Scoring OTAN ${NATO_SCORE_LABELS[value]}`}
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-semibold",
        withTooltip && "cursor-help",
        NATO_CLASSES[value],
        className,
      )}
      // Passive info trigger — focus also opens the tooltip for keyboard users.
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
      tabIndex={withTooltip ? 0 : undefined}
      {...props}
    >
      {showIcon && <Shield className="size-3" aria-hidden />}
      {NATO_SCORE_LABELS[value]}
    </span>
  );

  if (!withTooltip) return badge;

  if (helpMode === "full") {
    return (
      <Popover>
        <PopoverTrigger asChild>{badge}</PopoverTrigger>
        <PopoverContent className="w-80 p-4 text-sm" align="start">
          <h3 className="mb-1 text-sm font-semibold text-text-primary">{NATO_HELP_TITLE}</h3>
          <p className="mb-3 text-xs text-text-secondary">{NATO_HELP_INTRO}</p>
          <p className="mb-2 text-xs font-semibold text-text-primary">Niveles de clasificación:</p>
          <ul className="space-y-2">
            {NATO_SCORE_VALUES.map((v) => (
              <li key={v} className="grid grid-cols-[3.5rem_1fr] items-start gap-2">
                <NatoScoreBadge value={v} showIcon={false} withTooltip={false} />
                <span className="text-xs text-text-secondary">{NATO_SCORE_RUBRIC[v]}</span>
              </li>
            ))}
          </ul>
          {natoExpiresAt && (
            <p className="mt-3 border-t border-border pt-2 text-xs text-text-secondary">
              <span className="font-medium text-text-primary">Caduca el: </span>
              {formatDdMmYyyy(natoExpiresAt)}
            </p>
          )}
        </PopoverContent>
      </Popover>
    );
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>{badge}</TooltipTrigger>
      <TooltipContent>{NATO_SCORE_RUBRIC[value]}</TooltipContent>
    </Tooltip>
  );
}
