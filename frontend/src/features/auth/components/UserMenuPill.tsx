import { ChevronDown, LogOut, User as UserIcon } from "lucide-react";
import { type FC, useCallback } from "react";
import { useNavigate } from "react-router-dom";

import { authApi } from "../api/auth-api";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { clearRefreshToken, readRefreshToken } from "@/lib/auth/token-storage";
import { useAuthStore } from "@/lib/stores/auth-store";

import { NotificationBell } from "./NotificationBell";

function roleDisplay(role: "admin" | "user"): string {
  return role === "admin" ? "Administrator" : "User";
}

/**
 * Authenticated user pill rendered in the Header — pixel-faithful to Figma
 * node 37:45.
 *
 * Composition:
 *  - NotificationBell on the left (36 px button + 8 px red dot).
 *  - A clickable pill (52 px tall) with:
 *      avatar (32 px, magenta) + full_name (14 px / medium) + role (12 px /
 *      medium / text-secondary) + chevron-down (16 px).
 *  - Dropdown (256 px) anchored under the pill: name (16 px), email
 *    (14 px / text-secondary), role (12 px / text-secondary), divider,
 *    "Cerrar sesión" item in destructive red with a leading LogOut icon.
 */
export const UserMenuPill: FC = () => {
  const user = useAuthStore((s) => s.user);
  const clearSession = useAuthStore((s) => s.clearSession);
  const navigate = useNavigate();

  const onLogout = useCallback(async () => {
    const refreshToken = readRefreshToken();
    if (refreshToken) {
      try {
        await authApi.logout(refreshToken);
      } catch (err) {
        console.warn("auth.logout backend call failed, proceeding with local logout", err);
      }
    }
    clearSession();
    clearRefreshToken();
    navigate("/login", { replace: true });
  }, [clearSession, navigate]);

  if (!user) return null;

  return (
    <div className="flex items-center gap-1">
      <NotificationBell />
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label={`Menú de usuario, ${user.full_name}`}
            className="flex h-[52px] items-center gap-3 rounded-md px-3 py-2 hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1 data-[state=open]:bg-accent"
          >
            <Avatar>
              <AvatarFallback>
                <UserIcon className="size-5" aria-hidden="true" />
              </AvatarFallback>
            </Avatar>
            <span className="flex min-w-0 flex-col items-start">
              <span className="truncate text-sm font-medium leading-5 tracking-[-0.1504px] text-text-primary">
                {user.full_name || user.email}
              </span>
              <span className="truncate text-xs font-medium leading-4 text-text-secondary">
                {roleDisplay(user.global_role)}
              </span>
            </span>
            <ChevronDown
              className="size-4 shrink-0 text-text-secondary"
              aria-hidden="true"
            />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" sideOffset={8} className="w-64 p-0">
          <div className="flex flex-col gap-1 p-4">
            <p className="text-base font-medium leading-6 tracking-[-0.3125px] text-text-primary">
              {user.full_name || user.email}
            </p>
            <p className="text-sm leading-5 tracking-[-0.1504px] text-text-secondary">
              {user.email}
            </p>
            <p className="text-xs leading-4 text-text-secondary">
              {roleDisplay(user.global_role)}
            </p>
          </div>
          <DropdownMenuSeparator />
          <DropdownMenuItem destructive onSelect={onLogout}>
            <LogOut className="size-4" aria-hidden="true" />
            Cerrar sesión
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
};
