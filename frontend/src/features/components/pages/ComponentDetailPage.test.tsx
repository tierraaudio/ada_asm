import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { server } from "@/tests/setup";
import { loginInStore, renderWithProviders } from "@/tests/utils";

import { ComponentDetailPage } from "./ComponentDetailPage";

const API = "http://localhost:8000";

const SAMPLE = {
  id: "abc",
  mpn: "ACS712",
  sku: "ACS712-30A",
  name: "Sensor Hall",
  family: "Sensores",
  description: "Sensor de corriente Hall",
  datasheet_url: null,
  location: "A-12-3",
  supplier: "DigiKey",
  price_per_100: "8.4500",
  stock: 145,
  tier: "B" as const,
  nato_score: "otan" as const,
  country_of_origin: "US",
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z",
};

describe("<ComponentDetailPage>", () => {
  it("renders header card + tabs + alerts panel", async () => {
    loginInStore();
    server.use(
      http.get(`${API}/api/v1/components/:id`, () => HttpResponse.json(SAMPLE)),
      http.get(`${API}/api/v1/components/:id/purchases`, () =>
        HttpResponse.json({ items: [], total: 0, page: 1, page_size: 100 }),
      ),
    );

    renderWithProviders(
      <Routes>
        <Route path="/components/:id" element={<ComponentDetailPage />} />
      </Routes>,
      { route: `/components/${SAMPLE.id}` },
    );

    expect(await screen.findByRole("heading", { name: "ACS712" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Detalle" })).toBeInTheDocument();
    expect(screen.getByText(/Alertas/)).toBeInTheDocument();
    // No purchases ⇒ "no_purchases" alert active. The string also appears in
    // the chart placeholder, so accept ≥ 1 occurrence.
    expect(screen.getAllByText(/Aún no hay compras registradas/).length)
      .toBeGreaterThan(0);
  });

  it("navigates back to /components on 'Volver al catálogo' click", async () => {
    loginInStore();
    server.use(
      http.get(`${API}/api/v1/components/:id`, () => HttpResponse.json(SAMPLE)),
      http.get(`${API}/api/v1/components/:id/purchases`, () =>
        HttpResponse.json({ items: [], total: 0, page: 1, page_size: 100 }),
      ),
    );

    renderWithProviders(
      <Routes>
        <Route path="/components" element={<p>landed-on-list</p>} />
        <Route path="/components/:id" element={<ComponentDetailPage />} />
      </Routes>,
      { route: `/components/${SAMPLE.id}` },
    );

    await screen.findByRole("heading", { name: "ACS712" });
    await userEvent.click(screen.getByRole("button", { name: /volver al catálogo/i }));
    expect(await screen.findByText("landed-on-list")).toBeInTheDocument();
  });

  it("renders the stock-evolution chart when purchases exist", async () => {
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
          page_size: 100,
        }),
      ),
    );

    renderWithProviders(
      <Routes>
        <Route path="/components/:id" element={<ComponentDetailPage />} />
      </Routes>,
      { route: `/components/${SAMPLE.id}` },
    );

    await screen.findByRole("heading", { name: "ACS712" });
    expect(screen.getByText(/Evolución del stock/)).toBeInTheDocument();
    // With purchases present, the no-purchases alert is gone.
    expect(screen.queryByText(/Aún no hay compras registradas/)).not.toBeInTheDocument();
  });

  it("opens the confirm delete dialog when 'Eliminar' is clicked", async () => {
    loginInStore();
    server.use(
      http.get(`${API}/api/v1/components/:id`, () => HttpResponse.json(SAMPLE)),
      http.get(`${API}/api/v1/components/:id/purchases`, () =>
        HttpResponse.json({ items: [], total: 0, page: 1, page_size: 100 }),
      ),
    );

    renderWithProviders(
      <Routes>
        <Route path="/components/:id" element={<ComponentDetailPage />} />
      </Routes>,
      { route: `/components/${SAMPLE.id}` },
    );

    await screen.findByRole("heading", { name: "ACS712" });
    await userEvent.click(screen.getByRole("button", { name: /^Eliminar$/ }));
    expect(
      await screen.findByText("¿Eliminar componente?"),
    ).toBeInTheDocument();
  });
});
