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
