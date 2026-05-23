import type { FC } from "react";
import { Link } from "react-router-dom";

import { cn } from "@/lib/utils/cn";
import { useNotifications } from "../hooks/use-notifications";
import type { Notification } from "../types";

/**
 * Notification dropdown panel — pixel-faithful to Figma 47:14343.
 *
 * Rendered as the content of a Popover anchored under the bell. Reads from
 * the `useNotifications` hook so the future real-feed US only has to rewrite
 * the hook.
 */
export const NotificationPanel: FC = () => {
  const { items, unreadCount } = useNotifications();

  return (
    <div className="flex w-96 flex-col" data-testid="notification-panel">
      <header className="flex items-center justify-between border-b border-border p-4">
        <h3 className="text-lg font-medium leading-7 tracking-[-0.4395px] text-text-primary">
          Notificaciones
        </h3>
        {unreadCount > 0 && (
          <span className="rounded-full bg-brand px-2 py-1 text-xs leading-4 text-brand-foreground">
            {unreadCount} nuevas
          </span>
        )}
      </header>

      <ul className="max-h-[500px] overflow-y-auto">
        {items.map((item, index) => (
          <NotificationItem key={item.id} notification={item} isLast={index === items.length - 1} />
        ))}
      </ul>

      <footer className="border-t border-border py-4 text-center">
        <Link
          to="/notifications"
          className="text-sm font-medium leading-5 tracking-[-0.1504px] text-brand hover:underline focus-visible:underline focus-visible:outline-none"
        >
          Ver todas las notificaciones
        </Link>
      </footer>
    </div>
  );
};

const NotificationItem: FC<{ notification: Notification; isLast: boolean }> = ({
  notification,
  isLast,
}) => {
  return (
    <li
      className={cn(
        "relative px-4 py-4",
        !isLast && "border-b border-border",
        !notification.read && "bg-brand/5",
      )}
    >
      {!notification.read && (
        <span
          aria-label="Sin leer"
          className="absolute right-4 top-4 size-2 rounded-full bg-brand"
        />
      )}
      <p className="pr-6 text-sm font-medium leading-5 tracking-[-0.1504px] text-text-primary">
        {notification.title}
      </p>
      <p className="mt-1 text-xs leading-4 text-text-secondary">{notification.subtitle}</p>
      <p className="mt-1 text-xs leading-4 text-text-secondary">{notification.timestamp}</p>
    </li>
  );
};
