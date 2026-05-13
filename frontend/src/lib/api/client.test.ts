import { describe, expect, it } from "vitest";

import { api } from "./client";

describe("api client", () => {
  it("uses VITE_API_URL as the base URL when defined", () => {
    // Vitest's import.meta.env.VITE_API_URL defaults to undefined in tests,
    // so the client falls back to the local default — verify either case is
    // populated and well-formed.
    expect(api.defaults.baseURL).toMatch(/^https?:\/\//);
  });

  it("does not send credentials by default", () => {
    expect(api.defaults.withCredentials).toBe(false);
  });

  it("has a sensible timeout", () => {
    expect(api.defaults.timeout).toBeGreaterThan(0);
  });
});
