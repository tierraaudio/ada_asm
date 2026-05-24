import { cn } from "@/lib/utils/cn";

export type Period = "week" | "month" | "year";

const OPTIONS: Array<{ value: Period; label: string }> = [
  { value: "week", label: "Semana" },
  { value: "month", label: "Mes" },
  { value: "year", label: "Año" },
];

/** Lower bound for the period window, anchored on "now". */
export function periodCutoff(period: Period): Date {
  const now = new Date();
  const out = new Date(now);
  if (period === "week") out.setDate(now.getDate() - 7);
  else if (period === "month") out.setMonth(now.getMonth() - 1);
  else out.setFullYear(now.getFullYear() - 1);
  return out;
}

interface PeriodToggleProps {
  value: Period;
  onChange: (value: Period) => void;
  className?: string;
}

export function PeriodToggle({ value, onChange, className }: PeriodToggleProps) {
  return (
    <div
      className={cn("inline-flex rounded-md border border-border bg-white p-0.5", className)}
      role="radiogroup"
      aria-label="Periodo"
    >
      {OPTIONS.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(opt.value)}
            className={cn(
              "rounded px-3 py-1 text-xs font-medium transition-colors",
              active ? "bg-brand text-white" : "text-text-secondary hover:bg-muted",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
