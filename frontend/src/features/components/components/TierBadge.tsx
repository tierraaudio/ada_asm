import type { HTMLAttributes } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils/cn";

import { TIER_HELP_INTRO, TIER_HELP_TITLE, TIER_LABELS, TIER_RUBRIC } from "../rubrics";
import { TIER_VALUES } from "../types";
import type { TierValue } from "../types";

/**
 * Colour bands per the Figma:
 *   Tier 1 (most critical) → red
 *   Tier 2 → orange
 *   Tier 3 → amber
 *   Tier 4 → emerald
 */
const TIER_CLASSES: Record<TierValue, string> = {
  1: "bg-red-500/15 text-red-700 border-red-200",
  2: "bg-orange-500/15 text-orange-700 border-orange-200",
  3: "bg-amber-500/15 text-amber-700 border-amber-200",
  4: "bg-emerald-500/15 text-emerald-700 border-emerald-200",
};

export type TierBadgeHelpMode = "tooltip" | "full";

export interface TierBadgeProps extends HTMLAttributes<HTMLSpanElement> {
  value: TierValue;
  /** When true (default), wraps in a Tooltip/Popover showing the rubric on hover. */
  withTooltip?: boolean;
  /**
   * `tooltip` (default, used in lists) — single-line tooltip with category + riesgo.
   * `full` (used in detail screen) — click-popover with the full Niveles de TIER list.
   */
  helpMode?: TierBadgeHelpMode;
}

export function TierBadge({
  value,
  withTooltip = true,
  helpMode = "tooltip",
  className,
  ...props
}: TierBadgeProps) {
  const badge = (
    <span
      aria-label={`Tier ${value}`}
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold",
        withTooltip && "cursor-help",
        TIER_CLASSES[value],
        className,
      )}
      // Passive info trigger — focus also opens the tooltip for keyboard users.
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
      tabIndex={withTooltip ? 0 : undefined}
      {...props}
    >
      {TIER_LABELS[value]}
    </span>
  );

  if (!withTooltip) return badge;

  if (helpMode === "full") {
    return (
      <Tooltip>
        <TooltipTrigger asChild>{badge}</TooltipTrigger>
        <TooltipContent className="w-80 p-4 text-sm" align="start">
          <h3 className="mb-1 text-sm font-semibold text-text-primary">{TIER_HELP_TITLE}</h3>
          <p className="mb-3 text-xs text-text-secondary">{TIER_HELP_INTRO}</p>
          <p className="mb-2 text-xs font-semibold text-text-primary">Niveles de TIER:</p>
          <ul className="space-y-2">
            {TIER_VALUES.map((v) => (
              <li key={v} className="grid grid-cols-[4rem_1fr] items-start gap-3">
                <TierBadge value={v} withTooltip={false} />
                <span className="text-xs text-text-secondary">
                  <span className="block font-medium text-text-primary">
                    {TIER_RUBRIC[v].category}
                  </span>
                  Riesgo: {TIER_RUBRIC[v].risk}
                </span>
              </li>
            ))}
          </ul>
        </TooltipContent>
      </Tooltip>
    );
  }

  const rubric = TIER_RUBRIC[value];
  return (
    <Tooltip>
      <TooltipTrigger asChild>{badge}</TooltipTrigger>
      <TooltipContent>
        <p className="font-semibold text-text-primary">{rubric.category}</p>
        <p className="text-text-secondary">Riesgo: {rubric.risk}</p>
      </TooltipContent>
    </Tooltip>
  );
}
