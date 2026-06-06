import type { FC } from "react";

import { UserMenuPill } from "@/features/auth/components/UserMenuPill";
import { NotificationMenu } from "@/features/notifications/components/NotificationMenu";

/**
 * Authenticated dashboard header.
 *
 * The sidebar (rendered to the left of this header) owns its own
 * fold/unfold toggle, so this strip is just the notification bell + user
 * menu pill on the right edge.
 */
export const Header: FC = () => {
  return (
    <header
      role="banner"
      data-testid="app-header"
      className="flex h-[84px] items-center justify-end gap-3 border-b border-border bg-white px-6 py-4"
    >
      <NotificationMenu />
      <UserMenuPill />
    </header>
  );
};
