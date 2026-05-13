import { Bell } from "lucide-react";
import { type FC } from "react";

/**
 * Bell button with a red status dot — pixel-faithful to Figma 37:45.
 *
 * The dot is currently a static visual placeholder: notification state is a
 * future US, but the dot is shown in the design so we render it always. When
 * notifications land we will gate the dot behind a real "unread" boolean.
 */
export const NotificationBell: FC = () => {
  return (
    <button
      type="button"
      aria-label="Notificaciones"
      className="relative size-9 rounded-md p-2 text-text-primary hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
    >
      <Bell className="size-5" aria-hidden="true" />
      <span
        aria-hidden="true"
        className="absolute right-1 top-1 size-2 rounded-full bg-destructive"
      />
    </button>
  );
};
