import {
  Activity,
  Box,
  Cable,
  CircuitBoard,
  Cpu,
  type LucideIcon,
  Package,
  Triangle,
  Wifi,
  Zap,
} from "lucide-react";

/**
 * Map a component family name to a Lucide icon. The Figma uses Lucide-style
 * line icons; we lean on the same library so we render the same glyphs.
 * Unknown families fall back to a neutral `Package` so the column never
 * shows a broken slot.
 */
const FAMILY_ICONS: Record<string, LucideIcon> = {
  Microcontroladores: Cpu,
  Condensadores: CircuitBoard,
  Resistencias: Activity,
  Sensores: Activity,
  "Fuentes de alimentación": Zap,
  Diodos: Triangle,
  Transistores: Zap,
  Conectores: Cable,
  Módulos: Wifi,
  Discretos: Box,
};

export function iconForFamily(family: string): LucideIcon {
  return FAMILY_ICONS[family] ?? Package;
}

/**
 * Short description per component family — surfaced by `FamilyChip` on hover.
 * Mirrors the user-friendly copy on the components Figma and the rubric the
 * warehouse team operates with day-to-day.
 */
const FAMILY_DESCRIPTIONS: Record<string, string> = {
  Microcontroladores: "Unidades de procesamiento — MCUs, MPUs, SoCs.",
  Sensores: "Adquisición física: temperatura, presión, inercial, distancia, óptico.",
  Conectores: "Interconexión mecánica/eléctrica — USB, JST, headers, bornas.",
  Resistencias: "Componentes pasivos de resistencia (SMD y through-hole).",
  Condensadores: "Componentes pasivos de capacitancia (cerámicos, electrolíticos, tantalio).",
  Inductores: "Bobinas y choques (filtrado de potencia + comunicaciones).",
  Diodos: "Rectificación + protección (Schottky, Zener, TVS, LEDs).",
  Transistores: "Switching + amplificación (BJT, MOSFET, IGBT).",
  Módulos: "Submódulos prefabricados (radios, conversores, drivers integrados).",
  "Fuentes de alimentación": "Pilas, conversores AC/DC, DC/DC step-up/step-down.",
  Discretos: "Componentes pasivos sueltos sin categoría más específica.",
};

export function descriptionForFamily(family: string): string {
  return FAMILY_DESCRIPTIONS[family] ?? "Componente electrónico.";
}
