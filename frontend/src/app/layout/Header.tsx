import { Menu, X } from "lucide-react";
import type { FC } from "react";

import { UserMenuPill } from "@/features/auth/components/UserMenuPill";
import { NotificationMenu } from "@/features/notifications/components/NotificationMenu";
import { useUiStore } from "@/lib/stores/ui-store";

/**
 * Authenticated dashboard header.
 *
 * Pixel-faithful to Figma 47:14343 (expanded) and 47:23460 (collapsed). The
 * layout has three slots, left → right: a sidebar toggle, an interactive
 * notification bell + panel, and the user menu pill.
 */
export const Header: FC = () => {
  const sidebarCollapsed = useUiStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);

  const ToggleIcon = sidebarCollapsed ? Menu : X;
  const toggleLabel = sidebarCollapsed ? "Mostrar menú lateral" : "Ocultar menú lateral";

  return (
    <header
      role="banner"
      data-testid="app-header"
      className="flex h-[84px] items-center justify-between border-b border-border bg-white px-6 py-4"
    >
      <button
        type="button"
        onClick={toggleSidebar}
        aria-label={toggleLabel}
        aria-expanded={!sidebarCollapsed}
        className="flex size-9 items-center justify-center rounded-md text-text-primary hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
      >
        <ToggleIcon className="size-5" aria-hidden="true" />
      </button>

      <div className="flex items-center gap-3">
        <NotificationMenu />
        <UserMenuPill />
      </div>
    </header>
  );
};
