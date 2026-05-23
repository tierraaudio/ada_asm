import { beforeEach, describe, expect, it, vi } from "vitest";

import { SIDEBAR_COLLAPSED_KEY } from "@/lib/ui/sidebar-storage";

describe("ui-store", () => {
  beforeEach(() => window.localStorage.clear());

  it("initialises sidebarCollapsed to false on a fresh load", async () => {
    const { useUiStore } = await freshImport();
    expect(useUiStore.getState().sidebarCollapsed).toBe(false);
  });

  it("reads the persisted value on initialisation", async () => {
    window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, "true");
    const { useUiStore } = await freshImport();
    expect(useUiStore.getState().sidebarCollapsed).toBe(true);
  });

  it("toggleSidebar flips and persists", async () => {
    const { useUiStore } = await freshImport();
    useUiStore.getState().toggleSidebar();
    expect(useUiStore.getState().sidebarCollapsed).toBe(true);
    expect(window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY)).toBe("true");

    useUiStore.getState().toggleSidebar();
    expect(useUiStore.getState().sidebarCollapsed).toBe(false);
    expect(window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY)).toBe("false");
  });

  it("setSidebarCollapsed writes the explicit value", async () => {
    const { useUiStore } = await freshImport();
    useUiStore.getState().setSidebarCollapsed(true);
    expect(useUiStore.getState().sidebarCollapsed).toBe(true);
    expect(window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY)).toBe("true");
  });
});

// The store reads localStorage at module init time. Reset the module registry
// before each scenario so the initial-value tests are deterministic.
async function freshImport() {
  vi.resetModules();
  return import("./ui-store");
}
