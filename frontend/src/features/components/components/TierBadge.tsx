import type { HTMLAttributes } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils/cn";

import { TIER_LABELS, TIER_RUBRIC } from "../rubrics";
import type { TierValue } from "../types";

/**
 * Colour bands per the Figma:
 *   Tier 1 (most critical) → red
 *   Tier 2 → orange
 *   Tier 3 → amber
 *   Tier 4 → emerald
 * Soft 15 % alpha background + saturated foreground text, matching the NATO
 * badge convention so the two badges sit visually balanced in the table.
 */
const TIER_CLASSES: Record<TierValue, string> = {
  1: "bg-red-500/15 text-red-700 border-red-200",
  2: "bg-orange-500/15 text-orange-700 border-orange-200",
  3: "bg-amber-500/15 text-amber-700 border-amber-200",
  4: "bg-emerald-500/15 text-emerald-700 border-emerald-200",
};

export interface TierBadgeProps extends HTMLAttributes<HTMLSpanElement> {
  value: TierValue;
  /** When true (default), wraps in a Tooltip showing the rubric on hover. */
  withTooltip?: boolean;
}

export function TierBadge({ value, withTooltip = true, className, ...props }: TierBadgeProps) {
  const badge = (
    <span
      aria-label={`Tier ${value}`}
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold",
        withTooltip && "cursor-help",
        TIER_CLASSES[value],
        className,
      )}
      // tabIndex makes the badge focusable so keyboard users also get the
      // tooltip (Radix opens it on focus). The badge itself isn't interactive
      // — it's a passive info trigger — so the a11y rule is intentional here.
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
      tabIndex={withTooltip ? 0 : undefined}
      {...props}
    >
      {TIER_LABELS[value]}
    </span>
  );

  if (!withTooltip) return badge;

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
