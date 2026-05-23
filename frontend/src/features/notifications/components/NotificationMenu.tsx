import type { FC } from "react";

import { NotificationBell } from "@/features/auth/components/NotificationBell";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

import { NotificationPanel } from "./NotificationPanel";

/**
 * Composes the existing NotificationBell trigger with a Popover anchored
 * panel. The bell stays a "passive" visual element; this composite owns the
 * open/close state.
 */
export const NotificationMenu: FC = () => {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <NotificationBell />
      </PopoverTrigger>
      <PopoverContent align="end" sideOffset={8} className="p-0">
        <NotificationPanel />
      </PopoverContent>
    </Popover>
  );
};
