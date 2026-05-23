import { describe, expect, it } from "vitest";

import {
  computeAlerts,
  lowStockAlert,
  noPurchasesAlert,
  staleSupplierAlert,
} from "./alerts";
import type { Component, ComponentPurchase } from "./types";

const baseComponent: Component = {
  id: "abc",
  mpn: "X",
  sku: null,
  name: "x",
  family: "Sensores",
  description: null,
  datasheet_url: null,
  location: null,
  supplier: null,
  price_per_100: null,
  stock: 100,
  tier: "C",
  nato_score: "neutral",
  country_of_origin: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function purchase(daysAgo: number): ComponentPurchase {
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  return {
    id: `p-${daysAgo}`,
    component_id: "abc",
    purchased_at: d.toISOString().slice(0, 10),
    quantity: 100,
    supplier: "DigiKey",
    unit_cost: "1.0000",
    total_cost: "100.0000",
    currency: "EUR",
    created_at: d.toISOString(),
  };
}

describe("alerts", () => {
  it("low-stock triggers when stock < 10", () => {
    expect(lowStockAlert({ ...baseComponent, stock: 5 })).not.toBeNull();
    expect(lowStockAlert({ ...baseComponent, stock: 10 })).toBeNull();
    expect(lowStockAlert({ ...baseComponent, stock: 100 })).toBeNull();
  });

  it("no-purchases triggers when purchases array is empty", () => {
    expect(noPurchasesAlert([])).not.toBeNull();
    expect(noPurchasesAlert([purchase(5)])).toBeNull();
  });

  it("stale-supplier triggers when newest purchase is older than 180 days", () => {
    expect(staleSupplierAlert([purchase(200)])).not.toBeNull();
    expect(staleSupplierAlert([purchase(5)])).toBeNull();
    expect(staleSupplierAlert([])).toBeNull();
  });

  it("computeAlerts aggregates and filters out nulls", () => {
    const all = computeAlerts({ ...baseComponent, stock: 2 }, []);
    expect(all.map((a) => a.id)).toEqual(["low_stock", "no_purchases"]);

    const none = computeAlerts(baseComponent, [purchase(5)]);
    expect(none).toEqual([]);
  });
});
