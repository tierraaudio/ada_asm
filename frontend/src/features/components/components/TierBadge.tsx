import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

import { TIER_LABELS } from "../rubrics";
import type { TierValue } from "../types";

const TIER_CLASSES: Record<TierValue, string> = {
  "A+": "bg-emerald-500/15 text-emerald-700",
  A: "bg-emerald-500/10 text-emerald-700",
  B: "bg-amber-500/15 text-amber-700",
  C: "bg-orange-500/15 text-orange-700",
  D: "bg-red-500/15 text-red-700",
};

export interface TierBadgeProps extends HTMLAttributes<HTMLSpanElement> {
  value: TierValue;
}

export function TierBadge({ value, className, ...props }: TierBadgeProps) {
  return (
    <span
      aria-label={`Tier ${TIER_LABELS[value]}`}
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
        TIER_CLASSES[value],
        className,
      )}
      {...props}
    >
      {TIER_LABELS[value]}
    </span>
  );
}
