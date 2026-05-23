/**
 * localStorage owner for the dashboard sidebar collapse state.
 *
 * Centralised here so a future change can swap the persistence target (e.g.,
 * server-side user preferences) without touching components or the Zustand
 * store. Mirrors the pattern of `lib/auth/token-storage.ts`.
 */

export const SIDEBAR_COLLAPSED_KEY = "adaasm.ui.sidebarCollapsed";

export function readSidebarCollapsed(): boolean {
  try {
    return window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true";
  } catch {
    return false;
  }
}

export function writeSidebarCollapsed(collapsed: boolean): void {
  try {
    window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(collapsed));
  } catch {
    /* SSR / private-mode: silently drop */
  }
}

export function clearSidebarCollapsed(): void {
  try {
    window.localStorage.removeItem(SIDEBAR_COLLAPSED_KEY);
  } catch {
    /* see above */
  }
}
