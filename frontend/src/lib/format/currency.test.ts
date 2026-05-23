import { describe, expect, it } from "vitest";

import { formatEuros } from "./currency";

describe("formatEuros", () => {
  it("formats positive numbers in Spanish euro style", () => {
    expect(formatEuros(8.45)).toMatch(/8,45/);
    expect(formatEuros(8.45)).toContain("€");
  });

  it("accepts string inputs (Decimals come from the API as strings)", () => {
    expect(formatEuros("12.4000")).toMatch(/12,40/);
  });

  it("returns em-dash for null, undefined, and empty string", () => {
    expect(formatEuros(null)).toBe("—");
    expect(formatEuros(undefined)).toBe("—");
    expect(formatEuros("")).toBe("—");
  });

  it("returns em-dash when the input is not a number", () => {
    expect(formatEuros("not-a-number")).toBe("—");
  });

  it("handles zero", () => {
    expect(formatEuros(0)).toMatch(/0,00/);
  });

  it("handles very small and very large values", () => {
    expect(formatEuros(0.0001)).toMatch(/0,00/);
    expect(formatEuros(1_000_000)).toMatch(/1\.000\.000,00/);
  });
});
