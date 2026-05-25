import type { HTMLAttributes } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils/cn";

export interface FamilyChipProps extends HTMLAttributes<HTMLSpanElement> {
  /** The family label (e.g. "Board" / "Microcontroladores"). */
  value: string;
  /** Tooltip body shown on hover/focus — short description of what the family means. */
  description: string;
}

/**
 * Generic enum chip used in tables and detail pages. Same visual treatment
 * everywhere a high-level taxonomy value is rendered — modules' family
 * (Board/Device/Bundle/Case) and components' family (Microcontroladores /
 * Sensores / …) both compose this primitive.
 */
export function FamilyChip({ value, description, className, ...rest }: FamilyChipProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          aria-label={`Familia: ${value}`}
          // Passive info trigger — focus opens the tooltip too for keyboard users.
          // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
          tabIndex={0}
          className={cn(
            "inline-flex cursor-help items-center whitespace-nowrap rounded-md",
            "border border-border bg-muted/50 px-2 py-0.5 text-xs font-medium text-text-primary",
            "outline-none focus-visible:ring-2 focus-visible:ring-ring",
            className,
          )}
          {...rest}
        >
          {value}
        </span>
      </TooltipTrigger>
      <TooltipContent side="bottom" sideOffset={6} className="max-w-xs">
        <p className="font-semibold text-text-primary">{value}</p>
        <p className="mt-0.5 text-text-secondary">{description}</p>
      </TooltipContent>
    </Tooltip>
  );
}
