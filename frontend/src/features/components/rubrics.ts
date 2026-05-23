import type { NatoScoreValue, TierValue } from "./types";

export const TIER_LABELS: Record<TierValue, string> = {
  "A+": "A+",
  A: "A",
  B: "B",
  C: "C",
  D: "D",
};

export const TIER_DESCRIPTIONS: Record<TierValue, string> = {
  "A+": "Componente crítico y de alta visibilidad: requiere segundo proveedor, plan de obsolescencia y validaciones extra.",
  A: "Componente crítico para el producto final: requiere stock estratégico y proveedor cualificado.",
  B: "Componente importante con varios proveedores cualificados, gestión estándar.",
  C: "Componente estándar de consumo regular y bajo riesgo de discontinuación.",
  D: "Commodity sin requisitos especiales — disponible en cualquier distribuidor.",
};

export const NATO_SCORE_LABELS: Record<NatoScoreValue, string> = {
  "100_otan": "100% OTAN",
  otan: "OTAN",
  allied_otan: "Aliados OTAN",
  neutral: "Neutral",
  high_risk: "Alto riesgo",
  no_otan: "No OTAN",
};

export const NATO_SCORE_DESCRIPTIONS: Record<NatoScoreValue, string> = {
  "100_otan": "Fabricado íntegramente en países miembros de la OTAN.",
  otan: "Fabricado mayoritariamente en países miembros de la OTAN.",
  allied_otan: "Fabricado en países aliados de la OTAN (Japón, Corea del Sur, etc.).",
  neutral: "Origen en país neutral, sin alineación clara con la OTAN ni con sus rivales.",
  high_risk: "Origen en país de alto riesgo geopolítico para nuestra cadena de suministro.",
  no_otan: "Origen explícitamente fuera del bloque OTAN — escalado al equipo de compras.",
};
