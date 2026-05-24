import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

import { TIER_LABELS } from "../rubrics";
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
}

export function TierBadge({ value, className, ...props }: TierBadgeProps) {
  return (
    <span
      aria-label={`Tier ${value}`}
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold",
        TIER_CLASSES[value],
        className,
      )}
      {...props}
    >
      {TIER_LABELS[value]}
    </span>
  );
}
