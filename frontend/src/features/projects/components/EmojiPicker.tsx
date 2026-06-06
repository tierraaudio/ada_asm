import { Smile, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils/cn";

/**
 * Curated palette of project-relevant emojis. Grouped so the user can scan by
 * category. Keep this list tight — the form input still accepts ANY emoji
 * (free text), this picker is just an accelerator for common cases.
 */
const EMOJI_GROUPS: { label: string; emojis: string[] }[] = [
  {
    label: "Electrónica + potencia",
    emojis: ["⚡", "🔋", "🔌", "💡", "🔦", "🧲", "🧪", "🛠️", "🔧", "⚙️"],
  },
  {
    label: "Aeroespacial + drones",
    emojis: ["🚁", "🛩️", "✈️", "🚀", "🛰️", "📡", "🎯", "🪂", "🛸", "🧭"],
  },
  {
    label: "Automoción + transporte",
    emojis: ["🚗", "🏎️", "🚛", "🚜", "🛵", "🛻", "🚙", "🛞", "🏁", "⛽"],
  },
  {
    label: "Sensores + IoT",
    emojis: ["🌡️", "💧", "🌬️", "🧊", "🔥", "📊", "📈", "📉", "🛡️", "🔍"],
  },
  {
    label: "Energía + climáticos",
    emojis: ["☀️", "🌤️", "⛅", "🌧️", "❄️", "🌪️", "🌊", "🌍", "🌳", "🌱"],
  },
  {
    label: "Salud + medical",
    emojis: ["🩺", "💉", "💊", "🧬", "🦠", "🩹", "❤️", "🧠", "👁️", "🦷"],
  },
  {
    label: "Otros",
    emojis: ["📁", "📦", "📂", "🗂️", "🏭", "🏗️", "🧱", "🪛", "🔨", "🎛️"],
  },
];

interface EmojiPickerProps {
  /** Current emoji value (single char/cluster). */
  value: string | null | undefined;
  onChange: (next: string) => void;
  className?: string;
}

/**
 * Inline emoji picker — Popover trigger renders the current emoji (or a
 * neutral face) plus a small label. Clicking opens a curated grid grouped
 * by domain. Free-text emoji input still lives next to the picker in the
 * project form, so the user can paste anything; this primitive just
 * accelerates the common case.
 */
export function EmojiPicker({ value, onChange, className }: EmojiPickerProps) {
  const [open, setOpen] = useState(false);
  const display = value?.trim() || "";

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Elegir emoji"
          className={cn(
            "flex h-10 items-center gap-2 rounded-md border border-border bg-white px-3 text-sm",
            "hover:border-brand focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/30",
            className,
          )}
        >
          {display ? (
            <span aria-hidden className="text-base">
              {display}
            </span>
          ) : (
            <Smile className="size-4 text-text-secondary" aria-hidden />
          )}
          <span className="text-xs text-text-secondary">
            {display ? "Cambiar" : "Elegir"}
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[320px] p-3">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-sm font-semibold text-text-primary">Emoji del proyecto</p>
          {display && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={() => {
                onChange("");
                setOpen(false);
              }}
            >
              <X className="size-3" />
              Quitar
            </Button>
          )}
        </div>
        <div className="flex max-h-[320px] flex-col gap-3 overflow-y-auto">
          {EMOJI_GROUPS.map((group) => (
            <div key={group.label}>
              <p className="mb-1 text-[10px] uppercase tracking-wide text-text-secondary">
                {group.label}
              </p>
              <div className="grid grid-cols-8 gap-1">
                {group.emojis.map((emoji) => (
                  <button
                    key={emoji}
                    type="button"
                    onClick={() => {
                      onChange(emoji);
                      setOpen(false);
                    }}
                    className={cn(
                      "flex size-8 items-center justify-center rounded-md text-lg",
                      "hover:bg-muted focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/30",
                      display === emoji && "bg-brand/10 ring-1 ring-brand",
                    )}
                    aria-label={`Elegir ${emoji}`}
                    aria-pressed={display === emoji}
                  >
                    {emoji}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}
