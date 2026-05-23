import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { server } from "@/tests/setup";
import { loginInStore, renderWithProviders } from "@/tests/utils";

import { ComponentNatoScoringPage } from "./ComponentNatoScoringPage";

const API = "http://localhost:8000";

const SAMPLE = {
  id: "abc",
  mpn: "ESP32-WROOM-32E",
  sku: "ESP32-E",
  name: "Modulo WiFi + Bluetooth",
  family: "Microcontroladores",
  description: null,
  datasheet_url: null,
  location: "C-01-1",
  supplier: "Mouser",
  price_per_100: "3.5500",
  stock: 280,
  tier: "A" as const,
  nato_score: "high_risk" as const,
  country_of_origin: "CN",
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z",
};

describe("<ComponentNatoScoringPage>", () => {
  it("renders tier, NATO score, country of origin and the legend", async () => {
    loginInStore();
    server.use(
      http.get(`${API}/api/v1/components/:id`, () => HttpResponse.json(SAMPLE)),
    );

    renderWithProviders(
      <Routes>
        <Route path="/components/:id/nato" element={<ComponentNatoScoringPage />} />
      </Routes>,
      { route: `/components/${SAMPLE.id}/nato` },
    );

    expect(await screen.findByRole("heading", { name: "ESP32-WROOM-32E" })).toBeInTheDocument();
    // Tier and NATO badges + textual labels.
    expect(screen.getAllByLabelText(/Tier A/i).length).toBeGreaterThan(0);
    expect(screen.getAllByLabelText(/Alto riesgo/i).length).toBeGreaterThan(0);
    // Country of origin appears at least once (header card + NATO section).
    expect(screen.getAllByText("CN").length).toBeGreaterThan(0);
    // Legend has every tier and every NATO value at minimum.
    expect(screen.getAllByLabelText(/Tier D/i).length).toBeGreaterThan(0);
    expect(screen.getAllByLabelText(/100% OTAN/i).length).toBeGreaterThan(0);
  });
});
