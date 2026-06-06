import type { ReactNode } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils/cn";

export interface TruncatedTextProps {
  /** The full text. Shown verbatim inside the tooltip. */
  text: string;
  /**
   * Extra classes for the visible truncated span. The component already
   * applies `block truncate` to drive the single-line ellipsis behaviour;
   * callers pass typography / colour utilities here.
   */
  className?: string;
  /**
   * Wrapper tag for the visible text. Defaults to `<span>` — pass `"p"` when
   * the host uses block-level paragraph styling.
   */
  as?: "span" | "p";
  /**
   * Disable the Radix Tooltip wrapper — useful when the host already nests
   * a popover/tooltip and we want to avoid stacked-trigger weirdness.
   */
  withTooltip?: boolean;
  /** Optional render-override for the visible text (e.g. add an icon).
   *  When omitted, the visible text is just the truncated `text`. */
  children?: ReactNode;
}

/**
 * Single-line truncated text with a tooltip exposing the full string on hover.
 *
 * Shared primitive used by every list / hierarchy table where a name (or any
 * dense label) might be clipped by the column width — keeps the UX consistent
 * across Projects · Modules · Components tables.
 *
 * Native `title` is set as a graceful fallback for environments that don't
 * render the Radix Tooltip (e.g. screen readers in some configurations,
 * automated tests).
 */
export function TruncatedText({
  text,
  className,
  as = "span",
  withTooltip = true,
  children,
}: TruncatedTextProps) {
  const Tag = as;
  const visible = (
    <Tag className={cn("block truncate", className)} title={text}>
      {children ?? text}
    </Tag>
  );
  if (!withTooltip) return visible;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{visible}</TooltipTrigger>
      <TooltipContent side="top" align="start" className="max-w-md break-words">
        {text}
      </TooltipContent>
    </Tooltip>
  );
}
