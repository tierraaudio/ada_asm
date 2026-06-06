import type { HTMLAttributes } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils/cn";

import { PROJECT_STATUS_DESCRIPTIONS, type ProjectStatus } from "../types";

export interface ProjectStatusBadgeProps extends HTMLAttributes<HTMLSpanElement> {
  value: ProjectStatus;
  /** When false, no tooltip wrapping is used (avoids nesting inside popovers). */
  withTooltip?: boolean;
}

const STATUS_CLASS: Record<ProjectStatus, string> = {
  // Figma mapping: Presupuestado = lavender, Esperando = ámbar,
  // En proceso = azul, Completado = verde, Archivado = gris.
  Presupuestado: "bg-violet-50 text-violet-700 border-violet-200",
  Esperando: "bg-amber-50 text-amber-700 border-amber-200",
  "En proceso": "bg-sky-50 text-sky-700 border-sky-200",
  Completado: "bg-emerald-50 text-emerald-700 border-emerald-200",
  Archivado: "bg-zinc-100 text-zinc-500 border-zinc-200",
};

/**
 * Status pill — same visual language as FamilyChip/NatoScoreBadge. Hover/focus
 * surfaces a tooltip with the full lifecycle description so reviewers don't
 * have to memorize the enum.
 */
export function ProjectStatusBadge({
  value,
  withTooltip = true,
  className,
  ...rest
}: ProjectStatusBadgeProps) {
  const chip = (
    <span
      // Passive info trigger — focus opens the tooltip for keyboard users.
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
      tabIndex={withTooltip ? 0 : undefined}
      aria-label={`Estado: ${value}`}
      className={cn(
        "inline-flex cursor-help items-center whitespace-nowrap rounded-md border",
        "px-2 py-0.5 text-xs font-medium",
        "outline-none focus-visible:ring-2 focus-visible:ring-ring",
        STATUS_CLASS[value],
        className,
      )}
      {...rest}
    >
      {value}
    </span>
  );
  if (!withTooltip) return chip;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{chip}</TooltipTrigger>
      <TooltipContent side="bottom" sideOffset={6} className="max-w-xs">
        <p className="font-semibold text-text-primary">{value}</p>
        <p className="mt-0.5 text-text-secondary">{PROJECT_STATUS_DESCRIPTIONS[value]}</p>
      </TooltipContent>
    </Tooltip>
  );
}
