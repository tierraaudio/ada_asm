import { Info } from "lucide-react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

import { TIER_HELP_INTRO, TIER_HELP_TITLE, TIER_RUBRIC } from "../rubrics";
import { TIER_VALUES } from "../types";
import { TierBadge } from "./TierBadge";

export function TierHelpPopover() {
  return (
    <Popover>
      <PopoverTrigger
        type="button"
        aria-label={TIER_HELP_TITLE}
        className="inline-flex size-4 items-center justify-center text-text-secondary hover:text-text-primary"
      >
        <Info className="size-3.5" aria-hidden />
      </PopoverTrigger>
      <PopoverContent className="w-80 p-4 text-sm" align="end">
        <h3 className="mb-1 text-sm font-semibold text-text-primary">{TIER_HELP_TITLE}</h3>
        <p className="mb-3 text-xs text-text-secondary">{TIER_HELP_INTRO}</p>
        <p className="mb-2 text-xs font-semibold text-text-primary">Niveles de TIER:</p>
        <ul className="space-y-2">
          {TIER_VALUES.map((value) => (
            <li key={value} className="grid grid-cols-[4rem_1fr] items-start gap-3">
              <TierBadge value={value} />
              <span className="text-xs text-text-secondary">
                <span className="block font-medium text-text-primary">
                  {TIER_RUBRIC[value].category}
                </span>
                Riesgo: {TIER_RUBRIC[value].risk}
              </span>
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
