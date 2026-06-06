import { Boxes, Cpu, FolderKanban, PanelLeftClose, PanelLeftOpen, type LucideIcon } from "lucide-react";
import type { FC } from "react";
import { NavLink, useLocation } from "react-router-dom";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { BrandLogo } from "@/features/branding/components/BrandLogo";
import { useUiStore } from "@/lib/stores/ui-store";
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
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);
  const ToggleIcon = collapsed ? PanelLeftOpen : PanelLeftClose;
  const toggleLabel = collapsed ? "Expandir menú" : "Plegar menú";
  // Compute `isActive` ourselves: Radix's `TooltipTrigger asChild` wraps the
  // NavLink in a Slot that stringifies any non-string className, which kills
  // NavLink's function-as-className. Passing a plain string sidesteps that.
  const { pathname } = useLocation();

  return (
    <aside
      role="navigation"
      aria-label="Primary"
      data-testid="app-sidebar"
      className={cn(
        "flex h-full shrink-0 flex-col border-r border-border bg-white transition-[width] duration-150",
        collapsed ? "w-16" : "w-64",
      )}
    >
      <div
        className={cn(
          "flex h-[84px] items-center border-b border-border",
          collapsed ? "justify-center px-2" : "justify-between px-4",
        )}
      >
        {!collapsed && <BrandLogo />}
        <button
          type="button"
          onClick={toggleSidebar}
          aria-label={toggleLabel}
          aria-expanded={!collapsed}
          className="flex size-9 items-center justify-center rounded-md text-text-secondary hover:bg-accent hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
        >
          <ToggleIcon className="size-5" aria-hidden="true" />
        </button>
      </div>

      <nav className={cn("flex flex-col gap-1", collapsed ? "p-2" : "p-4")}>
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => {
          const isActive = pathname === to || pathname.startsWith(`${to}/`);
          const linkClass = cn(
            "flex h-12 w-full items-center rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1",
            collapsed ? "justify-center px-0" : "gap-3 px-4",
            isActive
              ? "bg-text-primary text-white"
              : "text-text-primary hover:bg-accent hover:text-accent-foreground",
          );
          const link = (
            <NavLink key={to} to={to} className={linkClass}>
              <Icon className={cn("size-5", collapsed && "mx-auto")} aria-hidden="true" />
              {!collapsed && <span className="text-base">{label}</span>}
            </NavLink>
          );

          if (!collapsed) return link;
          return (
            <Tooltip key={to}>
              <TooltipTrigger asChild>{link}</TooltipTrigger>
              <TooltipContent side="right" sideOffset={6}>
                {label}
              </TooltipContent>
            </Tooltip>
          );
        })}
      </nav>
    </aside>
  );
};
