import { Bell } from "lucide-react";
import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

/**
 * Bell button with a red status dot — pixel-faithful to Figma 37:45.
 *
 * The dot is currently a static visual placeholder: notification state is a
 * future US, but the dot is shown in the design so we render it always. When
 * notifications land we will gate the dot behind a real "unread" boolean.
 *
 * Exposed as `forwardRef` so Radix's `asChild` Slot in `<NotificationMenu>`
 * can wire its trigger ref and onClick handler onto the underlying button.
 * The `cn(...)` merge ensures Slot's injected className composes with the
 * default visual styles instead of replacing them.
 */
export const NotificationBell = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement>
>(({ className, children, ...props }, ref) => {
  return (
    <button
      ref={ref}
      type="button"
      aria-label="Notificaciones"
      className={cn(
        "relative size-9 rounded-md p-2 text-text-primary hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1",
        className,
      )}
      {...props}
    >
      <Bell className="size-5" aria-hidden="true" />
      <span
        aria-hidden="true"
        className="absolute right-1 top-1 size-2 rounded-full bg-destructive"
      />
      {children}
    </button>
  );
});
NotificationBell.displayName = "NotificationBell";
