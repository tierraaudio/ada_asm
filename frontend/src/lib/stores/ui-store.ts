import { create } from "zustand";

import { readSidebarCollapsed, writeSidebarCollapsed } from "@/lib/ui/sidebar-storage";

type UiState = {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (value: boolean) => void;
};

/**
 * Persisted UI state shared across the dashboard chrome.
 *
 * Initial value is read SYNCHRONOUSLY from localStorage so the first paint
 * does not flash the wrong state on a hard refresh. Mutations are mirrored
 * back to localStorage by each action so persistence stays in one place.
 */
export const useUiStore = create<UiState>((set) => ({
  sidebarCollapsed: readSidebarCollapsed(),
  toggleSidebar: () =>
    set((state) => {
      const next = !state.sidebarCollapsed;
      writeSidebarCollapsed(next);
      return { sidebarCollapsed: next };
    }),
  setSidebarCollapsed: (value) => {
    writeSidebarCollapsed(value);
    set({ sidebarCollapsed: value });
  },
}));
