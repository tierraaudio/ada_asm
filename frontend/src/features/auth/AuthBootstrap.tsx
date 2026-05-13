import { useEffect, useState, type ReactNode, type FC } from "react";

import { authApi } from "./api/auth-api";
import { useAuthStore } from "@/lib/stores/auth-store";
import { readRefreshToken, writeRefreshToken, clearRefreshToken } from "@/lib/auth/token-storage";

/**
 * Renders nothing of its own — wraps `children` and runs once on mount:
 *  1. If a refresh token sits in localStorage, attempt a refresh.
 *  2. On success, pull /auth/me to repopulate the user slice.
 *  3. On failure, clear state and remain anonymous.
 * Until the bootstrap resolves we render `fallback` (defaults to nothing)
 * so the router doesn't flash a redirect for the half-second the refresh
 * takes on hard-reload.
 */
export const AuthBootstrap: FC<{ children: ReactNode; fallback?: ReactNode }> = ({
  children,
  fallback = null,
}) => {
  const setSession = useAuthStore((s) => s.setSession);
  const clearSession = useAuthStore((s) => s.clearSession);
  const [ready, setReady] = useState(() => readRefreshToken() === null);

  useEffect(() => {
    let cancelled = false;
    if (ready) return;

    (async () => {
      const refreshToken = readRefreshToken();
      if (!refreshToken) {
        if (!cancelled) setReady(true);
        return;
      }
      try {
        const tokens = await authApi.refresh(refreshToken);
        writeRefreshToken(tokens.refresh_token);
        // Temporarily set the access token so getMe is authorised, then
        // fetch the user.
        useAuthStore.setState({ accessToken: tokens.access_token });
        const me = await authApi.getMe();
        if (!cancelled) {
          setSession(tokens.access_token, me);
        }
      } catch {
        clearRefreshToken();
        if (!cancelled) clearSession();
      } finally {
        if (!cancelled) setReady(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [ready, setSession, clearSession]);

  return <>{ready ? children : fallback}</>;
};
