import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { server } from "@/tests/setup";
import { loginInStore, renderWithProviders } from "@/tests/utils";

import { ComponentPurchaseHistoryPage } from "./ComponentPurchaseHistoryPage";

const API = "http://localhost:8000";

const SAMPLE = {
  id: "abc",
  mpn: "BME280",
  sku: "BME280-ENV",
  name: "Sensor T/H/P",
  family: "Sensores",
  description: null,
  datasheet_url: null,
  location: "A-08-2",
  supplier: "DigiKey",
  price_per_100: "4.7800",
  stock: 320,
  tier: "B" as const,
  nato_score: "allied_otan" as const,
  country_of_origin: "JP",
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z",
};

describe("<ComponentPurchaseHistoryPage>", () => {
  it("renders the cost-trend chart and history table when purchases exist", async () => {
    loginInStore();
    server.use(
      http.get(`${API}/api/v1/components/:id`, () => HttpResponse.json(SAMPLE)),
      http.get(`${API}/api/v1/components/:id/purchases`, () =>
        HttpResponse.json({
          items: [
            {
              id: "p1",
              component_id: SAMPLE.id,
              purchased_at: "2026-04-01",
              quantity: 100,
              supplier: "DigiKey",
              unit_cost: "0.0480",
              total_cost: "4.8000",
              currency: "EUR",
              created_at: "2026-04-01T00:00:00Z",
            },
          ],
          total: 1,
          page: 1,
          page_size: 25,
        }),
      ),
    );

    renderWithProviders(
      <Routes>
        <Route
          path="/components/:id/purchases"
          element={<ComponentPurchaseHistoryPage />}
        />
      </Routes>,
      { route: `/components/${SAMPLE.id}/purchases` },
    );

    expect(await screen.findByRole("heading", { name: "BME280" })).toBeInTheDocument();
    const rows = await screen.findAllByRole("row");
    // 1 header + 1 data
    expect(rows.length).toBeGreaterThanOrEqual(2);
    expect(within(rows[1]!).getByText("DigiKey")).toBeInTheDocument();
  });

  it("shows the empty placeholder when there are no purchases", async () => {
    loginInStore();
    server.use(
      http.get(`${API}/api/v1/components/:id`, () => HttpResponse.json(SAMPLE)),
      http.get(`${API}/api/v1/components/:id/purchases`, () =>
        HttpResponse.json({ items: [], total: 0, page: 1, page_size: 25 }),
      ),
    );

    renderWithProviders(
      <Routes>
        <Route
          path="/components/:id/purchases"
          element={<ComponentPurchaseHistoryPage />}
        />
      </Routes>,
      { route: `/components/${SAMPLE.id}/purchases` },
    );

    await screen.findByRole("heading", { name: "BME280" });
    expect(
      screen.getAllByText(/Aún no hay compras registradas/).length,
    ).toBeGreaterThan(0);
  });
});
