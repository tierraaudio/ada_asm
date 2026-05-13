import type { FC } from "react";

import { UserMenuPill } from "@/features/auth/components/UserMenuPill";

/**
 * Authenticated dashboard header — pixel-faithful to Figma 37:45.
 *
 * Left side: reserved for a future sidebar collapse / title block.
 * Right side: notification bell + user menu pill (with logout dropdown).
 */
export const Header: FC = () => {
  return (
    <header
      role="banner"
      data-testid="app-header"
      className="flex h-[84px] items-center justify-between border-b border-border bg-white px-6 py-4"
    >
      <div aria-hidden="true" className="size-9" />
      <UserMenuPill />
    </header>
  );
};
