/**
 * Owns the localStorage key for the refresh token. Centralising this here
 * keeps the storage key referenced in exactly one place across the app so
 * tests can clear it deterministically and a future migration (e.g. to
 * HttpOnly cookies) only touches one file.
 *
 * Trade-off documented in design.md: the refresh token lives in localStorage
 * so a hard reload of an authenticated session can recover without forcing
 * the user back to /login. This is XSS-attractive; the project assumes no
 * untrusted-HTML rendering and short access-token TTLs cap the blast radius.
 */

export const REFRESH_TOKEN_KEY = "adaasm.auth.refreshToken";

export function readRefreshToken(): string | null {
  try {
    return window.localStorage.getItem(REFRESH_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function writeRefreshToken(token: string): void {
  try {
    window.localStorage.setItem(REFRESH_TOKEN_KEY, token);
  } catch {
    /* SSR / private-mode safari: silently drop. */
  }
}

export function clearRefreshToken(): void {
  try {
    window.localStorage.removeItem(REFRESH_TOKEN_KEY);
  } catch {
    /* see above */
  }
}
