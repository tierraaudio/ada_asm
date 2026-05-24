import { Info } from "lucide-react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

import { NATO_HELP_INTRO, NATO_HELP_TITLE, NATO_SCORE_RUBRIC } from "../rubrics";
import { NATO_SCORE_VALUES } from "../types";
import { NatoScoreBadge } from "./NatoScoreBadge";

export function NatoScoreHelpPopover() {
  return (
    <Popover>
      <PopoverTrigger
        type="button"
        aria-label={NATO_HELP_TITLE}
        className="inline-flex size-4 items-center justify-center text-text-secondary hover:text-text-primary"
      >
        <Info className="size-3.5" aria-hidden />
      </PopoverTrigger>
      <PopoverContent className="w-80 p-4 text-sm" align="end">
        <h3 className="mb-1 text-sm font-semibold text-text-primary">{NATO_HELP_TITLE}</h3>
        <p className="mb-3 text-xs text-text-secondary">{NATO_HELP_INTRO}</p>
        <p className="mb-2 text-xs font-semibold text-text-primary">Niveles de clasificación:</p>
        <ul className="space-y-2">
          {NATO_SCORE_VALUES.map((value) => (
            <li key={value} className="grid grid-cols-[3.5rem_1fr] items-start gap-2">
              <NatoScoreBadge value={value} showIcon={false} withTooltip={false} />
              <span className="text-xs text-text-secondary">{NATO_SCORE_RUBRIC[value]}</span>
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
