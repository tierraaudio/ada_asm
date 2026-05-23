import { forwardRef } from "react";

const COUNTRY_OPTIONS: Array<{ code: string; label: string }> = [
  { code: "ES", label: "España" },
  { code: "DE", label: "Alemania" },
  { code: "FR", label: "Francia" },
  { code: "IT", label: "Italia" },
  { code: "GB", label: "Reino Unido" },
  { code: "US", label: "Estados Unidos" },
  { code: "CA", label: "Canadá" },
  { code: "JP", label: "Japón" },
  { code: "KR", label: "Corea del Sur" },
  { code: "TW", label: "Taiwán" },
  { code: "CN", label: "China" },
  { code: "TR", label: "Turquía" },
];

export interface CountryOfOriginSelectProps {
  value: string | null | undefined;
  onChange: (value: string) => void;
  id?: string;
  disabled?: boolean;
}

export const CountryOfOriginSelect = forwardRef<
  HTMLSelectElement,
  CountryOfOriginSelectProps
>(({ value, onChange, id, disabled }, ref) => {
  const normalized = (value ?? "").toUpperCase();
  const isCustom = normalized !== "" && !COUNTRY_OPTIONS.some((c) => c.code === normalized);
  return (
    <div className="flex flex-col gap-2 sm:flex-row">
      <select
        ref={ref}
        id={id}
        disabled={disabled}
        value={isCustom ? "__other__" : normalized}
        onChange={(e) => {
          const next = e.target.value;
          onChange(next === "__other__" ? "" : next);
        }}
        className="h-10 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
      >
        <option value="">— Sin especificar —</option>
        {COUNTRY_OPTIONS.map((c) => (
          <option key={c.code} value={c.code}>
            {c.code} — {c.label}
          </option>
        ))}
        <option value="__other__">Otro…</option>
      </select>
      {isCustom && (
        <input
          type="text"
          value={normalized}
          maxLength={2}
          onChange={(e) => onChange(e.target.value.toUpperCase())}
          placeholder="XX"
          aria-label="Código ISO 3166-1 alpha-2"
          className="h-10 w-24 rounded-md border border-input bg-background px-3 text-sm uppercase focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
        />
      )}
    </div>
  );
});
CountryOfOriginSelect.displayName = "CountryOfOriginSelect";
