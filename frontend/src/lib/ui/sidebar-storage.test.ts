import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  SIDEBAR_COLLAPSED_KEY,
  clearSidebarCollapsed,
  readSidebarCollapsed,
  writeSidebarCollapsed,
} from "./sidebar-storage";

describe("sidebar-storage", () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(() => window.localStorage.clear());

  it("returns false when nothing has been written", () => {
    expect(readSidebarCollapsed()).toBe(false);
  });

  it("round-trips the boolean as a string", () => {
    writeSidebarCollapsed(true);
    expect(window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY)).toBe("true");
    expect(readSidebarCollapsed()).toBe(true);

    writeSidebarCollapsed(false);
    expect(window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY)).toBe("false");
    expect(readSidebarCollapsed()).toBe(false);
  });

  it("clear removes the entry", () => {
    writeSidebarCollapsed(true);
    clearSidebarCollapsed();
    expect(window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY)).toBeNull();
    expect(readSidebarCollapsed()).toBe(false);
  });
});
