import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

import { NATO_SCORE_LABELS } from "../rubrics";
import type { NatoScoreValue } from "../types";

const NATO_CLASSES: Record<NatoScoreValue, string> = {
  "100_otan": "bg-emerald-500/15 text-emerald-700",
  otan: "bg-emerald-500/10 text-emerald-700",
  allied_otan: "bg-sky-500/15 text-sky-700",
  neutral: "bg-amber-500/15 text-amber-700",
  high_risk: "bg-orange-500/15 text-orange-700",
  no_otan: "bg-red-500/15 text-red-700",
};

export interface NatoScoreBadgeProps extends HTMLAttributes<HTMLSpanElement> {
  value: NatoScoreValue;
}

export function NatoScoreBadge({ value, className, ...props }: NatoScoreBadgeProps) {
  return (
    <span
      aria-label={`Scoring OTAN ${NATO_SCORE_LABELS[value]}`}
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
        NATO_CLASSES[value],
        className,
      )}
      {...props}
    >
      {NATO_SCORE_LABELS[value]}
    </span>
  );
}
