import { NavLink } from "react-router-dom";

import { cn } from "@/lib/utils/cn";

const TABS: Array<{ to: string; label: string; end: boolean }> = [
  { to: "", label: "Detalle", end: true },
  { to: "purchases", label: "Historial", end: false },
  { to: "nato", label: "Scoring OTAN", end: false },
];

export function ComponentDetailTabs({ componentId }: { componentId: string }) {
  return (
    <nav
      role="tablist"
      aria-label="Vistas del componente"
      className="flex border-b border-border"
    >
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={`/components/${componentId}${tab.to ? `/${tab.to}` : ""}`}
          end={tab.end}
          role="tab"
          className={({ isActive }) =>
            cn(
              "px-4 py-3 text-sm font-medium text-text-secondary transition-colors",
              "hover:text-text-primary",
              isActive && "border-b-2 border-brand text-text-primary",
            )
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}
