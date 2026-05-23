import { describe, expect, it } from "vitest";

import { componentCreateSchema, componentUpdateSchema } from "./schemas";

const validMinimal = {
  mpn: "TEST-001",
  name: "Test",
  family: "Sensores",
  tier: "B" as const,
  nato_score: "otan" as const,
};

describe("componentCreateSchema", () => {
  it("accepts the minimal happy payload", () => {
    const parsed = componentCreateSchema.parse(validMinimal);
    expect(parsed.mpn).toBe("TEST-001");
    expect(parsed.stock).toBe(0);
  });

  it("rejects an empty mpn", () => {
    const r = componentCreateSchema.safeParse({ ...validMinimal, mpn: "" });
    expect(r.success).toBe(false);
  });

  it("rejects an empty name", () => {
    const r = componentCreateSchema.safeParse({ ...validMinimal, name: "" });
    expect(r.success).toBe(false);
  });

  it("rejects an unknown tier", () => {
    const r = componentCreateSchema.safeParse({ ...validMinimal, tier: "Z" });
    expect(r.success).toBe(false);
  });

  it("rejects an unknown nato_score", () => {
    const r = componentCreateSchema.safeParse({
      ...validMinimal,
      nato_score: "garbage",
    });
    expect(r.success).toBe(false);
  });

  it("rejects a negative stock", () => {
    const r = componentCreateSchema.safeParse({ ...validMinimal, stock: -1 });
    expect(r.success).toBe(false);
  });

  it("rejects a lowercase country code", () => {
    const r = componentCreateSchema.safeParse({
      ...validMinimal,
      country_of_origin: "us",
    });
    expect(r.success).toBe(false);
  });

  it("accepts a valid 2-letter uppercase country code", () => {
    const r = componentCreateSchema.parse({
      ...validMinimal,
      country_of_origin: "US",
    });
    expect(r.country_of_origin).toBe("US");
  });

  it("normalises empty strings to undefined for optional fields", () => {
    const r = componentCreateSchema.parse({
      ...validMinimal,
      sku: "",
      description: "",
      datasheet_url: "",
      country_of_origin: "",
    });
    expect(r.sku).toBeUndefined();
    expect(r.description).toBeUndefined();
    expect(r.datasheet_url).toBeUndefined();
    expect(r.country_of_origin).toBeUndefined();
  });

  it("rejects an invalid URL for datasheet_url", () => {
    const r = componentCreateSchema.safeParse({
      ...validMinimal,
      datasheet_url: "not-a-url",
    });
    expect(r.success).toBe(false);
  });

  it("rejects a negative price_per_100", () => {
    const r = componentCreateSchema.safeParse({
      ...validMinimal,
      price_per_100: "-1",
    });
    expect(r.success).toBe(false);
  });
});

describe("componentUpdateSchema", () => {
  it("accepts an empty object (no-op patch)", () => {
    const r = componentUpdateSchema.parse({});
    expect(r).toEqual({});
  });

  it("does not allow mpn to be set", () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const r = componentUpdateSchema.safeParse({ mpn: "X" } as any);
    expect(r.success).toBe(true);
    if (r.success) expect((r.data as Record<string, unknown>).mpn).toBeUndefined();
  });

  it("validates partial fields", () => {
    const r = componentUpdateSchema.parse({ name: "Renamed" });
    expect(r.name).toBe("Renamed");
  });
});
