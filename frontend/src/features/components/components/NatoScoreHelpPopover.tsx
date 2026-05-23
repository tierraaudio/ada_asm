import { HelpCircle } from "lucide-react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

import { NATO_SCORE_DESCRIPTIONS, NATO_SCORE_LABELS } from "../rubrics";
import { NATO_SCORE_VALUES } from "../types";

export function NatoScoreHelpPopover() {
  return (
    <Popover>
      <PopoverTrigger
        type="button"
        aria-label="¿Qué es el Scoring OTAN?"
        className="inline-flex size-5 items-center justify-center rounded-full text-muted-foreground hover:text-foreground"
      >
        <HelpCircle className="size-4" />
      </PopoverTrigger>
      <PopoverContent className="w-80 p-4 text-sm">
        <h3 className="mb-2 text-sm font-semibold">Scoring OTAN</h3>
        <p className="mb-3 text-xs text-muted-foreground">
          Clasifica el origen geopolítico del componente para nuestra cadena de
          suministro.
        </p>
        <dl className="space-y-2">
          {NATO_SCORE_VALUES.map((value) => (
            <div key={value} className="grid grid-cols-[7rem_1fr] items-baseline gap-2">
              <dt className="text-xs font-semibold">{NATO_SCORE_LABELS[value]}</dt>
              <dd className="text-xs text-muted-foreground">
                {NATO_SCORE_DESCRIPTIONS[value]}
              </dd>
            </div>
          ))}
        </dl>
      </PopoverContent>
    </Popover>
  );
}
