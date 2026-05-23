import { Boxes, Cpu, FolderKanban, type LucideIcon } from "lucide-react";
import type { FC } from "react";
import { NavLink } from "react-router-dom";

import { BrandLogo } from "@/features/branding/components/BrandLogo";
import { cn } from "@/lib/utils/cn";

type NavItem = {
  to: string;
  label: string;
  icon: LucideIcon;
};

// Domain-hierarchy order. Overrides the Figma's literal order
// (Proyectos → Componentes → Módulos) per explicit user instruction.
const NAV_ITEMS: ReadonlyArray<NavItem> = [
  { to: "/projects", label: "Proyectos", icon: FolderKanban },
  { to: "/modules", label: "Módulos", icon: Boxes },
  { to: "/components", label: "Componentes", icon: Cpu },
];

export const Sidebar: FC = () => {
  return (
    <aside
      role="navigation"
      aria-label="Primary"
      data-testid="app-sidebar"
      className="flex h-full w-64 shrink-0 flex-col border-r border-border bg-white"
    >
      <div className="flex h-[77px] items-center border-b border-border px-6">
        <BrandLogo />
      </div>

      <nav className="flex flex-col gap-1 p-4">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "flex h-12 items-center gap-3 rounded-md px-4 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1",
                isActive
                  ? "bg-text-primary text-white"
                  : "text-text-primary hover:bg-accent hover:text-accent-foreground",
              )
            }
          >
            <Icon className="size-5" aria-hidden="true" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
};
