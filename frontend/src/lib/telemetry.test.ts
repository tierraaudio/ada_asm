import { afterEach, describe, expect, it, vi } from "vitest";

import { _resetForTests, getAppInsights, init } from "./telemetry";

describe("telemetry", () => {
  afterEach(() => {
    _resetForTests();
    vi.restoreAllMocks();
  });

  it("is a no-op when the connection string is undefined", () => {
    const result = init(undefined);
    expect(result).toBe(false);
    expect(getAppInsights()).toBeNull();
  });

  it("is a no-op when the connection string is empty", () => {
    const result = init("");
    expect(result).toBe(false);
    expect(getAppInsights()).toBeNull();
  });

  it("is a no-op when the connection string is whitespace only", () => {
    const result = init("   ");
    expect(result).toBe(false);
    expect(getAppInsights()).toBeNull();
  });

  it("returns the cached instance on a second init() call", () => {
    // Mocked AI: we only check the idempotency contract, not the
    // network behaviour (covered in App Insights' own test suite).
    const result1 = init(
      "InstrumentationKey=00000000-0000-0000-0000-000000000000;IngestionEndpoint=https://westeurope-1.in.applicationinsights.azure.com/",
    );
    const result2 = init(
      "InstrumentationKey=00000000-0000-0000-0000-000000000000;IngestionEndpoint=https://westeurope-1.in.applicationinsights.azure.com/",
    );
    expect(result1).toBe(true);
    expect(result2).toBe(true);
    expect(getAppInsights()).not.toBeNull();
  });

  it("is a no-op (never throws) when the connection string is malformed", () => {
    // A Key Vault placeholder like "CHANGE_ME" reaching the build must
    // degrade to no-telemetry, not crash the app before first render.
    const result = init("CHANGE_ME");
    expect(result).toBe(false);
    expect(getAppInsights()).toBeNull();
  });
});

