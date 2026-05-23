const eurFormatter = new Intl.NumberFormat("es-ES", {
  style: "currency",
  currency: "EUR",
});

/**
 * Format a value as Euros using the Spanish locale ("4,78 €").
 *
 * Accepts numbers, numeric strings (the backend returns Decimals as strings),
 * `null`, and `undefined`. Returns "—" for the null cases or when the value
 * cannot be parsed.
 */
export function formatEuros(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const numeric = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(numeric)) return "—";
  return eurFormatter.format(numeric);
}
