import type { NatoScoreValue, TierValue } from "@/features/shared/enums";

/* Labels and rubric copy taken verbatim from Figma node 47:15264 (NATO popover)
 * and the Tier popover the user provided. Do not paraphrase — the design owns
 * the wording. */

export const TIER_LABELS: Record<TierValue, string> = {
  1: "Tier 1",
  2: "Tier 2",
  3: "Tier 3",
  4: "Tier 4",
};

export interface TierRubricEntry {
  label: string;
  category: string;
  risk: string;
}

export const TIER_RUBRIC: Record<TierValue, TierRubricEntry> = {
  1: { label: "Tier 1", category: "Chips y microcontroladores", risk: "Muy alto" },
  2: { label: "Tier 2", category: "Sensores", risk: "Alto" },
  3: { label: "Tier 3", category: "Componentes pasivos", risk: "Medio" },
  4: { label: "Tier 4", category: "Plásticos, placas, conectores", risk: "Bajo" },
};

export const TIER_HELP_TITLE = "¿Qué es el TIER?";
export const TIER_HELP_INTRO =
  "Complejidad del componente y riesgo de no ser OTAN: no es lo mismo un trozo de plástico que un microchip con posibles puertas traseras.";

export const NATO_SCORE_LABELS: Record<NatoScoreValue, string> = {
  "A+": "A+",
  A: "A",
  B: "B",
  C: "C",
  D: "D",
  F: "F",
};

export const NATO_SCORE_RUBRIC: Record<NatoScoreValue, string> = {
  "A+": "100% OTAN - Todos los componentes verificados",
  A: "OTAN - Componentes de países OTAN",
  B: "Aliados OTAN - Componentes de países aliados",
  C: "Neutral - Requiere revisión",
  D: "Alto riesgo - Componentes de origen no verificado",
  F: "No OTAN - Componentes de países no aliados",
};

export const NATO_HELP_TITLE = "¿Qué es el Scoring OTAN?";
export const NATO_HELP_INTRO =
  "Revisión de Supply Chain para comprobar que todos los componentes son OTAN o aliados.";
