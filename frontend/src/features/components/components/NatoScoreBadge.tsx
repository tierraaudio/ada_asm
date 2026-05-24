import { Shield } from "lucide-react";
import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

import { NATO_SCORE_LABELS } from "../rubrics";
import type { NatoScoreValue } from "../types";

/**
 * Colour bands from the Figma list page (47:15264):
 *   A+ → emerald (verified)
 *   A → emerald (OTAN)
 *   B → sky (allied)
 *   C → amber (neutral)
 *   D → orange (high risk)
 *   F → red (non-OTAN)
 */
const NATO_CLASSES: Record<NatoScoreValue, string> = {
  "A+": "bg-emerald-100 text-emerald-700 border-emerald-200",
  A: "bg-emerald-50 text-emerald-700 border-emerald-200",
  B: "bg-sky-50 text-sky-700 border-sky-200",
  C: "bg-amber-50 text-amber-700 border-amber-200",
  D: "bg-orange-50 text-orange-700 border-orange-200",
  F: "bg-red-50 text-red-700 border-red-200",
};

export interface NatoScoreBadgeProps extends HTMLAttributes<HTMLSpanElement> {
  value: NatoScoreValue;
  showIcon?: boolean;
}

export function NatoScoreBadge({
  value,
  showIcon = true,
  className,
  ...props
}: NatoScoreBadgeProps) {
  return (
    <span
      aria-label={`Scoring OTAN ${NATO_SCORE_LABELS[value]}`}
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-semibold",
        NATO_CLASSES[value],
        className,
      )}
      {...props}
    >
      {showIcon && <Shield className="size-3" aria-hidden />}
      {NATO_SCORE_LABELS[value]}
    </span>
  );
}
